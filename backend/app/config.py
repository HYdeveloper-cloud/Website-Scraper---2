import os
import secrets
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _data_dir() -> Path:
    custom = os.getenv("HY_DATA_DIR")
    if custom:
        d = Path(custom)
    elif getattr(sys, "frozen", False):                    # the packaged Windows app keeps its data in the user's profile
        d = Path(os.getenv("APPDATA") or Path.home() / ".local" / "share") / "HYSalesEngine"
    else:
        d = Path(__file__).resolve().parent.parent / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


DATA_DIR = _data_dir()
# Built-in database file by default: nothing to install. Set DATABASE_URL (mysql+pymysql://...) to use MySQL instead.
DB_URL = os.getenv("DATABASE_URL") or f"sqlite:///{(DATA_DIR / 'hy_engine.db').as_posix()}"
OWNER_EMAIL = os.getenv("OWNER_EMAIL", "").strip().lower()      # optional: otherwise you create the account on first start
OWNER_PASSWORD = os.getenv("OWNER_PASSWORD", "")
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")
TOKEN_HOURS = int(os.getenv("TOKEN_HOURS", "12"))

SECRET_KEY = os.getenv("SECRET_KEY", "")
if len(SECRET_KEY) < 32:                                          # generated once and kept next to the database
    _kf = DATA_DIR / "secret.key"
    SECRET_KEY = _kf.read_text().strip() if _kf.exists() else ""
    if len(SECRET_KEY) < 32:
        SECRET_KEY = secrets.token_hex(32)
        _kf.write_text(SECRET_KEY)

# Development and testing only: allow analyzing sites on private addresses (never turn on for real use).
ALLOW_PRIVATE_URLS = os.getenv("ALLOW_PRIVATE_URLS", "0") == "1"
