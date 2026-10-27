"""Discovery runs: by link, auto-find from Google Places, and re-analysis of one lead.
Runs work in the background inside the backend process and report progress through the discovery_runs table."""
import asyncio
import re
from datetime import datetime
from urllib.parse import urlparse

from . import diagnose as dg
from . import places
from .crawler import crawl
from .db import SessionLocal
from .models import DiscoveryRun, Lead, Service
from .netsafe import safe_public_url

COUNTRY = {"AE": "United Arab Emirates", "SA": "Saudi Arabia", "GB": "United Kingdom",
           "US": "United States", "AU": "Australia"}
TASKS: set = set()


def spawn(coro):
    t = asyncio.create_task(coro)
    TASKS.add(t)
    t.add_done_callback(TASKS.discard)


def domain_of(url: str) -> str:
    if not url:
        return ""
    p = urlparse(url if "//" in url else "https://" + url)
    return (p.hostname or "").removeprefix("www.").lower()


def clean_phone(p) -> str:
    return re.sub(r"[\s()\-.]", "", p or "")[:40]


def load_services(db) -> list[dict]:
    return [{"name": s.name, "pain_points": s.pain_points, "signals": s.signals, "pitch": s.pitch}
            for s in db.query(Service).order_by(Service.sort).all()]


def find_existing(db, domain: str, phone: str):
    if domain:
        l = db.query(Lead).filter(Lead.domain == domain).first()
        if l:
            return l
    if phone:
        return db.query(Lead).filter(Lead.phone == phone).first()
    return None


async def analyze_site(url: str, services: list[dict], max_pages: int, ctx: dict | None = None) -> dict:
    pages, contacts, checks = await crawl(url, max_pages)
    if not pages:
        host = (urlparse(url).hostname or "").lower()
        if host.endswith((".canva.site", ".wixsite.com", ".webflow.io", ".framer.website", ".framer.app")):
            raise RuntimeError("This website is built with a tool that draws its pages inside the browser (Canva, Wix, Webflow or Framer), so the program cannot read its text. "
                               "Add the business in Leads by hand, or look at the site yourself.")
        raise RuntimeError("No readable pages found. The site may need JavaScript to show its content, or it blocks automated visits.")
    return await dg.diagnose(pages, contacts, checks, services, ctx)


def lead_ctx(lead: Lead, cfg=None) -> dict:
    return {"rating": lead.rating, "reviews": lead.reviews, "phone": lead.phone, "market": lead.market_code or "",
            "industry": lead.industry or "", "contact_person": lead.contact_name or "", "cfg": cfg}


def load_cfg(db) -> dict:
    """Your scoring choices (Settings > Lead Scoring) laid over the defaults."""
    from . import scoring
    from .deps import get_setting
    return scoring.merge(get_setting(db, "scoring"), get_setting(db, "leads").get("target_industries"))


def apply_analysis(lead: Lead, a: dict):
    top = sorted(a["pains"], key=lambda p: -p["severity"])
    lead.pain_point = top[0]["pain"] if top else "No clear gap found"
    lead.hy_solution = a.get("recommended_service", "")
    lead.fit_score = a["fit_score"]
    lead.fit_band, lead.fit_conf = a["report"]["band"], a["report"]["confidence"]
    lead.analysis = a
    lead.checks = a.get("checks") or {}
    lead.analyzed_at = datetime.utcnow()
    if not lead.industry and a.get("industry"):
        lead.industry = a["industry"]
    if not lead.city and a.get("city"):
        lead.city = a["city"]


class Stats:
    def __init__(self):
        self.n = dict(found=0, added=0, updated=0, skipped=0, filtered=0, failed=0)
        self.note = ""
        self.errors: list[str] = []
        self.claimed: set[str] = set()

    def claim(self, *keys) -> bool:
        keys = [k for k in keys if k]
        if any(k in self.claimed for k in keys):
            return False
        self.claimed.update(keys)
        return True

    def error(self, msg: str):
        if len(self.errors) < 8:
            self.errors.append(msg[:240])

    def save(self, db, run, status=None):
        for k, v in self.n.items():
            setattr(run, k, v)
        run.note = self.note[:300]
        run.errors = self.errors
        if status:
            run.status = status
            run.finished_at = datetime.utcnow()
        db.commit()


async def run_link(run_id: int, url: str, market_code: str):
    db = SessionLocal()
    run = db.get(DiscoveryRun, run_id)
    st = Stats()
    try:
        st.note = "Reading the website"
        st.save(db, run)
        a = await analyze_site(url, load_services(db), 30, {"market": market_code, "cfg": load_cfg(db)})
        dom = domain_of(url)
        lead = db.query(Lead).filter(Lead.domain == dom).first()
        c = a["contact"]
        if lead:
            apply_analysis(lead, a)
            st.n["updated"] = 1
        else:
            lead = Lead(business_name=a["business_name"] or dom, website=url, domain=dom,
                        market_code=market_code or None, source="link", status="New", run_id=run_id,
                        phone=clean_phone((c.get("phones") or [""])[0]),
                        email=(c.get("emails") or [""])[0], contact_name=c.get("person", ""))
            apply_analysis(lead, a)
            db.add(lead)
            st.n["added"] = 1
        st.n["found"] = 1
        st.note = "Finished"
        st.save(db, run, "done")
    except Exception as e:
        db.rollback()
        st.error(str(e))
        st.note = "Stopped by an error"
        st.save(db, run, "error")
    finally:
        db.close()


async def process_place(db, st: Stats, run, pl: dict, p: dict, services: list[dict], cfg: dict):
    try:
        if p["min_rating"] and (pl["rating"] or 0) < p["min_rating"]:
            st.n["filtered"] += 1
            return
        website = pl["website"]
        if p["require_website"] and not website:
            st.n["filtered"] += 1
            return
        phone, dom = clean_phone(pl["phone"]), domain_of(website)
        if find_existing(db, dom, phone) or not st.claim(dom, phone):
            st.n["skipped"] += 1
            return
        st.note = f"Analyzing {pl['name']}"
        ctx = {"rating": pl["rating"], "reviews": pl["reviews"], "phone": phone, "market": p["market_code"], "industry": p["niche"], "cfg": cfg}
        if website:
            a = await analyze_site(safe_public_url(website), services, 12, ctx)
        else:
            a = dg.no_website(pl["name"], services, ctx)
        if a["fit_score"] < p["min_fit"]:
            st.n["filtered"] += 1
            return
        if find_existing(db, dom, phone):        # another task may have saved it while we were reading
            st.n["skipped"] += 1
            return
        c = a.get("contact") or {}
        lead = Lead(business_name=pl["name"] or dom, phone=phone or clean_phone((c.get("phones") or [""])[0]),
                    email=(c.get("emails") or [""])[0], website=website, domain=dom, city=p["city"],
                    market_code=p["market_code"], industry=p["niche"], source="auto", status="New",
                    rating=pl["rating"], reviews=pl["reviews"], run_id=run.id, contact_name=c.get("person", ""))
        apply_analysis(lead, a)
        db.add(lead)
        db.commit()
        st.n["added"] += 1
    except Exception as e:
        db.rollback()
        st.n["failed"] += 1
        st.error(f"{pl.get('name', '?')}: {e}")


async def run_auto(run_id: int, p: dict):
    db = SessionLocal()
    run = db.get(DiscoveryRun, run_id)
    st = Stats()
    try:
        st.note = "Searching Google Places"
        st.save(db, run)
        query = f"{p['niche']} in {p['city']}, {COUNTRY.get(p['market_code'], '')}".strip(", ")
        found = await places.search(query, p["market_code"], p["limit"])
        st.n["found"] = len(found)
        st.save(db, run)
        services, sem, cfg = load_services(db), asyncio.Semaphore(3), load_cfg(db)

        async def one(pl):
            async with sem:
                await process_place(db, st, run, pl, p, services, cfg)
                st.save(db, run)

        await asyncio.gather(*(one(x) for x in found))
        st.note = "Finished"
        st.save(db, run, "done")
    except Exception as e:
        db.rollback()
        st.error(str(e))
        st.note = "Stopped by an error"
        st.save(db, run, "error")
    finally:
        db.close()


async def run_analyze(run_id: int, lead_id: int):
    db = SessionLocal()
    run = db.get(DiscoveryRun, run_id)
    st = Stats()
    try:
        lead = db.get(Lead, lead_id)
        st.note = f"Analyzing {lead.business_name}"
        st.save(db, run)
        a = await analyze_site(safe_public_url(lead.website), load_services(db), 20, lead_ctx(lead, load_cfg(db)))
        apply_analysis(lead, a)
        st.n["found"], st.n["updated"], st.note = 1, 1, "Finished"
        st.save(db, run, "done")
    except Exception as e:
        db.rollback()
        st.error(str(e))
        st.note = "Stopped by an error"
        st.save(db, run, "error")
    finally:
        db.close()


async def run_analyze_many(run_id: int, lead_ids: list[int]):
    """Analyze many leads (used after an upload). Three at a time."""
    db = SessionLocal()
    run = db.get(DiscoveryRun, run_id)
    st = Stats()
    st.n["found"] = len(lead_ids)
    try:
        services, sem, cfg = load_services(db), asyncio.Semaphore(3), load_cfg(db)

        async def one(lid):
            async with sem:
                lead = db.get(Lead, lid)
                try:
                    st.note = f"Analyzing {lead.business_name}"
                    a = await analyze_site(safe_public_url(lead.website), services, 12, lead_ctx(lead, cfg))
                    apply_analysis(lead, a)
                    db.commit()
                    st.n["updated"] += 1
                except Exception as e:
                    db.rollback()
                    st.n["failed"] += 1
                    st.error(f"{lead.business_name if lead else lid}: {e}")
                st.save(db, run)

        await asyncio.gather(*(one(i) for i in lead_ids))
        st.note = "Finished"
        st.save(db, run, "done")
    except Exception as e:
        db.rollback()
        st.error(str(e))
        st.note = "Stopped by an error"
        st.save(db, run, "error")
    finally:
        db.close()
