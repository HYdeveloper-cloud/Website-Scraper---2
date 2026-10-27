from sqlalchemy.orm import Session

from .models import AuditLog, Setting


def audit(db: Session, action: str, detail: str = ""):
    db.add(AuditLog(action=action, detail=detail[:300]))
    db.commit()


def get_setting(db: Session, key: str) -> dict:
    row = db.get(Setting, key)
    return row.value if row else {}
