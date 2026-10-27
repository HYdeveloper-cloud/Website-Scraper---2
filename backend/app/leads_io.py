"""Stage C: CSV/Excel upload with column mapping, bulk actions, Do Not Call list."""
import csv
import io
import re
import time
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from . import discovery, llm
from .db import get_db
from .deps import audit
from .models import DNC, CallTask, DiscoveryRun, Lead, Market, User
from .phones import market_of, normalize
from .security import current_user

router = APIRouter()
UPLOADS: dict[str, dict] = {}
FIELDS = ["business_name", "contact_name", "phone", "email", "website", "city", "market", "industry", "notes"]
SYN = {"business_name": ["business", "company", "name", "organization", "organisation"],
       "contact_name": ["contact", "person", "owner", "manager", "first name"],
       "phone": ["phone", "mobile", "tel", "whatsapp", "number"], "email": ["email", "e-mail", "mail"],
       "website": ["website", "web", "url", "site", "domain"], "city": ["city", "town", "location"],
       "market": ["market", "country"], "industry": ["industry", "category", "sector", "type"],
       "notes": ["note", "comment", "remark"]}
STATUSES = ["New", "Queued", "Contacted", "Interested", "Meeting Booked", "Follow-up Pending",
            "Not Interested", "Do Not Call", "Wrong Number", "Unreachable", "Won", "Lost"]
COUNTRY_CODE = {"uae": "AE", "united arab emirates": "AE", "emirates": "AE", "saudi arabia": "SA", "ksa": "SA", "saudi": "SA",
                "uk": "GB", "united kingdom": "GB", "england": "GB", "gb": "GB", "usa": "US", "us": "US", "united states": "US",
                "america": "US", "australia": "AU", "au": "AU", "ae": "AE", "sa": "SA"}


def read_table(filename: str, data: bytes):
    name = filename.lower()
    if len(data) > 5_000_000:
        raise ValueError("File is larger than 5 MB. Split it into smaller files.")
    if name.endswith(".xlsx"):
        from openpyxl import load_workbook
        ws = load_workbook(io.BytesIO(data), read_only=True, data_only=True).worksheets[0]
        rows = [["" if c is None else str(c).strip() for c in r] for r in ws.iter_rows(values_only=True)]
    elif name.endswith((".csv", ".txt")):
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = data.decode("cp1252")
        try:
            dialect = csv.Sniffer().sniff(text[:4000], delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        rows = [[c.strip() for c in r] for r in csv.reader(io.StringIO(text), dialect)]
    else:
        raise ValueError("Upload a .csv or .xlsx file. Older .xls files: save as .xlsx first.")
    rows = [r for r in rows if any(c for c in r)]
    if len(rows) < 2:
        raise ValueError("The file needs a header row and at least one lead.")
    header = [h or f"Column {i + 1}" for i, h in enumerate(rows[0])]
    body = [dict(zip(header, r + [""] * (len(header) - len(r)))) for r in rows[1:5001]]
    return header, body


def suggest(header: list[str]) -> dict:
    out, used = {}, set()
    for field in FIELDS:
        for h in header:
            if h not in used and any(k in h.lower() for k in SYN[field]):
                out[field] = h
                used.add(h)
                break
    return out


@router.post("/api/leads/upload/preview")
async def preview(file: UploadFile = File(...), _: User = Depends(current_user)):
    try:
        header, rows = read_table(file.filename or "", await file.read())
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception:
        raise HTTPException(400, "That file could not be read. Check that it is a normal CSV or Excel sheet.")
    now = time.time()
    for k in [k for k, v in UPLOADS.items() if now - v["ts"] > 1800]:
        UPLOADS.pop(k)
    uid = uuid.uuid4().hex
    UPLOADS[uid] = {"rows": rows, "ts": now}
    return {"upload_id": uid, "columns": header, "rows": rows[:8], "total": len(rows), "suggested": suggest(header)}


class ImportIn(BaseModel):
    upload_id: str
    mapping: dict[str, str]
    default_market: str = ""
    analyze: bool = False


@router.post("/api/leads/upload/import")
async def do_import(body: ImportIn, _: User = Depends(current_user), db: Session = Depends(get_db)):
    up = UPLOADS.get(body.upload_id)
    if not up:
        raise HTTPException(400, "This upload expired. Choose the file again.")
    m = body.mapping
    if not m.get("business_name"):
        raise HTTPException(400, "Choose which column holds the business name.")
    if body.default_market and not db.query(Market).filter(Market.code == body.default_market).first():
        raise HTTPException(400, "Choose a market from the list.")
    dnc = {d.phone for d in db.query(DNC).all()}
    seen_phone, seen_dom = set(), set()
    res = {"added": 0, "duplicates": 0, "invalid": 0, "do_not_call": 0, "problems": []}
    new_ids = []

    def problem(i, name, why, key):
        res[key] += 1
        if len(res["problems"]) < 100:
            res["problems"].append({"row": i + 2, "business": name[:60], "reason": why})

    for i, row in enumerate(up["rows"]):
        g = lambda f: (row.get(m.get(f, ""), "") or "").strip() if m.get(f) else ""
        name = g("business_name")
        if len(name) < 2:
            problem(i, name, "Missing business name", "invalid")
            continue
        mk = COUNTRY_CODE.get(g("market").lower(), g("market").upper()[:2]) if g("market") else ""
        mk = mk if mk in {"AE", "SA", "GB", "US", "AU"} else ""
        raw_phone = g("phone")
        phone = normalize(raw_phone, mk or body.default_market)
        if raw_phone and not phone:
            problem(i, name, f"Phone number not valid: {raw_phone[:30]}. Use the country code, like +971500000000.", "invalid")
            continue
        site = g("website")
        dom = discovery.domain_of(site)
        if not phone and not dom:
            problem(i, name, "Needs a phone number or a website", "invalid")
            continue
        if phone and phone in dnc:
            problem(i, name, "On the Do Not Call list", "do_not_call")
            continue
        if (phone and (phone in seen_phone or db.query(Lead).filter(Lead.phone == phone).first())) or \
           (dom and (dom in seen_dom or db.query(Lead).filter(Lead.domain == dom).first())):
            problem(i, name, "Already in Leads, or repeated in this file", "duplicates")
            continue
        market = mk or (market_of(phone) if phone else "") or body.default_market
        lead = Lead(business_name=name[:190], contact_name=g("contact_name")[:120], phone=phone or "", email=g("email")[:190],
                    website=site[:250], domain=dom, city=g("city")[:80], market_code=market or None,
                    industry=g("industry")[:120], notes=g("notes"), source="upload", status="New")
        db.add(lead)
        db.flush()
        if phone:
            seen_phone.add(phone)
        if dom:
            seen_dom.add(dom)
        res["added"] += 1
        if site:
            new_ids.append(lead.id)
    db.commit()
    UPLOADS.pop(body.upload_id, None)
    res["analysis_run"] = None
    if body.analyze and new_ids:
        if not llm.configured():
            res["analysis_note"] = "Leads were added, but the language model key is not set, so websites were not analyzed."
        else:
            ids = new_ids[:100]
            run = DiscoveryRun(mode="analyze", params={"business": f"{len(ids)} uploaded leads"}, status="running", note="Starting")
            db.add(run)
            db.commit()
            discovery.spawn(discovery.run_analyze_many(run.id, ids))
            res["analysis_run"] = run.id
    audit(db, "leads_uploaded", f"added {res['added']}")
    return res


class BulkIn(BaseModel):
    ids: list[int]
    action: str          # status | delete | tag
    value: str = ""


@router.post("/api/leads/bulk")
async def bulk(body: BulkIn, _: User = Depends(current_user), db: Session = Depends(get_db)):
    if not body.ids:
        raise HTTPException(400, "Select at least one lead.")
    q = db.query(Lead).filter(Lead.id.in_(body.ids[:1000]))
    n = q.count()
    if body.action == "status":
        if body.value not in STATUSES:
            raise HTTPException(400, "Unknown status")
        q.update({Lead.status: body.value}, synchronize_session=False)
    elif body.action == "tag":
        tag = re.sub(r"[^\w -]", "", body.value).strip()[:30]
        if not tag:
            raise HTTPException(400, "Type a tag first.")
        for l in q.all():
            tags = [t for t in (l.tags or "").split(",") if t]
            if tag not in tags:
                l.tags = ",".join(tags + [tag])[:300]
    elif body.action == "delete":
        db.query(CallTask).filter(CallTask.lead_id.in_(body.ids), CallTask.status == "pending").update(
            {CallTask.status: "cancelled", CallTask.note: "Lead deleted"}, synchronize_session=False)
        q.delete(synchronize_session=False)
    elif body.action == "analyze":
        if not llm.configured():
            raise HTTPException(400, "Add your language model key in Settings > Integrations first.")
        todo = [l.id for l in q.all() if l.website and l.source != "demo"][:100]
        if not todo:
            raise HTTPException(400, "None of the selected leads has a website to analyze.")
        run = DiscoveryRun(mode="analyze", params={"business": f"{len(todo)} selected leads"}, status="running", note="Starting")
        db.add(run)
        db.commit()
        discovery.spawn(discovery.run_analyze_many(run.id, todo))
        audit(db, "leads_bulk", f"analyze {len(todo)}")
        return {"changed": len(todo), "run_id": run.id}
    else:
        raise HTTPException(400, "Unknown action")
    db.commit()
    audit(db, "leads_bulk", f"{body.action} {n}")
    return {"changed": n}


# ---------------- Do Not Call ----------------
class DncIn(BaseModel):
    phone: str
    reason: str = ""


def add_dnc(db: Session, phone: str, reason: str):
    """Adds to the list, marks matching leads, cancels their pending calls. Safe to call twice."""
    if not db.query(DNC).filter(DNC.phone == phone).first():
        db.add(DNC(phone=phone, reason=reason[:200]))
    ids = [l.id for l in db.query(Lead).filter(Lead.phone == phone).all()]
    if ids:
        db.query(Lead).filter(Lead.id.in_(ids)).update({Lead.status: "Do Not Call"}, synchronize_session=False)
        db.query(CallTask).filter(CallTask.lead_id.in_(ids), CallTask.status == "pending").update(
            {CallTask.status: "cancelled", CallTask.note: "Do Not Call"}, synchronize_session=False)
    db.commit()


@router.get("/api/dnc")
async def list_dnc(_: User = Depends(current_user), db: Session = Depends(get_db)):
    return [{"id": d.id, "phone": d.phone, "reason": d.reason, "added_at": d.added_at.isoformat()}
            for d in db.query(DNC).order_by(DNC.id.desc()).limit(1000).all()]


@router.post("/api/dnc")
async def post_dnc(body: DncIn, _: User = Depends(current_user), db: Session = Depends(get_db)):
    phone = normalize(body.phone)
    if not phone:
        raise HTTPException(400, "Use international format like +971500000000.")
    add_dnc(db, phone, body.reason or "Added by owner")
    audit(db, "dnc_added", phone)
    return {"ok": True}


@router.delete("/api/dnc/{did}")
async def delete_dnc(did: int, _: User = Depends(current_user), db: Session = Depends(get_db)):
    d = db.get(DNC, did)
    if not d:
        raise HTTPException(404, "Not found")
    db.delete(d)
    db.commit()
    audit(db, "dnc_removed", d.phone)
    return {"ok": True}
