"""First-start data: owner account, default settings, markets, HY Developer service catalog."""
from sqlalchemy.orm import Session

from . import config
from . import scoring
from .models import Market, Service, Setting, User
from .security import hash_password

DEFAULT_THEME = {"maroon": "#330908", "gold": "#C0A559", "ivory": "#F7F3E8", "ink": "#2A2220"}
DEFAULT_SETTINGS = {
    "theme": DEFAULT_THEME,
    "general": {"company_name": "HY Developer", "timezone": "Asia/Karachi", "currency": "USD"},
    "integrations": {"phone_numbers": []},
    "voice": {
        "agent_name": "HY Developer Sales Agent",
        "voices": {"en-US": "11labs-Adrian"},
        "call_language_by_market": {"AE": "en-US", "SA": "en-US", "GB": "en-US", "US": "en-US", "AU": "en-US"},
        "tone": "professional, warm and confident",
        "speed": 1.0,
        "opening": "Hello, am I speaking with someone at {{business_name}}? This is an AI assistant calling on behalf of {{company_name}}.",
        "script_notes": "",
        "objection_notes": "",
        "company_facts": "",
        "company_site": "https://hy-developer.com",
        "max_call_minutes": 6,
    },
    "calling": {
        "short_call_seconds": 15, "followup_count": 3, "followup_gap_hours": 24, "callback_default_hours": 24,
        "max_concurrent": 2, "daily_call_limit": 50, "daily_minutes_cap": 120, "cost_per_minute": 0.15,
    },
    "acquisition": {
        "stages": ["Lead", "Contacted", "Interested", "Meeting", "Proposal Submitted", "Negotiation", "Won", "Lost"],
        "monthly_target": 0,
    },
    "compliance": {"recording_notice_enabled": False, "recording_notice": "This call may be recorded for quality purposes."},
    "leads": {"default_market": "", "analyze_uploads": False},
    "scoring": scoring.DEFAULTS,
}

# Calling hours and weekends are starting points only. Confirm local rules for each market (Settings, Stage F).
MARKETS = [
    ("AE", "United Arab Emirates", "Asia/Dubai", "main", ["English", "Arabic"], ["Sat", "Sun"], "09:00", "18:00"),
    ("SA", "Saudi Arabia (KSA)", "Asia/Riyadh", "main", ["English", "Arabic"], ["Fri", "Sat"], "09:00", "18:00"),
    ("GB", "United Kingdom", "Europe/London", "secondary", ["English"], ["Sat", "Sun"], "09:00", "18:00"),
    ("US", "United States", "America/New_York", "secondary", ["English"], ["Sat", "Sun"], "09:00", "18:00"),
    ("AU", "Australia", "Australia/Sydney", "secondary", ["English"], ["Sat", "Sun"], "09:00", "18:00"),
]

SERVICES = [
    ("Website design and development",
     ["No website", "Outdated design", "Not mobile-friendly", "Slow loading", "Weak lead capture"],
     ["Missing site", "No mobile layout", "No HTTPS", "Slow load", "No contact form"],
     "A fast, modern website that turns visitors into enquiries."),
    ("WordPress and Laravel builds",
     ["Hard-to-update site", "Poor performance"], ["Old CMS or theme", "Broken pages"],
     "A site your team can update without calling a developer."),
    ("Mobile apps (Flutter)",
     ["Customers cannot book or order from a phone"], ["No app", "Booking by phone only"],
     "One app for iPhone and Android that lets customers book and order."),
    ("CRM and ERP systems",
     ["Leads and operations tracked on paper or spreadsheets"],
     ["Manual forms", "No customer portal", "Multiple branches"],
     "One system for customers, orders and operations."),
    ("Cloud deployment",
     ["Downtime", "Slow hosting", "No backups"], ["Hosting errors", "Slow response"],
     "Reliable hosting with backups and monitoring."),
    ("SaaS and automation tools",
     ["Repetitive manual work", "Missed follow-ups"],
     ["No online booking", "No chat or auto-reply", "Manual order handling"],
     "Automation that handles the repetitive work and never forgets a follow-up."),
    ("Business Suite (website, CRM and automation together)",
     ["Disconnected tools"], ["Several of the above at once"],
     "Website, CRM and automation delivered as one connected business engine."),
]


def seed_all(db: Session):
    if not db.query(User).first() and config.OWNER_EMAIL and config.OWNER_PASSWORD:
        if len(config.OWNER_PASSWORD) < 10:
            raise RuntimeError("OWNER_PASSWORD must be at least 10 characters.")
        db.add(User(email=config.OWNER_EMAIL, password_hash=hash_password(config.OWNER_PASSWORD)))
    for k, v in DEFAULT_SETTINGS.items():
        if not db.get(Setting, k):
            db.add(Setting(key=k, value=v))
    if not db.query(Market).first():
        for code, name, tz, pri, langs, wk, s, e in MARKETS:
            db.add(Market(code=code, name=name, timezone=tz, priority=pri, languages=langs,
                          weekend_days=wk, call_start=s, call_end=e))
    if not db.query(Service).first():
        for i, (name, pains, sigs, pitch) in enumerate(SERVICES):
            db.add(Service(name=name, pain_points=pains, signals=sigs, pitch=pitch, sort=i))
    db.commit()
