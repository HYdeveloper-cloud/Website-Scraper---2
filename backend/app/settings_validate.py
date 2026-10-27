"""Checks every Settings area before it is saved. Returns the cleaned value or raises HTTPException."""
import re
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .models import Market

LANG = re.compile(r"^[a-z]{2,3}(-[A-Za-z]{2,4})?$|^multi$")


def bad(msg):
    raise HTTPException(400, msg)


def num(body, key, lo, hi, kind=int):
    try:
        v = kind(body.get(key))
    except (TypeError, ValueError):
        bad(f"{key.replace('_', ' ').capitalize()} must be a number.")
    if not lo <= v <= hi:
        bad(f"{key.replace('_', ' ').capitalize()} must be between {lo} and {hi}.")
    return v


def validate(key: str, body: dict, db: Session) -> dict:
    if key == "voice":
        voices = {str(k): str(v).strip()[:80] for k, v in (body.get("voices") or {}).items() if LANG.match(str(k))}
        codes = {m.code for m in db.query(Market).all()}
        by_market = {str(k): str(v) for k, v in (body.get("call_language_by_market") or {}).items() if k in codes and LANG.match(str(v))}
        opening = str(body.get("opening", "")).strip()
        if not opening or len(opening) > 400:
            bad("The opening line is required and must be under 400 characters.")
        if not re.search(r"\bAI\b", opening) and "artificial" not in opening.lower():
            bad("The opening line must tell the person they are speaking with an AI assistant. Add the words 'an AI assistant'.")
        site = str(body.get("company_site", "")).strip()
        if site and not re.match(r"^https?://[^\s]+$", site):
            bad("Company website must start with http:// or https://")
        return {"agent_name": str(body.get("agent_name", "")).strip()[:80] or "HY Developer Sales Agent", "voices": voices,
                "call_language_by_market": by_market, "tone": str(body.get("tone", "")).strip()[:200] or "professional and warm",
                "speed": num(body, "speed", 0.6, 1.4, float), "opening": opening,
                "script_notes": str(body.get("script_notes", ""))[:3000], "objection_notes": str(body.get("objection_notes", ""))[:3000],
                "company_facts": str(body.get("company_facts", ""))[:5000], "company_site": site,
                "max_call_minutes": num(body, "max_call_minutes", 1, 15)}
    if key == "calling":
        return {"short_call_seconds": num(body, "short_call_seconds", 5, 60), "followup_count": num(body, "followup_count", 0, 5),
                "followup_gap_hours": num(body, "followup_gap_hours", 1, 168), "callback_default_hours": num(body, "callback_default_hours", 1, 168),
                "max_concurrent": num(body, "max_concurrent", 1, 10), "daily_call_limit": num(body, "daily_call_limit", 1, 1000),
                "daily_minutes_cap": num(body, "daily_minutes_cap", 10, 5000), "cost_per_minute": num(body, "cost_per_minute", 0, 5, float)}
    if key == "acquisition":
        stages = [str(s).strip()[:30] for s in body.get("stages", []) if str(s).strip()]
        if len(stages) < 4 or len(stages) > 12 or len(set(stages)) != len(stages):
            bad("Use 4 to 12 different stage names.")
        if stages[-2:] != ["Won", "Lost"]:
            bad("The last two stages must be Won and Lost, in that order.")
        return {"stages": stages, "monthly_target": num(body, "monthly_target", 0, 1_000_000_000, float)}
    if key == "compliance":
        return {"recording_notice_enabled": bool(body.get("recording_notice_enabled")),
                "recording_notice": str(body.get("recording_notice", "")).strip()[:200] or "This call may be recorded for quality purposes."}
    if key == "leads":
        dm = str(body.get("default_market", ""))
        if dm and not db.query(Market).filter(Market.code == dm).first():
            bad("Choose a market from the list.")
        return {"default_market": dm, "analyze_uploads": bool(body.get("analyze_uploads"))}
    if key == "scoring":
        return validate_scoring(body, db)
    raise HTTPException(404, "Unknown settings area")


def validate_market(body: dict) -> dict:
    tz = str(body.get("timezone", "")).strip()
    try:
        ZoneInfo(tz)
    except Exception:
        bad("Time zone not recognised. Use a name like Asia/Dubai.")
    s, e = str(body.get("call_start", "")), str(body.get("call_end", ""))
    if not (re.match(r"^([01]\d|2[0-3]):[0-5]\d$", s) and re.match(r"^([01]\d|2[0-3]):[0-5]\d$", e)) or s >= e:
        bad("Calling hours must look like 09:00 to 18:00, with the start before the end.")
    days = [d for d in body.get("weekend_days", []) if d in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")]
    if len(days) >= 7:
        bad("At least one calling day is needed.")
    return {"timezone": tz, "call_start": s, "call_end": e, "weekend_days": days, "active": bool(body.get("active", True))}


def validate_scoring(body: dict, db: Session) -> dict:
    """Checks the lead scoring choices. Every number has a sensible range so a typo cannot break scoring."""
    from .scoring import DEFAULTS
    codes = {m.code for m in db.query(Market).all()}
    icp = body.get("icp") or {}
    lines = lambda v: [str(x).strip()[:60] for x in (v or []) if str(x).strip()][:30]
    w = body.get("weights") or {}
    weights = {k: num(w, k, 0, 100) for k in DEFAULTS["weights"]}
    if sum(weights.values()) != 100:
        bad(f"The five weights must add up to 100. They add up to {sum(weights.values())} now.")
    r = body.get("rules") or {}
    rules = {"unverified_cap": num(r, "unverified_cap", 0, 100), "inferred_penalty": num(r, "inferred_penalty", 0, 50), "avoid_cap": num(r, "avoid_cap", 0, 100),
             "high_from": num(r, "high_from", 1, 100), "medium_from": num(r, "medium_from", 1, 100),
             "verified_min_pain": num(r, "verified_min_pain", 1, 5), "verified_min_evidence": num(r, "verified_min_evidence", 1, 5)}
    if rules["medium_from"] >= rules["high_from"]:
        bad("High priority must start above Medium priority.")
    g = body.get("gap_points") or {}
    gp = {"low": num(g, "low", 1, 100), "medium": num(g, "medium", 1, 100), "high": num(g, "high", 1, 100), "hypothesis_factor": num(g, "hypothesis_factor", 0, 1, float)}
    if not gp["low"] <= gp["medium"] <= gp["high"]:
        bad("Gap points must go up from low to medium to high.")
    steps = [float(x) for x in (body.get("pain_steps") or [])]
    if len(steps) != 4 or any(s <= 0 for s in steps) or steps != sorted(steps) or len(set(steps)) != 4:
        bad("The four pain steps must be increasing positive numbers.")
    b, z = body.get("buying") or {}, body.get("business") or {}
    return {"icp": {"target_industries": lines(icp.get("target_industries")), "avoid_industries": lines(icp.get("avoid_industries")),
                    "target_markets": [m for m in (icp.get("target_markets") or []) if m in codes]},
            "weights": weights, "rules": rules, "gap_points": gp, "pain_steps": steps,
            "buying": {"one": num(b, "one", 0, 5), "two_or_more": num(b, "two_or_more", 0, 5)},
            "business": {k: num(z, k, 0, 5) for k in DEFAULTS["business"]}}
