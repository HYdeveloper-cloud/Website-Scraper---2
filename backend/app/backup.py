"""Backups. Built-in database: a safe copy of the file. MySQL: mysqldump."""
import os
import shutil
import sqlite3
import subprocess
from datetime import datetime

from sqlalchemy.engine import make_url

from . import config

DIR = config.DATA_DIR / "backups"


def _url():
    return make_url(config.DB_URL)


def available() -> bool:
    return _url().drivername.startswith("sqlite") or bool(shutil.which("mysqldump"))


def run_backup() -> str:
    u = _url()
    DIR.mkdir(parents=True, exist_ok=True)
    stamp = f"{datetime.now():%Y%m%d_%H%M}"
    if u.drivername.startswith("sqlite"):
        out = DIR / f"hy_engine_{stamp}.db"
        src, dst = sqlite3.connect(u.database), sqlite3.connect(out)
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()
    elif u.drivername.startswith("mysql"):
        exe = shutil.which("mysqldump")
        if not exe:
            raise RuntimeError("mysqldump was not found on this computer. Install the MySQL client tools, or back up with your own tool.")
        out = DIR / f"hy_engine_{stamp}.sql"
        cmd = [exe, "-h", u.host or "127.0.0.1", "-P", str(u.port or 3306), "-u", u.username or "root", "--single-transaction", u.database]
        with open(out, "wb") as f:
            r = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, env={**os.environ, "MYSQL_PWD": u.password or ""}, timeout=300)
        if r.returncode != 0:
            out.unlink(missing_ok=True)
            raise RuntimeError("mysqldump failed: " + r.stderr.decode(errors="ignore")[:200])
    else:
        raise RuntimeError("Backups are not available for this database type.")
    for old in sorted(DIR.glob("hy_engine_*"))[:-14]:
        old.unlink()
    return out.name


def list_backups() -> list[str]:
    return sorted((p.name for p in DIR.glob("hy_engine_*")), reverse=True) if DIR.exists() else []


def maybe_daily(db):
    """Called every scheduler tick. One backup per day, after 02:00."""
    now = datetime.now()
    if now.hour < 2 or not available():
        return
    if any(n.startswith(f"hy_engine_{now:%Y%m%d}") for n in list_backups()):
        return
    try:
        run_backup()
    except Exception:
        pass
