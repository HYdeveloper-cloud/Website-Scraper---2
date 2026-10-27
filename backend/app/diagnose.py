"""Pain-point engine. Step 1: read every page and measure the site in code. Step 2: the AI finds gaps and must quote the page.
Step 3: the program checks each quote really exists on that page, then scores the lead (see scoring.py)."""
import re
from datetime import datetime

from . import llm, scoring

SYSTEM = """You are a careful business analyst for HY Developer, a software agency that builds websites, mobile apps,
CRM/ERP systems, cloud deployments, SaaS products and automation tools.
You receive a prospect's website pages (each with its URL), technical measurements, and HY Developer's service catalog.
Work in this order: understand the business, find what it already has, then find gaps HY Developer could solve.

Rules:
- For a gap that is visible on a page, give "basis":"quote", the exact words copied from that page (8 to 30 words, unchanged), and that page's URL.
  The program will search the page for your quote. A quote that is not found is thrown away, so never paraphrase.
- For a gap that is an absence (something a business like this normally has but you did not see), use "basis":"absent" and say what you looked for in "note". No quote.
- Never claim anything about revenue, staff numbers, prices or customer opinions.
- Do not repeat anything in "already_measured". "service" must be copied exactly from the catalog names.
- severity: 3 = costs them customers now, 2 = clear gap, 1 = minor.
- "already_has": useful things the business already has that reduce the need for our services. Quote the page.
- "buying_signals": public signs the business plans to improve or grow (expansion, hiring, a new location, a stated plan to improve, an explicit request for a solution). Quote the page. "explicit": true only if they ask for a solution.
Return ONLY JSON:
{"business_name":"","industry":"","city":"","summary":"2 plain sentences","offers":["what the business sells"],
 "contact":{"person":""},
 "gaps":[{"pain":"","service":"","severity":2,"basis":"quote","quote":"","url":"","note":""}],
 "already_has":[{"item":"","quote":"","url":""}],
 "buying_signals":[{"signal":"","quote":"","url":"","explicit":false}],
 "talking_points":["three short, specific lines a caller could say, each based on a gap above"]}"""


def norm(t: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[\u201c\u201d\"'\u2019`]", "", t or "")).strip().lower()


def find_quote(quote: str, url: str, pages: list[dict]):
    q = norm(quote)
    if len(q) < 12:
        return None
    by = {p["url"]: p for p in pages}
    if url in by and q in by[url]["norm"]:
        return url
    return next((p["url"] for p in pages if q in p["norm"]), None)


def measured_gaps(checks: dict, web_service: str) -> list[dict]:
    home, searched = checks.get("home_url"), (checks.get("pages") or [])[:12]
    out = []

    def add(pain, evidence, sev, url=None, urls=None, direct=True):
        out.append({"pain": pain, "service": web_service, "severity": sev, "basis": "measured", "direct": direct, "evidence": evidence,
                    "quote": "", "url": url, "urls_checked": urls or []})

    if checks.get("https") is False:
        add("Website is not secure", "The site loads without HTTPS, so browsers can warn visitors.", 2, home)
    if checks.get("mobile_viewport") is False:
        add("Not built for mobile phones", "No mobile viewport setting was found on the home page.", 2, home)
    ms = checks.get("response_ms")
    if ms and ms > 3000:
        add("Slow website", f"The home page took {ms / 1000:.1f} seconds to respond when tested from this computer.", 1, home)
    if not checks.get("contact_form"):
        add("Weak lead capture", f"No contact or enquiry form was found on any of the {checks.get('pages_read', 0)} pages read. A missing feature is a hypothesis, not proof of harm.", 1, None, searched, direct=False)
    yr = checks.get("copyright_year")
    if yr and yr <= datetime.now().year - 3:
        add("Site looks outdated", f"The footer shows a copyright year of {yr}.", 1, home)
    return out


def measured_has(checks: dict) -> list[dict]:
    refs, out = checks.get("refs") or {}, []
    def has(item, url=None): out.append({"item": item, "url": url, "basis": "measured"})
    if checks.get("https"): has("Secure connection (HTTPS)", checks.get("home_url"))
    if checks.get("mobile_viewport"): has("Mobile layout set", checks.get("home_url"))
    if checks.get("contact_form"): has("Contact or enquiry form", refs.get("contact_form"))
    if checks.get("booking_found"): has("Booking wording or link", refs.get("booking_found"))
    if checks.get("chat_or_whatsapp"): has("Chat or WhatsApp button", refs.get("chat_or_whatsapp"))
    if checks.get("app_links"): has("Mobile app store links", refs.get("app_links"))
    if checks.get("cms"): has(f"Platform: {checks['cms']}", checks.get("home_url"))
    return out


def no_website(name: str, services: list[dict], ctx: dict) -> dict:
    web = services[0]["name"]
    gaps = [{"pain": "No website", "service": web, "severity": 3, "basis": "measured", "direct": True, "quote": "", "url": None, "urls_checked": [],
             "evidence": "Google lists this business without a website."}]
    return _finish(name, "", "", f"{name} has no website listed on Google.", [], {}, gaps, [], [
        "Customers searching online cannot find a website for the business.",
        "A simple site would let them show services, hours and contact details.",
        "It also gives an address to put on Google and social profiles."], {"emails": [], "phones": []}, "", ctx, services, 0, 0, listing_only=True)


def _finish(name, industry, city, summary, offers, checks, gaps, already, points, contacts, person, ctx, services, pages_read, dropped, listing_only=False, signals=None):
    cfg = ctx.get("cfg") or scoring.merge(None)
    rep = scoring.build_report(gaps, already, signals or [], checks, {**ctx, "contact_person": person or ctx.get("contact_person")}, industry, contacts, pages_read, dropped, listing_only, cfg)
    pains = [{"pain": g["pain"], "evidence": g["evidence"], "service": g["service"], "severity": g["severity"], "basis": g["basis"], "direct": g["direct"], "url": g.get("url")} for g in gaps]
    rec = recommend(gaps, services, cfg)
    return {"business_name": name[:190], "industry": industry[:120], "city": city[:80], "summary": summary[:600], "offers": [str(o)[:100] for o in offers][:8],
            "pains": pains, "talking_points": [str(t)[:200] for t in points][:4], "recommended_service": rec, "fit_score": rep["score"],
            "report": rep, "contact": {"person": person[:120], "emails": contacts.get("emails", []), "phones": contacts.get("phones", [])}, "checks": checks}


def recommend(gaps: list[dict], services: list[dict], cfg: dict) -> str:
    if not gaps:
        return ""
    if len({g["service"] for g in gaps}) >= 3:
        suite = next((s["name"] for s in services if s["name"].lower().startswith("business suite")), None)
        if suite:
            return suite
    return max(gaps, key=lambda g: scoring.weight(g, cfg))["service"]


async def diagnose(pages: list[dict], contacts: dict, checks: dict, services: list[dict], ctx: dict | None = None) -> dict:
    ctx = ctx or {}
    names = [s["name"] for s in services]
    det = measured_gaps(checks, names[0])
    for p in pages:
        p["norm"] = norm(p["text"])
    order = {"home": 0, "about": 1, "services": 2, "portfolio": 3, "contact": 4, "blog": 5, "other": 6}
    corpus, total = [], 0
    for p in sorted(pages, key=lambda p: order.get(p["type"], 9)):
        chunk = f"### [{p['type']}] {p['title']}\nURL: {p['url']}\n{p['text'][:2500]}\n"
        if total + len(chunk) > 60_000:
            break
        corpus.append(chunk)
        total += len(chunk)
    catalog = [{"name": s["name"], "problems": s["pain_points"], "signals": s["signals"]} for s in services]
    user = (f"SERVICE CATALOG:\n{catalog}\n\nTECHNICAL MEASUREMENTS: {checks}\n"
            f"already_measured: {[g['pain'] for g in det] + [h['item'] for h in measured_has(checks)]}\n\nWEBSITE PAGES:\n" + "\n".join(corpus))
    data = await llm.complete_json(SYSTEM, user, 4500)

    lower, dropped, content, seen = {n.lower(): n for n in names}, 0, [], set()
    for g in data.get("gaps", []):
        svc, pain = lower.get(str(g.get("service", "")).lower()), str(g.get("pain", "")).strip()
        if not svc or not pain or pain.lower() in seen:
            continue
        sev = g.get("severity") if g.get("severity") in (1, 2, 3) else 1
        if g.get("basis") == "quote":
            url = find_quote(str(g.get("quote", "")), str(g.get("url", "")), pages)
            if not url:
                dropped += 1                                        # honesty rule: no verifiable quote, no gap
                continue
            content.append({"pain": pain[:140], "service": svc, "severity": sev, "basis": "verified", "direct": True, "quote": str(g["quote"]).strip()[:400],
                            "evidence": "\u201c" + str(g["quote"]).strip()[:400] + "\u201d", "url": url, "urls_checked": []})
        else:
            note = str(g.get("note", "")).strip() or "Not seen on the pages read."
            content.append({"pain": pain[:140], "service": svc, "severity": sev, "basis": "inferred", "direct": False, "quote": "", "evidence": note[:300],
                            "url": None, "urls_checked": [p["url"] for p in pages][:12]})
        seen.add(pain.lower())
    gaps = (det + content)[:8]

    already = measured_has(checks)
    for h in data.get("already_has", []):
        url = find_quote(str(h.get("quote", "")), str(h.get("url", "")), pages)
        if url and str(h.get("item", "")).strip():
            already.append({"item": str(h["item"]).strip()[:120], "url": url, "basis": "verified", "quote": str(h["quote"]).strip()[:300]})
    c = data.get("contact") or {}
    signals = []
    for b in data.get("buying_signals", []):
        url = find_quote(str(b.get("quote", "")), str(b.get("url", "")), pages)
        if url and str(b.get("signal", "")).strip():
            signals.append({"signal": str(b["signal"]).strip()[:140], "quote": str(b["quote"]).strip()[:300], "url": url, "explicit": bool(b.get("explicit"))})
    return _finish(str(data.get("business_name", "")), str(data.get("industry", "")), str(data.get("city", "")), str(data.get("summary", "")),
                   data.get("offers", []), checks, gaps, already, data.get("talking_points", []), contacts, str(c.get("person", "")),
                   ctx, services, checks.get("pages_read", len(pages)), dropped, signals=signals)
