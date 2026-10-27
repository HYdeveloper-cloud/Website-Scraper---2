from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import DB_URL

_sqlite = DB_URL.startswith("sqlite")
engine = create_engine(DB_URL, pool_pre_ping=True,
                       connect_args={"check_same_thread": False, "timeout": 30} if _sqlite else {})
if _sqlite:
    @event.listens_for(engine, "connect")
    def _pragmas(con, _):
        cur = con.cursor()
        cur.execute("PRAGMA journal_mode=WAL")      # the scheduler and the screens can use the file at the same time
        cur.execute("PRAGMA busy_timeout=30000")
        cur.close()
SessionLocal = sessionmaker(bind=engine, autoflush=False)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
