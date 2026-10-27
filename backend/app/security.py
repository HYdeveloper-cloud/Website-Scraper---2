import hashlib
import hmac
import os
import time
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from .config import SECRET_KEY, TOKEN_HOURS
from .db import get_db
from .models import User

ITER = 390_000


def hash_password(pw: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, ITER)
    return f"pbkdf2${salt.hex()}${dk.hex()}"


def verify_password(pw: str, stored: str) -> bool:
    try:
        _, salt, dk = stored.split("$")
        new = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), ITER)
        return hmac.compare_digest(new.hex(), dk)
    except ValueError:
        return False


def make_token(user_id: int) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=TOKEN_HOURS)
    return jwt.encode({"sub": str(user_id), "exp": exp}, SECRET_KEY, algorithm="HS256")


def current_user(authorization: str = Header(default=""), db: Session = Depends(get_db)) -> User:
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Not signed in")
    try:
        data = jwt.decode(authorization[7:], SECRET_KEY, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(401, "Session expired. Sign in again.")
    user = db.get(User, int(data["sub"]))
    if not user:
        raise HTTPException(401, "Not signed in")
    return user


# Simple lockout: 5 wrong passwords in 5 minutes blocks that address for the rest of the window.
_fails: dict[str, list[float]] = {}


def check_throttle(ip: str):
    now = time.time()
    recent = [t for t in _fails.get(ip, []) if now - t < 300]
    _fails[ip] = recent
    if len(recent) >= 5:
        raise HTTPException(429, "Too many wrong attempts. Wait 5 minutes and try again.")


def record_fail(ip: str):
    _fails.setdefault(ip, []).append(time.time())


def clear_fails(ip: str):
    _fails.pop(ip, None)
