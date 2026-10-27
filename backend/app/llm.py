"""Any OpenAI-compatible chat API (Gemini, OpenAI, Groq, OpenRouter...). The key and address are set in Settings > Integrations."""
import json
import os

import httpx

DEFAULT_BASE = "https://generativelanguage.googleapis.com/v1beta/openai"


def configured() -> bool:
    return bool(os.getenv("LLM_API_KEY"))


def parse_json(text: str) -> dict:
    a, b = text.find("{"), text.rfind("}")
    if a == -1 or b == -1 or b < a:
        raise RuntimeError("The language model did not return JSON.")
    try:
        return json.loads(text[a:b + 1])
    except json.JSONDecodeError:
        raise RuntimeError("The language model returned broken JSON.")


async def complete_json(system: str, user: str, max_tokens: int = 6000) -> dict:
    key = os.getenv("LLM_API_KEY")
    if not key:
        raise RuntimeError("The language model key is missing. Add it in Settings > Integrations.")
    base = os.getenv("LLM_BASE_URL", DEFAULT_BASE).rstrip("/")
    body = {"model": os.getenv("LLM_MODEL", "gemini-2.5-flash"), "max_tokens": max_tokens,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {"type": "json_object"}}
    if "generativelanguage.googleapis.com" in base:
        body["reasoning_effort"] = "low"       # Gemini "thinking" can use up the whole answer budget and leave the answer empty
    problem = ""
    async with httpx.AsyncClient(timeout=180) as c:
        for attempt in range(3):
            r = await c.post(f"{base}/chat/completions", json=body, headers={"Authorization": f"Bearer {key}"})
            if r.status_code == 400 and attempt == 0:           # this provider may not accept the extra options
                body.pop("response_format", None)
                body.pop("reasoning_effort", None)
                continue
            if r.status_code >= 300:
                raise RuntimeError(f"Language model error {r.status_code}: {r.text[:200]}")
            choice = r.json()["choices"][0]
            text = (choice.get("message") or {}).get("content") or ""
            try:
                return parse_json(text)
            except RuntimeError as e:
                problem = f"{e} It stopped because: {choice.get('finish_reason') or 'unknown'}. Answer length: {len(text)} characters."
                body["max_tokens"] = min(int(body["max_tokens"]) * 2, 32000)    # try again with more room
    raise RuntimeError(problem + " Try again, or choose a different model in Settings > Integrations.")
