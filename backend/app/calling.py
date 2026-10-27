"""Stage D: calling engine (windows, dispatch, polling, follow-ups) and its API."""
import asyncio
import os
from datetime import datetime, time as dtime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from . import agent_build, outcomes, retell
from .db import SessionLocal, get_db
from .deps import audit, get_setting
from .leads_io import add_dnc
from .models import AgentRec, Call, CallTask, Campaign, Deal, Lead, Market, User
from .phones import normalize
from .security import current_user

router = APIRouter()
STATE = {"paused": "", "error": "", "last_tick": None}
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
NO_CALL_STATUS = {"Do Not Call", "Wrong Number", "Not Interested", "Unreachable", "Won", "Lost", "Meeting Booked"}
NO_ENGAGE = {"short_call", "no_answer", "voicemail"}
TICK_SECONDS = 15


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---------------- calling windows ----------------
def _local(m: Market, dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc).astimezone(ZoneInfo(m.timezone))


def window_ok(m: Market, dt: datetime) -> bool:
    l = _local(m, dt)
    return DAYS[l.weekday()] not in m.weekend_days and m.call_start <= l.strftime("%H:%M") < m.call_end


def next_window(m: Market, dt: datetime) -> datetime:
    """Earliest UTC time at or after dt that is inside the market's calling hours."""
    tz, l = ZoneInfo(m.timezone), _local(m, dt)
    sh, sm = map(int, m.call_start.split(":"))
    eh, em = map(int, m.call_end.split(":"))
    for d in range(15):
        day = l.date() + timedelta(days=d)
        if DAYS[day.weekday()] in m.weekend_days:
            continue
        start = datetime.combine(day, dtime(sh, sm), tzinfo=tz)
        end = datetime.combine(day, dtime(eh, em), tzinfo=tz)
        if d == 0 and l >= end:
            continue
        pick = max(start, l) if d == 0 else start
        return pick.astimezone(timezone.utc).replace(tzinfo=None)
    return dt + timedelta(days=1)


def owner_day_start(db: Session) -> datetime:
    tz = ZoneInfo(get_setting(db, "general").get("timezone", "UTC"))
    now = datetime.now(tz)
    return now.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc).replace(tzinfo=None)


# ---------------- rules a lead must pass before any call ----------------
def lead_blocker(db: Session, lead: Lead | None):
    if not lead:
        return "The lead was deleted."
    if lead.source == "demo":
        return "Sample leads cannot be called."
    if lead.status in NO_CALL_STATUS:
        return f"Lead status is {lead.status}."
    phone = normalize(lead.phone, lead.market_code or "")
    if not phone:
        return "Phone number is missing or not in international format. Fix it in Leads."
    from .models import DNC
    if db.query(DNC).filter(DNC.phone == phone).first():
        return "On the Do Not Call list."
    if not lead.market_code:
        return "Choose a market for this lead first."
    return None


def build_vars(db: Session, lead: Lead, kind: str, attempt: int) -> dict:
    a = lead.analysis or {}
    pains = [p for p in a.get("pains", []) if p.get("direct")]          # the agent only states verified problems, never hypotheses
    top = sorted(pains, key=lambda p: -p.get("severity", 0))
    top = top[0] if top else {}
    last = db.query(Call).filter(Call.lead_id == lead.id, Call.summary.isnot(None), Call.summary != "").order_by(Call.id.desc()).first()
    n = get_setting(db, "calling")["followup_count"]
    return {"business_name": lead.business_name, "lead_name": lead.contact_name or "the owner",
            "company_name": agent_build.company(db), "pain_point": top.get("pain") or "",
            "evidence": top.get("evidence") or "No verified problem yet. Ask open questions and do not claim any problem.", "hy_solution": lead.hy_solution or "",
            "talking_points": " ".join((a.get("talking_points") or [])[:3]),
            "last_call_summary": last.summary if last else "None. This is the first call.",
            "call_attempt": ("callback the person asked for" if kind == "callback" else
                             "first call" if attempt == 0 else f"follow-up {attempt} of {n}")}


def pick_agent(db: Session, market_code: str):
    v = get_setting(db, "voice")
    lang = v["call_language_by_market"].get(market_code, "en-US")
    return (db.query(AgentRec).filter(AgentRec.language == lang).first()
            or db.query(AgentRec).filter(AgentRec.language == "en-US").first())


def cancel_pending(db: Session, lead_id: int, note: str):
    db.query(CallTask).filter(CallTask.lead_id == lead_id, CallTask.status == "pending").update(
        {CallTask.status: "cancelled", CallTask.note: note}, synchronize_session=False)


def ensure_deal(db: Session, lead: Lead):
    if db.query(Deal).filter(Deal.lead_id == lead.id, Deal.stage.notin_(["Won", "Lost"])).first():
        return
    stages = get_setting(db, "acquisition")["stages"]
    stage = "Meeting" if "Meeting" in stages else stages[min(3, len(stages) - 3)]
    db.add(Deal(lead_id=lead.id, service=lead.hy_solution, stage=stage, value=0))


# ---------------- what happens after a call ----------------
def apply_outcome(db: Session, call: Call, info: dict):
    call.outcome, call.summary, call.meeting_when = info["outcome"], info["summary"], info.get("meeting_when", "")
    lead = db.get(Lead, call.lead_id) if call.lead_id else None
    if not lead:
        db.commit()
        return
    cs, out, now = get_setting(db, "calling"), info["outcome"], utcnow()
    if out in NO_ENGAGE:
        cancel_pending(db, lead.id, "Replaced by a newer plan")
        if call.attempt < cs["followup_count"]:
            db.add(CallTask(lead_id=lead.id, campaign_id=call.campaign_id, kind="followup", attempt=call.attempt + 1,
                            due_at=now + timedelta(hours=cs["followup_gap_hours"]),
                            note=f"Follow-up {call.attempt + 1} of {cs['followup_count']}"))
            lead.status = "Follow-up Pending"
        else:
            lead.status = "Unreachable"
    elif out == "callback_requested":
        cancel_pending(db, lead.id, "Replaced by a callback")
        hrs = info.get("callback_in_hours") or cs["callback_default_hours"]
        db.add(CallTask(lead_id=lead.id, campaign_id=call.campaign_id, kind="callback", attempt=call.attempt,
                        due_at=now + timedelta(hours=hrs), note="Callback the person asked for"))
        lead.status = "Follow-up Pending"
    else:
        cancel_pending(db, lead.id, f"Call ended: {outcomes.LABEL.get(out, out)}")
        if out == "meeting_booked":
            lead.status = "Meeting Booked"
            ensure_deal(db, lead)
        elif out == "interested":
            lead.status = "Interested"
        elif out == "not_interested":
            lead.status = "Not Interested"
        elif out == "wrong_number":
            lead.status = "Wrong Number"
        elif out == "do_not_call":
            phone = normalize(lead.phone, lead.market_code or "")
            if phone:
                add_dnc(db, phone, "Asked on a call")
            lead.status = "Do Not Call"
        else:
            lead.status = "Contacted"
    db.commit()


async def finalize(db: Session, call: Call, data: dict):
    st = data.get("call_status")
    call.status = "error" if st == "error" else "ended"
    s, e, dur = data.get("start_timestamp"), data.get("end_timestamp"), data.get("duration_ms")
    call.started_at = datetime.utcfromtimestamp(s / 1000) if s else call.created_at
    call.ended_at = datetime.utcfromtimestamp(e / 1000) if e else utcnow()
    call.duration_s = round(dur / 1000) if dur else (round((e - s) / 1000) if s and e else 0)
    call.disconnection_reason = str(data.get("disconnection_reason") or "")[:60]
    call.transcript, call.recording_url = data.get("transcript") or "", data.get("recording_url") or ""
    info = await outcomes.classify(call.transcript, call.duration_s, call.disconnection_reason,
                                   get_setting(db, "calling")["short_call_seconds"])
    apply_outcome(db, call, info)


async def poll_calls(db: Session):
    for call in db.query(Call).filter(Call.status.in_(["registered", "ongoing"])).all():
        try:
            data = await retell.get_call(call.retell_call_id)
        except retell.RetellError as e:
            if utcnow() - call.created_at > timedelta(minutes=30):
                await finalize(db, call, {"call_status": "error", "disconnection_reason": "error_poll"})
            STATE["error"] = str(e)[:200]
            continue
        if data.get("call_status") in ("ended", "error"):
            await finalize(db, call, data)
        elif data.get("call_status") == "ongoing" and call.status != "ongoing":
            call.status = "ongoing"
            db.commit()


async def dispatch(db: Session):
    cs, nums = get_setting(db, "calling"), get_setting(db, "integrations").get("phone_numbers", [])
    STATE["paused"] = ""
    if not retell.configured():
        STATE["paused"] = "Add your Retell key in Settings > Integrations."
        return
    if not nums:
        STATE["paused"] = "Add your calling phone numbers in Settings > Integrations."
        return
    today = owner_day_start(db)
    active = db.query(Call).filter(Call.status.in_(["registered", "ongoing"])).count()
    calls_today = db.query(Call).filter(Call.created_at >= today).count()
    mins_today = (db.query(func.coalesce(func.sum(Call.duration_s), 0)).filter(Call.created_at >= today).scalar() or 0) / 60
    if calls_today >= cs["daily_call_limit"]:
        STATE["paused"] = "Daily call limit reached. Calls continue tomorrow, or raise the limit in Settings > Calling Rules."
        return
    if mins_today >= cs["daily_minutes_cap"]:
        STATE["paused"] = "Daily minutes cap reached. Calls continue tomorrow, or raise the cap in Settings > Calling Rules."
        return
    slots, now = cs["max_concurrent"] - active, utcnow()
    due = db.query(CallTask).filter(CallTask.status == "pending", CallTask.due_at <= now).order_by(CallTask.due_at).limit(25).all()
    for t in due:
        if slots <= 0 or calls_today >= cs["daily_call_limit"]:
            break
        camp = db.get(Campaign, t.campaign_id) if t.campaign_id else None
        if camp and camp.status != "active":
            continue
        lead = db.get(Lead, t.lead_id)
        why = lead_blocker(db, lead)
        if why:
            t.status, t.note = "blocked", why
            db.commit()
            continue
        m = db.query(Market).filter(Market.code == lead.market_code).first()
        if not m or not m.active:
            t.status, t.note = "blocked", "This market is switched off in Settings > Markets."
            db.commit()
            continue
        if not window_ok(m, now):
            t.due_at, t.note = next_window(m, now), f"Waiting for {m.name} calling hours"
            db.commit()
            continue
        agent = pick_agent(db, lead.market_code)
        if not agent:
            STATE["paused"] = "Build the voice agent first: Settings > Voice Agent > Build agent."
            break
        to = normalize(lead.phone, lead.market_code)
        try:
            resp = await retell.create_phone_call(nums[calls_today % len(nums)], to, agent.retell_agent_id,
                                                  build_vars(db, lead, t.kind, t.attempt),
                                                  {"lead_id": str(lead.id), "task_id": str(t.id)})
        except retell.RetellError as e:
            t.status, t.note = "blocked", str(e)[:290]
            db.commit()
            continue
        except Exception as e:                      # network trouble: try again in 5 minutes
            t.due_at, t.note = now + timedelta(minutes=5), f"Network problem, retrying: {str(e)[:120]}"
            db.commit()
            continue
        db.add(Call(lead_id=lead.id, campaign_id=t.campaign_id, task_id=t.id, kind=t.kind, attempt=t.attempt,
                    retell_call_id=resp["call_id"], status="registered", language=agent.language, to_number=to))
        t.status, t.note = "done", "Call placed"
        db.commit()
        slots -= 1
        calls_today += 1


async def tick():
    with SessionLocal() as db:
        STATE["error"] = ""
        await poll_calls(db)
        await dispatch(db)
        from . import backup
        backup.maybe_daily(db)
    STATE["last_tick"] = utcnow().isoformat()


async def scheduler_loop():
    while True:
        try:
            await tick()
        except Exception as e:
            STATE["error"] = f"{type(e).__name__}: {e}"[:200]
        await asyncio.sleep(TICK_SECONDS)


# ---------------- API ----------------
def parse_local(db: Session, text: str) -> datetime:
    """'2026-10-12T10:00' in the owner's time zone -> naive UTC."""
    try:
        d = datetime.fromisoformat(text)
    except ValueError:
        raise HTTPException(400, "Choose a valid date and time.")
    tz = ZoneInfo(get_setting(db, "general").get("timezone", "UTC"))
    return d.replace(tzinfo=tz).astimezone(timezone.utc).replace(tzinfo=None)


@router.get("/api/calling/status")
async def calling_status(_: User = Depends(current_user), db: Session = Depends(get_db)):
    cs, today = get_setting(db, "calling"), owner_day_start(db)
    return {"paused": STATE["paused"], "error": STATE["error"], "last_tick": STATE["last_tick"],
            "active_calls": db.query(Call).filter(Call.status.in_(["registered", "ongoing"])).count(),
            "calls_today": db.query(Call).filter(Call.created_at >= today).count(), "daily_limit": cs["daily_call_limit"],
            "minutes_today": round((db.query(func.coalesce(func.sum(Call.duration_s), 0)).filter(Call.created_at >= today).scalar() or 0) / 60, 1),
            "agents": [a.language for a in db.query(AgentRec).all()], "retell_configured": retell.configured(),
            "numbers": len(get_setting(db, "integrations").get("phone_numbers", []))}


@router.post("/api/voice/build")
async def build_voice(_: User = Depends(current_user), db: Session = Depends(get_db)):
    try:
        report = await agent_build.build_agents(db)
    except retell.RetellError as e:
        raise HTTPException(502, str(e))
    audit(db, "voice_agent_built", "; ".join(report)[:250])
    return {"report": report}


class TestIn(BaseModel):
    to_number: str
    language: str = "en-US"


@router.post("/api/voice/test-call")
async def test_call(body: TestIn, _: User = Depends(current_user), db: Session = Depends(get_db)):
    to = normalize(body.to_number)
    nums = get_setting(db, "integrations").get("phone_numbers", [])
    if not to:
        raise HTTPException(400, "Use international format like +923001234567.")
    if not nums:
        raise HTTPException(400, "Add your calling phone numbers in Settings > Integrations first.")
    agent = db.query(AgentRec).filter(AgentRec.language == body.language).first() or db.query(AgentRec).filter(AgentRec.language == "en-US").first()
    if not agent:
        raise HTTPException(400, "Build the voice agent first.")
    vars_ = {"business_name": "Test Business", "lead_name": "the owner", "company_name": agent_build.company(db),
             "pain_point": "No online booking", "evidence": "This is a test call.", "hy_solution": "Website design and development",
             "talking_points": "This is only a test of the calling agent.", "last_call_summary": "None. This is a test call.",
             "call_attempt": "first call"}
    try:
        resp = await retell.create_phone_call(nums[0], to, agent.retell_agent_id, vars_, {"test": "1"})
    except retell.RetellError as e:
        raise HTTPException(502, str(e))
    db.add(Call(lead_id=None, kind="first", attempt=0, retell_call_id=resp["call_id"], status="registered", language=agent.language, to_number=to))
    db.commit()
    return {"ok": True}


class CampaignIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    lead_ids: list[int] = []
    market_code: str = ""
    status: str = ""
    min_fit: int = Field(0, ge=0, le=100)
    limit: int = Field(50, ge=1, le=200)
    start_at: str = ""                  # empty = now, else local date-time in the owner's time zone


@router.post("/api/campaigns")
async def create_campaign(body: CampaignIn, _: User = Depends(current_user), db: Session = Depends(get_db)):
    start = parse_local(db, body.start_at) if body.start_at else utcnow()
    if start < utcnow() - timedelta(minutes=1):
        raise HTTPException(400, "The start time is in the past.")
    q = db.query(Lead)
    if body.lead_ids:
        q = q.filter(Lead.id.in_(body.lead_ids))
    else:
        if body.market_code:
            q = q.filter(Lead.market_code == body.market_code)
        if body.status:
            q = q.filter(Lead.status == body.status)
        if body.min_fit > 0:
            q = q.filter(Lead.fit_score >= body.min_fit)
    leads = q.order_by(Lead.fit_score.desc()).limit(body.limit).all()
    camp = Campaign(name=body.name.strip(), status="active", start_at=start if body.start_at else None,
                    params=body.model_dump())
    db.add(camp)
    db.flush()
    queued, skipped = 0, {}
    pending = {t.lead_id for t in db.query(CallTask).filter(CallTask.status == "pending").all()}
    for l in leads:
        why = "Already has a call planned" if l.id in pending else lead_blocker(db, l)
        if why:
            skipped[why] = skipped.get(why, 0) + 1
            continue
        db.add(CallTask(lead_id=l.id, campaign_id=camp.id, kind="first", attempt=0, due_at=start, note="First call"))
        l.status = "Queued" if l.status == "New" else l.status
        queued += 1
    db.commit()
    audit(db, "campaign_created", f"{camp.name}: {queued} queued")
    return {"id": camp.id, "queued": queued, "skipped": skipped}


@router.get("/api/campaigns")
async def list_campaigns(_: User = Depends(current_user), db: Session = Depends(get_db)):
    out = []
    for c in db.query(Campaign).order_by(Campaign.id.desc()).limit(50).all():
        tasks = db.query(CallTask).filter(CallTask.campaign_id == c.id)
        calls = db.query(Call).filter(Call.campaign_id == c.id)
        out.append({"id": c.id, "name": c.name, "status": c.status, "start_at": c.start_at.isoformat() if c.start_at else None,
                    "created_at": c.created_at.isoformat(), "pending": tasks.filter(CallTask.status == "pending").count(),
                    "calls": calls.count(),
                    "positive": calls.filter(Call.outcome.in_(["interested", "meeting_booked", "callback_requested"])).count()})
    return out


class CampStatus(BaseModel):
    status: str


@router.put("/api/campaigns/{cid}/status")
async def campaign_status(cid: int, body: CampStatus, _: User = Depends(current_user), db: Session = Depends(get_db)):
    c = db.get(Campaign, cid)
    if not c or body.status not in ("active", "paused", "cancelled"):
        raise HTTPException(400, "Unknown campaign or status")
    c.status = body.status
    if body.status == "cancelled":
        db.query(CallTask).filter(CallTask.campaign_id == cid, CallTask.status == "pending").update(
            {CallTask.status: "cancelled", CallTask.note: "Campaign cancelled"}, synchronize_session=False)
    db.commit()
    return {"ok": True}


def task_json(db: Session, t: CallTask) -> dict:
    l = db.get(Lead, t.lead_id)
    c = db.get(Campaign, t.campaign_id) if t.campaign_id else None
    return {"id": t.id, "lead_id": t.lead_id, "business": l.business_name if l else "(deleted)", "phone": l.phone if l else "",
            "market": l.market_code if l else "", "kind": t.kind, "attempt": t.attempt, "status": t.status, "note": t.note,
            "due_at": t.due_at.isoformat() if t.due_at else None, "campaign": c.name if c else ""}


@router.get("/api/tasks")
async def list_tasks(status: str = "pending", _: User = Depends(current_user), db: Session = Depends(get_db)):
    q = db.query(CallTask)
    if status != "all":
        q = q.filter(CallTask.status == status)
    return [task_json(db, t) for t in q.order_by(CallTask.due_at).limit(300).all()]


class WhenIn(BaseModel):
    start_at: str


@router.post("/api/tasks/{tid}/now")
async def task_now(tid: int, _: User = Depends(current_user), db: Session = Depends(get_db)):
    t = db.get(CallTask, tid)
    if not t:
        raise HTTPException(404, "Not found")
    t.status, t.due_at, t.note = "pending", utcnow(), "Call now requested"
    db.commit()
    return {"ok": True}


@router.post("/api/tasks/{tid}/reschedule")
async def task_resched(tid: int, body: WhenIn, _: User = Depends(current_user), db: Session = Depends(get_db)):
    t = db.get(CallTask, tid)
    if not t:
        raise HTTPException(404, "Not found")
    t.status, t.due_at, t.note = "pending", parse_local(db, body.start_at), "Rescheduled by owner"
    db.commit()
    return {"ok": True}


@router.post("/api/tasks/{tid}/cancel")
async def task_cancel(tid: int, _: User = Depends(current_user), db: Session = Depends(get_db)):
    t = db.get(CallTask, tid)
    if not t:
        raise HTTPException(404, "Not found")
    t.status, t.note = "cancelled", "Cancelled by owner"
    db.commit()
    return {"ok": True}


def call_json(db: Session, c: Call, full=False) -> dict:
    l = db.get(Lead, c.lead_id) if c.lead_id else None
    d = {"id": c.id, "lead_id": c.lead_id, "business": l.business_name if l else ("Test call" if not c.lead_id else "(deleted)"),
         "to_number": c.to_number, "kind": c.kind, "attempt": c.attempt, "status": c.status, "outcome": c.outcome,
         "outcome_label": outcomes.LABEL.get(c.outcome, c.outcome or ""), "duration_s": c.duration_s, "summary": c.summary,
         "created_at": c.created_at.isoformat(), "reason": c.disconnection_reason, "meeting_when": c.meeting_when}
    if full:
        d.update({"transcript": c.transcript, "recording_url": c.recording_url, "language": c.language})
    return d


@router.get("/api/calls")
async def list_calls(lead_id: int = 0, outcome: str = "", _: User = Depends(current_user), db: Session = Depends(get_db)):
    q = db.query(Call)
    if lead_id:
        q = q.filter(Call.lead_id == lead_id)
    if outcome:
        q = q.filter(Call.outcome == outcome)
    return [call_json(db, c) for c in q.order_by(Call.id.desc()).limit(300).all()]


@router.get("/api/calls/{cid}")
async def get_call_detail(cid: int, _: User = Depends(current_user), db: Session = Depends(get_db)):
    c = db.get(Call, cid)
    if not c:
        raise HTTPException(404, "Not found")
    return call_json(db, c, True)


class OutcomeIn(BaseModel):
    outcome: str


@router.put("/api/calls/{cid}/outcome")
async def override_outcome(cid: int, body: OutcomeIn, _: User = Depends(current_user), db: Session = Depends(get_db)):
    c = db.get(Call, cid)
    if not c or body.outcome not in outcomes.LABEL:
        raise HTTPException(400, "Unknown call or outcome")
    apply_outcome(db, c, {"outcome": body.outcome, "summary": c.summary or "Outcome set by owner.", "meeting_when": c.meeting_when or ""})
    audit(db, "outcome_overridden", f"call {cid} -> {body.outcome}")
    return call_json(db, c)
