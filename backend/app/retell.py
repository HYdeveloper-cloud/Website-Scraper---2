"""Retell AI client. Every Retell field name lives here, so a change on their side is a one-file fix."""
import os

import httpx

BASE = os.getenv("RETELL_BASE_URL", "https://api.retellai.com")


class RetellError(RuntimeError):
    pass


def configured() -> bool:
    return bool(os.getenv("RETELL_API_KEY"))


async def _call(method: str, path: str, **kw) -> dict:
    key = os.getenv("RETELL_API_KEY")
    if not key:
        raise RetellError("The Retell key is missing. Add it in Settings > Integrations.")
    async with httpx.AsyncClient(timeout=120) as c:
        r = await c.request(method, BASE + path, headers={"Authorization": f"Bearer {key}"}, **kw)
    if r.status_code >= 300:
        raise RetellError(f"Retell said {r.status_code} on {path}: {r.text[:300]}")
    return r.json() if r.content else {}


async def create_kb(name: str, texts: list[tuple[str, str]]) -> str:
    fields = {"knowledge_base_name": (None, name[:39])}
    for i, (title, text) in enumerate(texts[:50]):
        fields[f"knowledge_base_texts[{i}][title]"] = (None, title[:100])
        fields[f"knowledge_base_texts[{i}][text]"] = (None, text[:20000])
    return (await _call("POST", "/create-knowledge-base", files=fields))["knowledge_base_id"]


async def delete_kb(kb_id: str):
    await _call("DELETE", f"/delete-knowledge-base/{kb_id}")


def _llm_body(prompt: str, begin: str, kb_id: str) -> dict:
    return {"general_prompt": prompt, "begin_message": begin, "model": os.getenv("RETELL_LLM_MODEL", "gpt-4.1"),
            "knowledge_base_ids": [kb_id],
            "general_tools": [{"type": "end_call", "name": "end_call",
                               "description": "End the call when the person says goodbye, asks not to be called again, "
                                              "has been told the next step, or the call is not going anywhere."}]}


async def create_llm(prompt: str, begin: str, kb_id: str) -> str:
    return (await _call("POST", "/create-retell-llm", json=_llm_body(prompt, begin, kb_id)))["llm_id"]


async def update_llm(llm_id: str, prompt: str, begin: str, kb_id: str):
    await _call("PATCH", f"/update-retell-llm/{llm_id}", json=_llm_body(prompt, begin, kb_id))


def _agent_body(name, voice_id, language, speed, max_minutes) -> dict:
    return {"agent_name": name, "voice_id": voice_id, "language": language, "voice_speed": speed,
            "max_call_duration_ms": int(max_minutes * 60_000)}


async def create_agent(name, llm_id, voice_id, language, speed, max_minutes) -> str:
    body = {"response_engine": {"type": "retell-llm", "llm_id": llm_id}, **_agent_body(name, voice_id, language, speed, max_minutes)}
    try:   # hang up on voicemail instead of talking to a machine; skip if Retell rejects the option
        return (await _call("POST", "/create-agent", json={**body, "voicemail_option": {"action": {"type": "hangup"}}}))["agent_id"]
    except RetellError:
        return (await _call("POST", "/create-agent", json=body))["agent_id"]


async def update_agent(agent_id, voice_id, language, speed, max_minutes, name):
    await _call("PATCH", f"/update-agent/{agent_id}", json=_agent_body(name, voice_id, language, speed, max_minutes))


async def create_phone_call(from_number: str, to_number: str, agent_id: str, variables: dict, metadata: dict) -> dict:
    return await _call("POST", "/v2/create-phone-call", json={
        "from_number": from_number, "to_number": to_number, "override_agent_id": agent_id,
        "retell_llm_dynamic_variables": {k: str(v)[:600] for k, v in variables.items()}, "metadata": metadata})


async def get_call(call_id: str) -> dict:
    return await _call("GET", f"/v2/get-call/{call_id}")


async def ping():
    await _call("GET", "/list-agents")
