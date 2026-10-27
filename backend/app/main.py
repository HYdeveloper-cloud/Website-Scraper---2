import asyncio
import os
import re
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from . import config, discovery, llm, models, places
from .netsafe import safe_public_url
from .db import Base, SessionLocal, engine, get_db
from .demo import DEMO_LEADS
from .models import AuditLog, DiscoveryRun, Lead, Market, Service, Setting, User
from .security import (check_throttle, clear_fails, current_user, hash_password, make_token,
                       record_fail, verify_password)
from .deps import audit, get_setting
from .seed import DEFAULT_THEME, seed_all
from . import analytics, calling, keystore, leads_io, visuals
from .settings_validate import validate, validate_market

STATUSES = ["New", "Queued", "Contacted", "Interested", "Meeting Booked", "Follow-up Pending",
            "Not Interested", "Do Not Call", "Wrong Number", "Unreachable", "Won", "Lost"]
HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
PHONE = re.compile(r"^\+[1-9]\d{7,14}$")

app = FastAPI(title="HY Developer Sales Engine")
app.include_router(leads_io.router)
app.include_router(calling.router)
app.include_router(analytics.router)
app.include_router(visuals.router)
app.add_middleware(CORSMiddleware, allow_origins=[config.FRONTEND_ORIGIN],
                   allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
def startup():
    Base.metadata.create_all(engine)
    add_missing_columns()
    with SessionLocal() as db:
        seed_all(db)
        keystore.load_into_env(db)
        for r in db.query(DiscoveryRun).filter(DiscoveryRun.status == "running").all():
            r.status, r.note = "interrupted", "The backend was restarted while this was running"
        db.commit()
    if os.getenv("DISABLE_SCHEDULER") != "1":
        asyncio.create_task(calling.scheduler_loop())


def add_missing_columns():
    """Adds Stage B columns to a Stage A database without touching existing data."""
    from sqlalchemy import inspect, text
    have = {c["name"] for c in inspect(engine).get_columns("leads")}
    want = {"analysis": "JSON", "checks": "JSON", "analyzed_at": "DATETIME", "rating": "FLOAT", "run_id": "INT", "tags": "VARCHAR(300)", "reviews": "INT", "fit_band": "VARCHAR(12)", "fit_conf": "VARCHAR(8)"}
    with engine.begin() as cx:
        for name, typ in want.items():
            if name not in have:
                cx.execute(text(f"ALTER TABLE leads ADD COLUMN {name} {typ}"))


# ---------------- auth ----------------
class LoginIn(BaseModel):
    email: str
    password: str


class PasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=10)


@app.get("/api/health")
def health():
    return {"app": "hy-sales-engine"}


class SetupIn(BaseModel):
    email: str
    password: str = Field(min_length=10)


@app.get("/api/auth/setup-status")
def setup_status(db: Session = Depends(get_db)):
    return {"needs_setup": db.query(User).count() == 0}


@app.post("/api/auth/setup")
def setup(body: SetupIn, db: Session = Depends(get_db)):
    """Creates the one owner account. Only works while no account exists."""
    if db.query(User).count() > 0:
        raise HTTPException(409, "The owner account already exists. Sign in instead.")
    email = body.email.strip().lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise HTTPException(400, "Enter a valid email address.")
    user = User(email=email, password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    audit(db, "owner_created", email)
    return {"token": make_token(user.id), "email": email}


@app.get("/api/public/theme")
def public_theme(db: Session = Depends(get_db)):
    return {"theme": get_setting(db, "theme") or DEFAULT_THEME,
            "company_name": get_setting(db, "general").get("company_name", "HY Developer")}


@app.post("/api/auth/login")
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "local"
    check_throttle(ip)
    user = db.query(User).filter(User.email == body.email.strip().lower()).first()
    if not user or not verify_password(body.password, user.password_hash):
        record_fail(ip)
        audit(db, "login_failed", body.email[:100])
        raise HTTPException(401, "Email or password is wrong.")
    clear_fails(ip)
    audit(db, "login", user.email)
    return {"token": make_token(user.id), "email": user.email}


@app.get("/api/auth/me")
def me(user: User = Depends(current_user)):
    return {"email": user.email}


@app.post("/api/auth/change-password")
def change_password(body: PasswordIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, "Current password is wrong.")
    user.password_hash = hash_password(body.new_password)
    db.commit()
    audit(db, "password_changed", user.email)
    return {"ok": True}


# ---------------- settings ----------------
@app.get("/api/settings")
def all_settings(_: User = Depends(current_user), db: Session = Depends(get_db)):
    return {s.key: s.value for s in db.query(Setting).all() if s.key != "secrets"}


@app.put("/api/settings/{key}")
def save_setting(key: str, body: dict, _: User = Depends(current_user), db: Session = Depends(get_db)):
    if key == "theme":
        clean = {}
        for k in DEFAULT_THEME:
            v = str(body.get(k, DEFAULT_THEME[k]))
            if not HEX.match(v):
                raise HTTPException(400, f"{k} must be a hex color like #330908.")
            clean[k] = v.upper()
        body = clean
    elif key == "general":
        body = {"company_name": str(body.get("company_name", "")).strip()[:80] or "HY Developer",
                "timezone": str(body.get("timezone", "Asia/Karachi"))[:60],
                "currency": str(body.get("currency", "USD")).upper()[:3]}
    elif key == "integrations":
        nums = [str(n).replace(" ", "") for n in body.get("phone_numbers", []) if str(n).strip()]
        bad = [n for n in nums if not PHONE.match(n)]
        if bad:
            raise HTTPException(400, f"Use international format like +971500000000. Check: {', '.join(bad)}")
        body = {"phone_numbers": nums}
    else:
        body = validate(key, body, db)
    row = db.get(Setting, key)
    if row:
        row.value = body
    else:
        db.add(Setting(key=key, value=body))
    db.commit()
    audit(db, "settings_saved", key)
    return body


class KeysIn(BaseModel):
    LLM_API_KEY: str = ""
    GOOGLE_PLACES_API_KEY: str = ""
    RETELL_API_KEY: str = ""
    LLM_BASE_URL: str = ""
    LLM_MODEL: str = ""
    clear: list[str] = []


@app.get("/api/keys")
def get_keys(_: User = Depends(current_user)):
    return keystore.status()


@app.put("/api/keys")
def put_keys(body: KeysIn, _: User = Depends(current_user), db: Session = Depends(get_db)):
    try:
        keystore.save(db, body.model_dump(exclude={"clear"}), body.clear)
    except ValueError as e:
        raise HTTPException(400, str(e))
    audit(db, "keys_saved", "keys changed")
    return keystore.status()


@app.post("/api/keys/test/{service}")
async def test_key(service: str, _: User = Depends(current_user)):
    """Makes one tiny real request so you know the key works."""
    try:
        if service == "llm":
            await llm.complete_json('Reply with the JSON {"ok": true}', "ping", 50)
        elif service == "places":
            await places.search("cafe in Dubai", "AE", 1)
        elif service == "retell":
            from . import retell
            await retell.ping()
        else:
            raise HTTPException(404, "Unknown service")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"The test failed: {e}")
    return {"ok": True}


@app.post("/api/scoring/rescore")
def rescore_all(_: User = Depends(current_user), db: Session = Depends(get_db)):
    """Re-scores every analyzed lead with your current scoring choices. No new crawling and no AI calls: it only redoes the maths."""
    from . import scoring
    cfg, n = discovery.load_cfg(db), 0
    for l in db.query(Lead).filter(Lead.analysis.isnot(None)).all():
        a = l.analysis or {}
        old = a.get("report")
        if not old or old.get("method") != "v3-evidence-first":
            continue
        inp = old.get("inputs") or {}
        new = scoring.build_report(old["gaps"], old.get("already_has", []), old.get("buying_signals", []), a.get("checks") or {}, discovery.lead_ctx(l, cfg),
                                   a.get("industry", ""), a.get("contact") or {}, inp.get("pages_read", 0), inp.get("dropped", 0), inp.get("listing_only", False), cfg)
        new["checked_at"] = old.get("checked_at", new["checked_at"])
        a = dict(a)
        a["report"], a["fit_score"] = new, new["score"]
        l.analysis, l.fit_score, l.fit_band, l.fit_conf = a, new["score"], new["band"], new["confidence"]
        n += 1
    db.commit()
    audit(db, "leads_rescored", str(n))
    return {"rescored": n}


@app.get("/api/status")
def status(_: User = Depends(current_user)):
    import os
    return {"database": True,
            "llm_configured": bool(os.getenv("LLM_API_KEY")),
            "retell_configured": bool(os.getenv("RETELL_API_KEY")),
            "places_configured": places.configured()}


# ---------------- reference data ----------------
@app.get("/api/markets")
def markets(_: User = Depends(current_user), db: Session = Depends(get_db)):
    return [{"code": m.code, "name": m.name, "timezone": m.timezone, "priority": m.priority,
             "languages": m.languages, "weekend_days": m.weekend_days, "active": m.active,
             "call_start": m.call_start, "call_end": m.call_end} for m in db.query(Market).all()]


@app.put("/api/markets/{code}")
def edit_market(code: str, body: dict, _: User = Depends(current_user), db: Session = Depends(get_db)):
    m = db.query(Market).filter(Market.code == code).first()
    if not m:
        raise HTTPException(404, "Market not found")
    v = validate_market(body)
    m.timezone, m.call_start, m.call_end, m.weekend_days, m.active = v["timezone"], v["call_start"], v["call_end"], v["weekend_days"], v["active"]
    db.commit()
    audit(db, "market_edited", code)
    return {"ok": True}


@app.get("/api/services")
def services(_: User = Depends(current_user), db: Session = Depends(get_db)):
    return [{"id": s.id, "name": s.name, "pain_points": s.pain_points, "signals": s.signals, "pitch": s.pitch}
            for s in db.query(Service).order_by(Service.sort).all()]


# ---------------- leads ----------------
class LeadIn(BaseModel):
    business_name: str = Field(min_length=2, max_length=190)
    contact_name: str = ""
    phone: str = ""
    email: str = ""
    website: str = ""
    city: str = ""
    market_code: str = ""
    industry: str = ""
    notes: str = ""


domain_of = discovery.domain_of


def lead_json(l: Lead) -> dict:
    return {"id": l.id, "business_name": l.business_name, "contact_name": l.contact_name, "phone": l.phone,
            "email": l.email, "website": l.website, "city": l.city, "market_code": l.market_code,
            "industry": l.industry, "source": l.source, "fit_score": l.fit_score, "status": l.status,
            "pain_point": l.pain_point, "hy_solution": l.hy_solution, "rating": l.rating, "reviews": l.reviews,
            "fit_band": l.fit_band or "", "fit_conf": l.fit_conf or "",
            "tags": l.tags or "", "has_analysis": bool(l.analysis), "analyzed_at": l.analyzed_at.isoformat() if l.analyzed_at else None,
            "created_at": l.created_at.isoformat()}


@app.get("/api/leads")
def list_leads(market: str = "", status: str = "", q: str = "",
               _: User = Depends(current_user), db: Session = Depends(get_db)):
    query = db.query(Lead)
    if market:
        query = query.filter(Lead.market_code == market)
    if status:
        query = query.filter(Lead.status == status)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(Lead.business_name.like(like) | Lead.phone.like(like) | Lead.city.like(like))
    rows = query.order_by(Lead.fit_score.desc(), Lead.id.desc()).limit(500).all()
    return {"leads": [lead_json(l) for l in rows], "statuses": STATUSES,
            "total": db.query(Lead).count(), "demo_count": db.query(Lead).filter(Lead.source == "demo").count()}


@app.post("/api/leads")
def add_lead(body: LeadIn, _: User = Depends(current_user), db: Session = Depends(get_db)):
    if body.market_code and not db.query(Market).filter(Market.code == body.market_code).first():
        raise HTTPException(400, "Choose a market from the list.")
    phone = re.sub(r"[\s()-]", "", body.phone)
    if phone and not re.match(r"^\+?\d{7,15}$", phone):
        raise HTTPException(400, "Phone number looks wrong. Use digits, with the country code, like +971500000000.")
    dom = domain_of(body.website)
    if phone and db.query(Lead).filter(Lead.phone == phone).first():
        raise HTTPException(409, "A lead with this phone number already exists.")
    if dom and db.query(Lead).filter(Lead.domain == dom).first():
        raise HTTPException(409, "A lead with this website already exists.")
    lead = Lead(business_name=body.business_name.strip(), contact_name=body.contact_name, phone=phone,
                email=body.email, website=body.website, domain=dom, city=body.city,
                market_code=body.market_code, industry=body.industry, notes=body.notes, source="manual")
    db.add(lead)
    db.commit()
    return lead_json(lead)


class StatusIn(BaseModel):
    status: str


@app.put("/api/leads/{lead_id}/status")
def set_status(lead_id: int, body: StatusIn, _: User = Depends(current_user), db: Session = Depends(get_db)):
    lead = db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    if body.status not in STATUSES:
        raise HTTPException(400, "Unknown status")
    lead.status = body.status
    db.commit()
    return lead_json(lead)


@app.post("/api/leads/demo")
def load_demo(_: User = Depends(current_user), db: Session = Depends(get_db)):
    if db.query(Lead).filter(Lead.source == "demo").count():
        raise HTTPException(409, "Sample leads are already loaded.")
    for i, (name, city, mk, ind, site, fit, st, pain, sol) in enumerate(DEMO_LEADS):
        db.add(Lead(business_name=name, city=city, market_code=mk, industry=ind, website=site,
                    domain=domain_of(site), phone=f"+0000000{i:04d}", fit_score=fit, status=st,
                    pain_point=pain, hy_solution=sol, source="demo"))
    db.commit()
    return {"loaded": len(DEMO_LEADS)}


@app.delete("/api/leads/demo")
def clear_demo(_: User = Depends(current_user), db: Session = Depends(get_db)):
    n = db.query(Lead).filter(Lead.source == "demo").delete()
    db.commit()
    return {"removed": n}


# ---------------- Stage B: services editor ----------------
class ServiceIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    pitch: str = ""
    pain_points: list[str] = []
    signals: list[str] = []


def clean_list(v: list[str]) -> list[str]:
    return [x.strip()[:200] for x in v if x.strip()][:20]


@app.post("/api/services")
def add_service(body: ServiceIn, _: User = Depends(current_user), db: Session = Depends(get_db)):
    nxt = (db.query(Service).count())
    s = Service(name=body.name.strip(), pitch=body.pitch, pain_points=clean_list(body.pain_points),
                signals=clean_list(body.signals), sort=nxt)
    db.add(s)
    db.commit()
    return {"id": s.id}


@app.put("/api/services/{sid}")
def edit_service(sid: int, body: ServiceIn, _: User = Depends(current_user), db: Session = Depends(get_db)):
    s = db.get(Service, sid)
    if not s:
        raise HTTPException(404, "Service not found")
    s.name, s.pitch = body.name.strip(), body.pitch
    s.pain_points, s.signals = clean_list(body.pain_points), clean_list(body.signals)
    db.commit()
    audit(db, "service_edited", s.name)
    return {"ok": True}


@app.delete("/api/services/{sid}")
def delete_service(sid: int, _: User = Depends(current_user), db: Session = Depends(get_db)):
    if db.query(Service).count() <= 1:
        raise HTTPException(400, "Keep at least one service. The first service is used when a business has no website.")
    s = db.get(Service, sid)
    if not s:
        raise HTTPException(404, "Service not found")
    db.delete(s)
    db.commit()
    return {"ok": True}


# ---------------- Stage B: lead detail and discovery ----------------
@app.get("/api/leads/{lead_id}")
def lead_detail(lead_id: int, _: User = Depends(current_user), db: Session = Depends(get_db)):
    l = db.get(Lead, lead_id)
    if not l:
        raise HTTPException(404, "Lead not found")
    from .models import Call
    calls = [calling.call_json(db, c) for c in db.query(Call).filter(Call.lead_id == lead_id).order_by(Call.id.desc()).limit(20).all()]
    return {**lead_json(l), "analysis": l.analysis, "notes": l.notes, "calls": calls}


def run_json(r: DiscoveryRun) -> dict:
    return {"id": r.id, "mode": r.mode, "params": r.params, "status": r.status, "found": r.found,
            "added": r.added, "updated": r.updated, "skipped": r.skipped, "filtered": r.filtered,
            "failed": r.failed, "note": r.note, "errors": r.errors or [],
            "created_at": r.created_at.isoformat(), "finished_at": r.finished_at.isoformat() if r.finished_at else None}


def new_run(db: Session, mode: str, params: dict) -> DiscoveryRun:
    run = DiscoveryRun(mode=mode, params=params, status="running", note="Starting")
    db.add(run)
    db.commit()
    return run


def need_llm():
    if not llm.configured():
        raise HTTPException(400, "Add your language model key in Settings > Integrations first.")


class LinkIn(BaseModel):
    url: str
    market_code: str = ""


class AutoIn(BaseModel):
    niche: str = Field(min_length=2, max_length=80)
    city: str = Field(min_length=2, max_length=80)
    market_code: str
    limit: int = Field(20, ge=1, le=60)
    require_website: bool = False
    min_rating: float = Field(0, ge=0, le=5)
    min_fit: int = Field(0, ge=0, le=100)


@app.post("/api/discovery/link")
async def discover_link(body: LinkIn, _: User = Depends(current_user), db: Session = Depends(get_db)):
    need_llm()
    try:
        url = safe_public_url(body.url)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if body.market_code and not db.query(Market).filter(Market.code == body.market_code).first():
        raise HTTPException(400, "Choose a market from the list.")
    run = new_run(db, "link", {"url": url, "market_code": body.market_code})
    discovery.spawn(discovery.run_link(run.id, url, body.market_code))
    return run_json(run)


@app.post("/api/discovery/auto")
async def discover_auto(body: AutoIn, _: User = Depends(current_user), db: Session = Depends(get_db)):
    need_llm()
    if not places.configured():
        raise HTTPException(400, "Add your Google Places key in Settings > Integrations first.")
    if not db.query(Market).filter(Market.code == body.market_code).first():
        raise HTTPException(400, "Choose a market from the list.")
    params = body.model_dump()
    run = new_run(db, "auto", params)
    discovery.spawn(discovery.run_auto(run.id, params))
    return run_json(run)


@app.post("/api/leads/{lead_id}/analyze")
async def analyze_lead(lead_id: int, _: User = Depends(current_user), db: Session = Depends(get_db)):
    need_llm()
    l = db.get(Lead, lead_id)
    if not l:
        raise HTTPException(404, "Lead not found")
    if not l.website:
        raise HTTPException(400, "This lead has no website to analyze.")
    run = new_run(db, "analyze", {"lead_id": lead_id, "business": l.business_name})
    discovery.spawn(discovery.run_analyze(run.id, lead_id))
    return run_json(run)


@app.get("/api/discovery/runs")
def list_runs(_: User = Depends(current_user), db: Session = Depends(get_db)):
    return [run_json(r) for r in db.query(DiscoveryRun).order_by(DiscoveryRun.id.desc()).limit(30).all()]


# ---------------- the screens (packaged app) ----------------
def _ui_dir():
    import sys
    from pathlib import Path
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent)) / "ui"


if _ui_dir().exists():                 # served from this same program, so no separate web server is needed
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=str(_ui_dir()), html=True), name="ui")
