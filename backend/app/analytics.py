"""Stage E: dashboard analytics, client acquisition (deals), CSV reports."""
import csv
import io
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from . import outcomes
from .db import get_db
from .deps import audit, get_setting
from .models import AuditLog, Call, CallTask, Deal, Lead, Market, User
from .security import current_user

router = APIRouter()
POSITIVE = {"interested", "meeting_booked", "callback_requested"}
DENIAL = {"not_interested", "do_not_call"}
NOT_CONNECTED = {"short_call", "no_answer", "voicemail"}


def now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def real_leads(db: Session):
    return db.query(Lead).filter(Lead.source != "demo")


@router.get("/api/dashboard")
async def dashboard(days: int = 30, _: User = Depends(current_user), db: Session = Depends(get_db)):
    days = days if days in (1, 7, 30, 90) else 30
    since, cs = now() - timedelta(days=days), get_setting(db, "calling")
    calls = db.query(Call).filter(Call.created_at >= since, Call.lead_id.isnot(None)).all()
    done = [c for c in calls if c.outcome]
    connected = [c for c in done if c.outcome not in NOT_CONNECTED]
    cnt = Counter(c.outcome for c in done)
    won = db.query(Deal).filter(Deal.stage == "Won", Deal.closed_at >= since).all()
    leads = real_leads(db).filter(Lead.created_at >= since).all()
    pos, den = sum(cnt[o] for o in POSITIVE), sum(cnt[o] for o in DENIAL)
    mins = sum(c.duration_s or 0 for c in calls) / 60
    per_day = Counter((now() - c.created_at).days for c in db.query(Call).filter(Call.created_at >= now() - timedelta(days=14), Call.lead_id.isnot(None)).all())
    fu = db.query(CallTask).filter(CallTask.kind == "followup", CallTask.created_at >= since)
    markets = db.query(Market).all()
    by_market = [[m.name, sum(1 for l in leads if l.market_code == m.code),
                  sum(1 for c in calls if (lead := db.get(Lead, c.lead_id)) and lead.market_code == m.code),
                  sum(1 for c in done if c.outcome == "meeting_booked" and (lead := db.get(Lead, c.lead_id)) and lead.market_code == m.code)] for m in markets]
    pains = Counter(l.pain_point for l in leads if l.analysis and l.pain_point).most_common(5)
    allc = db.query(Call).filter(Call.lead_id.isnot(None), Call.outcome.isnot(None)).all()
    contacted = {c.lead_id for c in allc}
    return {
        "days": days, "empty": not (db.query(Lead).count() or calls),
        "kpis": {"discovered": len(leads), "calls": len(calls), "connected": len(connected), "meetings": cnt["meeting_booked"],
                 "won": len(won), "revenue": sum(d.final_value or 0 for d in won)},
        "calls_per_day": [per_day.get(i, 0) for i in range(13, -1, -1)],
        "outcomes": [[outcomes.LABEL[o], cnt[o]] for o in outcomes.LABEL if cnt[o]],
        "followups": {"scheduled": fu.count(), "completed": fu.filter(CallTask.status == "done").count(),
                      "pending": db.query(CallTask).filter(CallTask.kind == "followup", CallTask.status == "pending").count(),
                      "converted": sum(1 for c in done if c.attempt >= 1 and c.outcome in POSITIVE)},
        "success_rate": round(100 * pos / len(connected)) if connected else 0,
        "denial_rate": round(100 * den / len(connected)) if connected else 0,
        "short_calls": cnt["short_call"], "avg_duration": round(sum(c.duration_s for c in connected) / len(connected)) if connected else 0,
        "minutes": round(mins, 1), "cost_estimate": round(mins * cs["cost_per_minute"], 2),
        "by_market": by_market, "top_pains": [list(p) for p in pains],
        "by_band": by_band(db),
        "pipeline": [["Leads found", real_leads(db).count()], ["Contacted", len(contacted)],
                     ["Interested or better", len({c.lead_id for c in allc if c.outcome in POSITIVE})],
                     ["Meeting booked", len({c.lead_id for c in allc if c.outcome == "meeting_booked"})],
                     ["Proposal submitted", db.query(Deal).filter(Deal.proposal_date.isnot(None)).count()],
                     ["Won", db.query(Deal).filter(Deal.stage == "Won").count()]],
    }


def by_band(db: Session) -> list[dict]:
    """Outcomes grouped by priority band, so the scoring can be judged by real results before it is changed."""
    by_lead = defaultdict(list)
    for c in db.query(Call).filter(Call.lead_id.isnot(None), Call.outcome.isnot(None)).all():
        by_lead[c.lead_id].append(c.outcome)
    won = {d.lead_id for d in db.query(Deal).filter(Deal.stage == "Won").all()}
    rows = []
    for band in ("High", "Medium", "Low", ""):
        ls = [l for l in real_leads(db).all() if (l.fit_band or "") == band or (band == "" and (l.fit_band or "") not in ("High", "Medium", "Low"))]
        outs = [by_lead.get(l.id, []) for l in ls]
        rows.append({"band": band or "Not scored yet", "leads": len(ls), "called": sum(1 for o in outs if o),
                     "connected": sum(1 for o in outs if any(x not in NOT_CONNECTED for x in o)),
                     "positive": sum(1 for o in outs if any(x in POSITIVE for x in o)),
                     "meetings": sum(1 for o in outs if "meeting_booked" in o), "won": sum(1 for l in ls if l.id in won)})
    return rows


# ---------------- deals ----------------
def deal_json(db: Session, d: Deal) -> dict:
    l = db.get(Lead, d.lead_id) if d.lead_id else None
    f = lambda x: x.date().isoformat() if x else None
    return {"id": d.id, "lead_id": d.lead_id, "business": l.business_name if l else "(deleted)", "market": l.market_code if l else "",
            "source": l.source if l else "", "service": d.service, "stage": d.stage, "value": d.value or 0, "final_value": d.final_value,
            "proposal_date": f(d.proposal_date), "expected_close": f(d.expected_close), "closed_at": f(d.closed_at),
            "lost_reason": d.lost_reason, "notes": d.notes, "created_at": f(d.created_at)}


def parse_date(v):
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v)[:10])
    except ValueError:
        raise HTTPException(400, "Dates must look like 2026-10-31.")


class DealIn(BaseModel):
    lead_id: int
    service: str = ""
    value: float = 0
    stage: str = ""


@router.post("/api/deals")
async def new_deal(body: DealIn, _: User = Depends(current_user), db: Session = Depends(get_db)):
    lead = db.get(Lead, body.lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    if db.query(Deal).filter(Deal.lead_id == lead.id, Deal.stage.notin_(["Won", "Lost"])).first():
        raise HTTPException(409, "This lead already has an open deal.")
    stages = get_setting(db, "acquisition")["stages"]
    stage = body.stage if body.stage in stages[:-2] else stages[0]
    d = Deal(lead_id=lead.id, service=body.service or lead.hy_solution, stage=stage, value=max(body.value, 0))
    db.add(d)
    db.commit()
    return deal_json(db, d)


@router.put("/api/deals/{did}")
async def edit_deal(did: int, body: dict, _: User = Depends(current_user), db: Session = Depends(get_db)):
    d = db.get(Deal, did)
    if not d:
        raise HTTPException(404, "Deal not found")
    stages = get_setting(db, "acquisition")["stages"]
    lead = db.get(Lead, d.lead_id) if d.lead_id else None
    for k in ("service", "notes"):
        if k in body:
            setattr(d, k, str(body[k] or "")[:2000])
    if "value" in body:
        d.value = max(float(body["value"] or 0), 0)
    if "proposal_date" in body:
        d.proposal_date = parse_date(body["proposal_date"])
    if "expected_close" in body:
        d.expected_close = parse_date(body["expected_close"])
    if body.get("lost_reason") is not None:
        d.lost_reason = str(body["lost_reason"])[:200]
    if "final_value" in body and body["final_value"] not in (None, ""):
        d.final_value = max(float(body["final_value"]), 0)
    st = body.get("stage")
    if st and st != d.stage:
        if st not in stages:
            raise HTTPException(400, "Unknown stage")
        if st == "Won":
            fv = d.final_value if d.final_value else d.value
            if not fv:
                raise HTTPException(400, "Enter the final deal value before marking this deal Won.")
            d.final_value, d.closed_at = fv, now()
            if lead:
                lead.status = "Won"
        elif st == "Lost":
            if not (d.lost_reason or "").strip():
                raise HTTPException(400, "Enter why the deal was lost.")
            d.closed_at = now()
            if lead:
                lead.status = "Lost"
        else:
            d.closed_at = None
            if st.lower().startswith("proposal") and not d.proposal_date:
                d.proposal_date = now()
        d.stage = st
    db.commit()
    audit(db, "deal_updated", f"{did} {d.stage}")
    return deal_json(db, d)


@router.delete("/api/deals/{did}")
async def del_deal(did: int, _: User = Depends(current_user), db: Session = Depends(get_db)):
    d = db.get(Deal, did)
    if d:
        db.delete(d)
        db.commit()
    return {"ok": True}


@router.get("/api/acquisition")
async def acquisition(_: User = Depends(current_user), db: Session = Depends(get_db)):
    ac, cs = get_setting(db, "acquisition"), get_setting(db, "calling")
    deals = [deal_json(db, d) for d in db.query(Deal).order_by(Deal.id.desc()).all()]
    won = [d for d in deals if d["stage"] == "Won"]
    lost = [d for d in deals if d["stage"] == "Lost"]
    rev = sum(d["final_value"] or 0 for d in won)
    by_month = defaultdict(float)
    for d in won:
        by_month[d["closed_at"][:7]] += d["final_value"] or 0
    months = [(now().replace(day=1) - timedelta(days=31 * i)).strftime("%Y-%m") for i in range(5, -1, -1)]
    svc, src = defaultdict(float), defaultdict(float)
    for d in won:
        svc[d["service"] or "Not set"] += d["final_value"] or 0
        src[d["source"] or "Not set"] += d["final_value"] or 0
    cycles = [(datetime.fromisoformat(d["closed_at"]) - datetime.fromisoformat(d["created_at"])).days for d in won if d["closed_at"]]
    spend = (db.query(func.coalesce(func.sum(Call.duration_s), 0)).scalar() or 0) / 60 * cs["cost_per_minute"]
    this_month = by_month.get(now().strftime("%Y-%m"), 0)
    return {"stages": ac["stages"], "deals": deals, "target": ac["monthly_target"],
            "metrics": {"deals_won": len(won), "deals_lost": len(lost), "revenue": rev, "revenue_this_month": this_month,
                        "proposals": sum(1 for d in deals if d["proposal_date"]), "win_rate": round(100 * len(won) / (len(won) + len(lost))) if won or lost else 0,
                        "avg_deal": round(rev / len(won)) if won else 0, "avg_cycle_days": round(sum(cycles) / len(cycles)) if cycles else 0,
                        "cost_per_client": round(spend / len(won), 2) if won else None, "call_spend_estimate": round(spend, 2),
                        "target_progress": round(100 * this_month / ac["monthly_target"]) if ac["monthly_target"] else None},
            "revenue_by_month": [[m, by_month.get(m, 0)] for m in months],
            "by_service": sorted(svc.items(), key=lambda x: -x[1]), "by_source": sorted(src.items(), key=lambda x: -x[1]),
            "lost_reasons": Counter(d["lost_reason"] or "No reason" for d in lost).most_common()}


# ---------------- CSV reports and audit ----------------
def csv_response(name: str, header: list[str], rows) -> Response:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    for r in rows:
        w.writerow([("'" + str(v) if isinstance(v, str) and v[:1] in "=+-@" and name != "phones" else v) for v in r])
    return Response("\ufeff" + buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/api/reports/leads.csv")
async def rep_leads(_: User = Depends(current_user), db: Session = Depends(get_db)):
    return csv_response("leads.csv", ["Business", "Contact", "Phone", "Email", "Website", "City", "Market", "Industry", "Source", "Fit score", "Status", "Pain point", "Recommended service", "Tags", "Added"],
                        [[l.business_name, l.contact_name, l.phone, l.email, l.website, l.city, l.market_code, l.industry, l.source, l.fit_score, l.status, l.pain_point, l.hy_solution, l.tags, l.created_at.date()]
                         for l in real_leads(db).order_by(Lead.id).all()])


@router.get("/api/reports/calls.csv")
async def rep_calls(_: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = []
    for c in db.query(Call).order_by(Call.id).all():
        l = db.get(Lead, c.lead_id) if c.lead_id else None
        rows.append([c.created_at.isoformat(timespec="seconds"), l.business_name if l else "Test call", c.to_number, c.kind, c.attempt, c.duration_s,
                     outcomes.LABEL.get(c.outcome, c.outcome or ""), c.disconnection_reason, c.summary, c.meeting_when])
    return csv_response("calls.csv", ["Time (UTC)", "Business", "Number", "Type", "Attempt", "Seconds", "Outcome", "Ended because", "Summary", "Meeting time"], rows)


@router.get("/api/reports/deals.csv")
async def rep_deals(_: User = Depends(current_user), db: Session = Depends(get_db)):
    return csv_response("deals.csv", ["Business", "Service", "Stage", "Value", "Final value", "Proposal date", "Expected close", "Closed", "Lost reason", "Source"],
                        [[d["business"], d["service"], d["stage"], d["value"], d["final_value"], d["proposal_date"], d["expected_close"], d["closed_at"], d["lost_reason"], d["source"]]
                         for d in (deal_json(db, x) for x in db.query(Deal).order_by(Deal.id).all())])


@router.get("/api/audit")
async def audit_log(_: User = Depends(current_user), db: Session = Depends(get_db)):
    return [{"at": a.at.isoformat(), "action": a.action, "detail": a.detail} for a in db.query(AuditLog).order_by(AuditLog.id.desc()).limit(150).all()]
