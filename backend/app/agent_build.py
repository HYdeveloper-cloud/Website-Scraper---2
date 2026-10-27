"""Builds the HY Developer calling agent: prompt from Settings and the service catalog, knowledge base, Retell agent per language."""
from datetime import datetime

from sqlalchemy.orm import Session

from . import retell
from .crawler import crawl
from .deps import get_setting
from .models import AgentRec, Service
from .netsafe import safe_public_url


def company(db: Session) -> str:
    return get_setting(db, "general").get("company_name", "HY Developer")


def opening_line(db: Session) -> str:
    v, comp = get_setting(db, "voice"), get_setting(db, "compliance")
    line = v["opening"].replace("{{company_name}}", company(db))
    if comp.get("recording_notice_enabled"):
        line += " " + comp["recording_notice"]
    return line


def compose_prompt(db: Session, language: str) -> str:
    v, name = get_setting(db, "voice"), company(db)
    services = db.query(Service).order_by(Service.sort).all()
    cat = "\n".join(f"- {s.name}: {s.pitch} It helps with: {', '.join(s.pain_points)}." for s in services)
    speak = ("Speak Arabic in a polite, professional Gulf-friendly style. If the person answers in English, switch to English."
             if language.lower().startswith("ar") else "Speak clear, natural English.")
    return f"""## Identity
You are {v['agent_name']}, an AI voice assistant phoning businesses on behalf of {name}, a software agency. Your tone is {v['tone']}. {speak}

## Goal
Reach the right person, find out whether the problem we noticed is real for them, and agree a short call or meeting with the {name} team. You are not here to close a sale on this call.

## About {name}
Services:
{cat}
{('Facts you may state:' + chr(10) + v['company_facts']) if v['company_facts'].strip() else ''}
Use the knowledge base for more detail about {name}.

## This call
- Business: {{{{business_name}}}}. Person: {{{{lead_name}}}}.
- Call type: {{{{call_attempt}}}}.
- What we noticed: {{{{pain_point}}}}. Evidence: {{{{evidence}}}}.
- Service that fits: {{{{hy_solution}}}}.
- Points you can raise: {{{{talking_points}}}}.
- Earlier contact: {{{{last_call_summary}}}}

## Conversation flow
1. The opening line has already told them you are an AI assistant calling for {name}. Do not repeat it. Ask if now is an okay moment for one minute.
2. If something was noticed, mention it as an observation, not an accusation, and ask one question about it. If nothing was noticed, do not claim any problem: ask how they handle bookings, enquiries and follow-ups today.
3. In two short sentences, say how {{{{hy_solution}}}} would help with exactly that.
4. Propose a 15 minute call with the team. Ask for a day and time. Repeat it back to confirm.
5. Thank them and end the call.
On a follow-up, say briefly that we tried to reach them before, then continue from step 1. On a callback they asked for, thank them for making time.

## Objections
- Price: do not quote any price. Say the team gives a quote after understanding the need.
- Already have someone: say that is fine, and offer a short second opinion call.
- Send information: ask for an email address and say the team will send details.
- Busy: offer a better time and note it.
- Not interested: thank them and end the call politely.
{v['objection_notes']}

## Extra instructions from the owner
{v['script_notes']}

## Hard rules
- Only state facts from this prompt, the call details above, or the knowledge base. Never invent prices, discounts, results, clients, timelines or guarantees. If you do not know, say the team will follow up.
- If asked whether you are an AI, say yes, honestly.
- If they ask not to be called again, apologize once, confirm they will be removed, and end the call.
- Keep each turn to one to three short sentences. One question at a time. No lists. Never pressure anyone.
"""


async def kb_texts(db: Session) -> tuple[list[tuple[str, str]], str]:
    v, name = get_setting(db, "voice"), company(db)
    services = db.query(Service).order_by(Service.sort).all()
    texts = [(f"{name} services", "\n\n".join(
        f"{s.name}\nPitch: {s.pitch}\nSolves: {', '.join(s.pain_points)}\nSigns we look for: {', '.join(s.signals)}" for s in services))]
    if v["company_facts"].strip():
        texts.append(("Facts from the owner", v["company_facts"]))
    note = ""
    if v["company_site"].strip():
        try:
            pages, _, _ = await crawl(safe_public_url(v["company_site"]), 12)
            texts += [((p["title"] or p["url"]), f"Source: {p['url']}\n\n{p['text']}") for p in pages]
            note = f"Read {len(pages)} pages from {v['company_site']}."
        except Exception as e:
            note = f"Could not read {v['company_site']}: {e}"
    return texts, note


async def build_agents(db: Session) -> list[str]:
    v = get_setting(db, "voice")
    wanted = sorted(set(v["call_language_by_market"].values()) | {"en-US"})
    report, texts = [], None
    todo = [(l, v["voices"].get(l, "").strip()) for l in wanted]
    todo = [(l, vid) for l, vid in todo if vid]
    for l in wanted:
        if not v["voices"].get(l, "").strip():
            report.append(f"No voice set for {l}. Calls in that language use English instead.")
    if not todo:
        raise retell.RetellError("Set a Retell voice ID for English (en-US) first.")
    texts, note = await kb_texts(db)
    report.append(note or "Company website not added to the knowledge base.")
    old_kbs = {a.kb_id for a in db.query(AgentRec).all() if a.kb_id}
    kb_id = await retell.create_kb(f"{company(db)} KB {datetime.utcnow():%m%d%H%M}", texts)
    begin = opening_line(db)
    for lang, voice in todo:
        prompt, rec = compose_prompt(db, lang), db.query(AgentRec).filter(AgentRec.language == lang).first()
        name = f"{v['agent_name']} ({lang})"
        if rec:
            try:
                await retell.update_llm(rec.retell_llm_id, prompt, begin, kb_id)
                await retell.update_agent(rec.retell_agent_id, voice, lang, v["speed"], v["max_call_minutes"], name)
                rec.voice_id, rec.kb_id, rec.built_at = voice, kb_id, datetime.utcnow()
                report.append(f"Updated the {lang} agent.")
                continue
            except retell.RetellError as e:
                report.append(f"Could not update the {lang} agent ({e}). Creating a new one.")
                db.delete(rec)
                db.flush()
        llm_id = await retell.create_llm(prompt, begin, kb_id)
        agent_id = await retell.create_agent(name, llm_id, voice, lang, v["speed"], v["max_call_minutes"])
        db.add(AgentRec(language=lang, retell_agent_id=agent_id, retell_llm_id=llm_id, kb_id=kb_id, voice_id=voice))
        report.append(f"Created the {lang} agent.")
    db.commit()
    for old in old_kbs - {kb_id}:
        try:
            await retell.delete_kb(old)
        except retell.RetellError:
            pass
    return report
