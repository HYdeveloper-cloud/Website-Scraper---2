"""API keys entered in Settings. Stored encrypted in the database, loaded into this process, never sent back to the browser."""
import base64
import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from .config import SECRET_KEY
from .models import Setting

SECRET_KEYS = ["LLM_API_KEY", "GOOGLE_PLACES_API_KEY", "RETELL_API_KEY"]
PLAIN = ["LLM_BASE_URL", "LLM_MODEL"]
DEFAULT_BASE = "https://generativelanguage.googleapis.com/v1beta/openai"
DEFAULT_MODEL = "gemini-2.5-flash"


def _fernet() -> Fernet:
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(SECRET_KEY.encode()).digest()))


def load_into_env(db: Session):
    row = db.get(Setting, "secrets")
    for k, tok in (row.value if row else {}).items():
        if k in SECRET_KEYS:
            try:
                os.environ[k] = _fernet().decrypt(tok.encode()).decode()
            except InvalidToken:
                pass
        elif k in PLAIN:
            os.environ[k] = tok


def save(db: Session, updates: dict, clear: list):
    row = db.get(Setting, "secrets")
    data = dict(row.value) if row else {}
    for k, v in updates.items():
        v = str(v or "").strip()
        if k not in SECRET_KEYS + PLAIN or not v:
            continue
        if k in SECRET_KEYS:
            if len(v) < 8 or len(v) > 400 or any(c.isspace() for c in v):
                raise ValueError(f"That {k.replace('_', ' ').lower()} does not look right. Paste it again without spaces.")
            data[k] = _fernet().encrypt(v.encode()).decode()
            os.environ[k] = v
        elif k == "LLM_BASE_URL":
            if not v.startswith(("https://", "http://localhost", "http://127.0.0.1")):
                raise ValueError("The language model address must start with https://")
            data[k] = os.environ[k] = v.rstrip("/")
        else:
            data[k] = os.environ[k] = v[:80]
    for k in clear:
        if k in SECRET_KEYS + PLAIN:
            data.pop(k, None)
            os.environ.pop(k, None)
    if row:
        row.value = data
    else:
        db.add(Setting(key="secrets", value=data))
    db.commit()


def status() -> dict:
    out = {}
    for k in SECRET_KEYS:
        v = os.getenv(k, "")
        out[k] = {"set": bool(v), "hint": ("\u2022\u2022\u2022\u2022" + v[-4:]) if len(v) >= 8 else ""}
    return {"keys": out, "llm_base_url": os.getenv("LLM_BASE_URL", DEFAULT_BASE), "llm_model": os.getenv("LLM_MODEL", DEFAULT_MODEL)}
