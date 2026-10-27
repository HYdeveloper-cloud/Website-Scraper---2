from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, Float, Integer, String, Text, UniqueConstraint

from .db import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String(190), unique=True, nullable=False)
    password_hash = Column(String(300), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Setting(Base):
    __tablename__ = "settings"
    key = Column(String(60), primary_key=True)
    value = Column(JSON, nullable=False)


class Market(Base):
    __tablename__ = "markets"
    id = Column(Integer, primary_key=True)
    code = Column(String(4), unique=True, nullable=False)
    name = Column(String(80), nullable=False)
    timezone = Column(String(60), nullable=False)
    priority = Column(String(12), nullable=False)       # main | secondary
    languages = Column(JSON, nullable=False)
    weekend_days = Column(JSON, nullable=False)
    call_start = Column(String(5), nullable=False)
    call_end = Column(String(5), nullable=False)
    active = Column(Boolean, default=True)


class Service(Base):
    __tablename__ = "services"
    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    pain_points = Column(JSON, nullable=False)
    signals = Column(JSON, nullable=False)
    pitch = Column(Text, nullable=False)
    sort = Column(Integer, default=0)


class Lead(Base):
    __tablename__ = "leads"
    id = Column(Integer, primary_key=True)
    business_name = Column(String(190), nullable=False)
    contact_name = Column(String(120))
    phone = Column(String(40))
    email = Column(String(190))
    website = Column(String(250))
    domain = Column(String(190), index=True)
    city = Column(String(80))
    market_code = Column(String(4), index=True)
    industry = Column(String(120))
    source = Column(String(20), default="manual")         # manual | link | auto | upload | demo
    fit_score = Column(Integer)
    status = Column(String(30), default="New", index=True)
    pain_point = Column(Text)
    hy_solution = Column(String(190))
    notes = Column(Text)
    analysis = Column(JSON)
    checks = Column(JSON)
    analyzed_at = Column(DateTime)
    rating = Column(Float)
    run_id = Column(Integer)
    tags = Column(String(300))
    reviews = Column(Integer)
    fit_band = Column(String(12))
    fit_conf = Column(String(8))
    created_at = Column(DateTime, default=datetime.utcnow)


class DiscoveryRun(Base):
    __tablename__ = "discovery_runs"
    id = Column(Integer, primary_key=True)
    mode = Column(String(12), nullable=False)             # link | auto | analyze
    params = Column(JSON)
    status = Column(String(14), default="running")        # running | done | error | interrupted
    found = Column(Integer, default=0)
    added = Column(Integer, default=0)
    updated = Column(Integer, default=0)
    skipped = Column(Integer, default=0)
    filtered = Column(Integer, default=0)
    failed = Column(Integer, default=0)
    note = Column(String(300))
    errors = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(Integer, primary_key=True)
    at = Column(DateTime, default=datetime.utcnow)
    action = Column(String(60), nullable=False)
    detail = Column(String(300))


class DNC(Base):
    __tablename__ = "dnc"
    id = Column(Integer, primary_key=True)
    phone = Column(String(40), unique=True, nullable=False)
    reason = Column(String(200))
    added_at = Column(DateTime, default=datetime.utcnow)


class Campaign(Base):
    __tablename__ = "campaigns"
    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    status = Column(String(14), default="active")        # active | paused | cancelled | completed
    start_at = Column(DateTime)                           # UTC; null means started immediately
    params = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)


class CallTask(Base):
    """One planned call. First calls, follow-ups and callbacks are all tasks."""
    __tablename__ = "call_tasks"
    id = Column(Integer, primary_key=True)
    lead_id = Column(Integer, index=True)
    campaign_id = Column(Integer, index=True)
    kind = Column(String(10), default="first")            # first | followup | callback
    attempt = Column(Integer, default=0)                  # 0 first call, 1..n follow-ups
    due_at = Column(DateTime, index=True)                 # UTC
    status = Column(String(12), default="pending", index=True)   # pending | done | blocked | cancelled
    note = Column(String(300))
    created_at = Column(DateTime, default=datetime.utcnow)


class Call(Base):
    __tablename__ = "calls"
    id = Column(Integer, primary_key=True)
    lead_id = Column(Integer, index=True)                 # null for test calls
    campaign_id = Column(Integer)
    task_id = Column(Integer)
    kind = Column(String(10), default="first")
    attempt = Column(Integer, default=0)
    retell_call_id = Column(String(80), index=True)
    status = Column(String(12), default="registered", index=True)   # registered | ongoing | ended | error
    language = Column(String(10))
    to_number = Column(String(40))
    started_at = Column(DateTime)
    ended_at = Column(DateTime)
    duration_s = Column(Integer, default=0)
    disconnection_reason = Column(String(60))
    transcript = Column(Text)
    recording_url = Column(String(500))
    summary = Column(Text)
    outcome = Column(String(24), index=True)
    meeting_when = Column(String(120))
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class AgentRec(Base):
    __tablename__ = "agents"
    id = Column(Integer, primary_key=True)
    language = Column(String(10), unique=True, nullable=False)
    retell_agent_id = Column(String(80), nullable=False)
    retell_llm_id = Column(String(80), nullable=False)
    kb_id = Column(String(80))
    voice_id = Column(String(80))
    built_at = Column(DateTime, default=datetime.utcnow)


class Deal(Base):
    __tablename__ = "deals"
    id = Column(Integer, primary_key=True)
    lead_id = Column(Integer, index=True)
    service = Column(String(190))
    stage = Column(String(40), nullable=False, index=True)
    value = Column(Float, default=0)
    final_value = Column(Float)
    proposal_date = Column(DateTime)
    expected_close = Column(DateTime)
    closed_at = Column(DateTime)
    lost_reason = Column(String(200))
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class Visual(Base):
    __tablename__ = "visuals"
    id = Column(Integer, primary_key=True)
    slot = Column(String(30), index=True, nullable=False)
    version = Column(Integer, nullable=False)
    layout = Column(JSON, nullable=False)
    active = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
