"""Turns a finished call into an outcome. Facts first (duration, disconnect reason), language model only for real conversations."""
import re

from . import llm

NO_ANSWER = {"dial_no_answer", "dial_busy", "dial_failed", "user_declined", "registered_call_timeout"}
VALID = {"interested", "meeting_booked", "callback_requested", "not_interested", "do_not_call", "wrong_number", "connected"}
LABEL = {"interested": "Interested", "meeting_booked": "Meeting booked", "callback_requested": "Callback requested",
         "not_interested": "Not interested", "do_not_call": "Do Not Call", "wrong_number": "Wrong number",
         "connected": "Connected, no clear result", "short_call": "Short call", "no_answer": "No answer", "voicemail": "Voicemail"}
SYSTEM = """You review a phone call between an AI sales assistant calling for HY Developer (a software agency) and a business.
Choose ONE outcome:
- meeting_booked: the person agreed to a specific call or meeting time
- callback_requested: the person asked to be called back at another time
- interested: the person wants information or is open to talking later, with no time agreed
- not_interested: the person declined
- do_not_call: the person asked to stop being called or to be removed
- wrong_number: wrong business or person
- connected: a real conversation but no clear result
Return ONLY JSON: {"outcome":"","summary":"one or two plain sentences","callback_in_hours":null,"meeting_when":""}
callback_in_hours: whole hours until the requested callback, or null. meeting_when: the agreed time in the person's words, or empty."""


def heuristic(text: str) -> dict:
    t = text.lower()
    rules = [("do_not_call", r"do not call|don't call|stop calling|remove (me|my number)|take me off"),
             ("wrong_number", r"wrong number|wrong person"), ("not_interested", r"not interested|no thank"),
             ("callback_requested", r"call (me )?back|call me later|try again later")]
    for out, pat in rules:
        if re.search(pat, t):
            return {"outcome": out, "summary": "Classified from keywords in the transcript.", "callback_in_hours": None, "meeting_when": ""}
    return {"outcome": "connected", "summary": "A conversation took place. Read the transcript.", "callback_in_hours": None, "meeting_when": ""}


async def classify(transcript: str, duration_s: int, reason: str, short_s: int) -> dict:
    reason = reason or ""
    base = {"summary": "", "callback_in_hours": None, "meeting_when": ""}
    if reason in NO_ANSWER or reason.startswith("error"):
        return {**base, "outcome": "no_answer", "summary": f"Not connected ({reason or 'no reason given'})."}
    if "voicemail" in reason or "machine" in reason:
        return {**base, "outcome": "voicemail", "summary": "Reached voicemail."}
    if duration_s < short_s:
        return {**base, "outcome": "short_call", "summary": f"The call lasted {duration_s} seconds."}
    if not (transcript or "").strip():
        return {**base, "outcome": "connected", "summary": "Connected, but there is no transcript."}
    if not llm.configured():
        return heuristic(transcript)
    try:
        d = await llm.complete_json(SYSTEM, f"TRANSCRIPT:\n{transcript[:12000]}", 600)
        out = d.get("outcome") if d.get("outcome") in VALID else "connected"
        hrs = d.get("callback_in_hours")
        return {"outcome": out, "summary": str(d.get("summary", ""))[:500],
                "callback_in_hours": int(hrs) if isinstance(hrs, (int, float)) and 1 <= hrs <= 720 else None,
                "meeting_when": str(d.get("meeting_when", ""))[:120]}
    except Exception:
        return heuristic(transcript)
