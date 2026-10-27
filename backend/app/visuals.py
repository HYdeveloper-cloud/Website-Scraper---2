"""Stage F: visual editor storage (canvas layouts + exported PNG), backups."""
import base64
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from . import backup
from .db import get_db
from .deps import audit
from .models import User, Visual
from .security import current_user

router = APIRouter()
from . import config

DIR = config.DATA_DIR / "visuals"
SLOTS = {"logo": (480, 140), "login_banner": (900, 700), "dashboard_header": (1280, 180),
         "report_header": (900, 140), "agent_image": (480, 480)}
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def slot_ok(slot: str):
    if slot not in SLOTS:
        raise HTTPException(404, "Unknown visual")


class SaveIn(BaseModel):
    layout: dict
    png: str          # data URL


@router.get("/api/visual-slots")
async def slots(_: User = Depends(current_user)):
    return {k: {"width": w, "height": h} for k, (w, h) in SLOTS.items()}


@router.post("/api/visuals/{slot}")
async def save_visual(slot: str, body: SaveIn, _: User = Depends(current_user), db: Session = Depends(get_db)):
    slot_ok(slot)
    els = body.layout.get("elements")
    if not isinstance(els, list) or len(els) > 60 or len(json.dumps(body.layout)) > 4_000_000:
        raise HTTPException(400, "This design is too large. Remove some elements or use smaller images.")
    try:
        data = base64.b64decode(body.png.split(",", 1)[1], validate=True)
    except Exception:
        raise HTTPException(400, "The exported image was not readable.")
    if not data.startswith(PNG_MAGIC) or len(data) > 3_000_000:
        raise HTTPException(400, "The exported image must be a PNG under 3 MB.")
    last = db.query(Visual).filter(Visual.slot == slot).order_by(Visual.version.desc()).first()
    ver = (last.version if last else 0) + 1
    DIR.mkdir(parents=True, exist_ok=True)
    (DIR / f"{slot}_{ver}.png").write_bytes(data)
    db.query(Visual).filter(Visual.slot == slot).update({Visual.active: False})
    db.add(Visual(slot=slot, version=ver, layout=body.layout, active=True))
    db.commit()
    for old in db.query(Visual).filter(Visual.slot == slot, Visual.version <= ver - 15).all():   # keep the last 15 versions
        (DIR / f"{slot}_{old.version}.png").unlink(missing_ok=True)
        db.delete(old)
    db.commit()
    audit(db, "visual_saved", f"{slot} v{ver}")
    return {"version": ver}


@router.get("/api/visuals/{slot}")
async def get_visual(slot: str, version: int = 0, _: User = Depends(current_user), db: Session = Depends(get_db)):
    slot_ok(slot)
    versions = db.query(Visual).filter(Visual.slot == slot).order_by(Visual.version.desc()).all()
    pick = next((v for v in versions if (v.version == version if version else v.active)), None)
    return {"slot": slot, "width": SLOTS[slot][0], "height": SLOTS[slot][1], "layout": pick.layout if pick else None,
            "versions": [{"version": v.version, "active": bool(v.active), "created_at": v.created_at.isoformat()} for v in versions]}


@router.post("/api/visuals/{slot}/activate/{version}")
async def activate(slot: str, version: int, _: User = Depends(current_user), db: Session = Depends(get_db)):
    slot_ok(slot)
    v = db.query(Visual).filter(Visual.slot == slot, Visual.version == version).first()
    if not v:
        raise HTTPException(404, "Version not found")
    db.query(Visual).filter(Visual.slot == slot).update({Visual.active: False})
    v.active = True
    db.commit()
    return {"ok": True}


@router.delete("/api/visuals/{slot}/active")
async def reset_visual(slot: str, _: User = Depends(current_user), db: Session = Depends(get_db)):
    slot_ok(slot)
    db.query(Visual).filter(Visual.slot == slot).update({Visual.active: False})
    db.commit()
    return {"ok": True}


@router.get("/api/public/visual/{slot}")
async def public_visual(slot: str, db: Session = Depends(get_db)):
    slot_ok(slot)
    v = db.query(Visual).filter(Visual.slot == slot, Visual.active.is_(True)).first()
    f = DIR / f"{slot}_{v.version}.png" if v else None
    if not f or not f.exists():
        raise HTTPException(404, "No custom visual")
    return FileResponse(f, media_type="image/png", headers={"Cache-Control": "no-cache"})


@router.get("/api/public/visuals")
async def active_visuals(db: Session = Depends(get_db)):
    return {v.slot: v.version for v in db.query(Visual).filter(Visual.active.is_(True)).all()}


@router.post("/api/backup")
async def make_backup(_: User = Depends(current_user)):
    try:
        return {"file": backup.run_backup()}
    except RuntimeError as e:
        raise HTTPException(400, str(e))


@router.get("/api/backups")
async def backups(_: User = Depends(current_user)):
    return backup.list_backups()
