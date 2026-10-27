"""Same-domain crawler. Reads pages, collects contacts, and runs the technical checks
that feed the pain-point engine (HTTPS, mobile layout, speed, forms, booking, chat, apps, platform)."""
import asyncio
import re
import time
from datetime import datetime
from urllib.parse import urljoin, urlparse, urldefrag

import httpx
from bs4 import BeautifulSoup

UA = "Mozilla/5.0 (compatible; HYSalesEngineBot/1.0)"
SKIP_EXT = (".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".pdf", ".zip", ".mp4", ".mp3",
            ".css", ".js", ".ico", ".woff", ".woff2", ".xml", ".json")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"\+?\d[\d\s().-]{8,}\d")
BOOKING_RE = re.compile(r"book(ing)?\s*(an?\s*)?(online|now|appointment|a\s+(table|room|slot|call|visit|demo))"
                        r"|appointment|reserve|calendly|schedule\s+(a|your)\s+\w+|\u062d\u062c\u0632", re.I)
CHAT_TOKENS = ("tawk.to", "intercom", "drift.com", "crisp.chat", "livechatinc", "tidio", "zopim",
               "olark", "wa.me/", "api.whatsapp.com", "wa.link")
CMS_MARKERS = [("WordPress", ("wp-content", "wordpress")), ("Wix", ("wixstatic", "wix.com")),
               ("Squarespace", ("squarespace",)), ("Shopify", ("cdn.shopify", "shopify")),
               ("Joomla", ("joomla",)), ("Drupal", ("drupal",)), ("Webflow", ("webflow",))]
COPYRIGHT_RE = re.compile(r"(?:\u00a9|&copy;|copyright)\s*(?:20\d{2}\s*[-\u2013]\s*)?(20\d{2})", re.I)


def host(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def normalize(url: str) -> str:
    url, _ = urldefrag(url)
    p = urlparse(url)
    return p._replace(query="", path=p.path.rstrip("/") or "/").geturl()


def page_type(url: str) -> str:
    path = urlparse(url).path.lower()
    if path in ("", "/"):
        return "home"
    for kind, keys in (("contact", ("contact",)), ("about", ("about", "team", "who-we-are")),
                       ("blog", ("blog", "news", "article")), ("portfolio", ("portfolio", "work", "project", "case")),
                       ("services", ("service", "solution", "product", "pricing", "treatment", "menu"))):
        if any(k in path for k in keys):
            return kind
    return "other"


def detect_cms(low: str, soup: BeautifulSoup):
    gen = soup.find("meta", attrs={"name": "generator"})
    blob = ((gen.get("content", "") if gen else "") + " " + low).lower()
    for name, marks in CMS_MARKERS:
        if any(m in blob for m in marks):
            return name
    return None


def has_real_form(soup: BeautifulSoup) -> bool:
    for f in soup.find_all("form"):
        if (f.get("role") or "").lower() == "search":
            continue
        if f.find("textarea") or f.find("input", attrs={"type": ["email", "tel"]}):
            return True
    return False


def contacts_from(html: str, soup: BeautifulSoup):
    emails, phones = set(), set()
    for a in soup.find_all("a", href=True):
        h = a["href"].strip()
        if h.startswith("mailto:"):
            emails.add(h[7:].split("?")[0].lower())
        elif h.startswith("tel:"):
            phones.add(h[4:].strip())
    emails.update(e.lower() for e in EMAIL_RE.findall(html) if not e.lower().endswith((".png", ".jpg", ".webp", ".svg")))
    for m in PHONE_RE.findall(soup.get_text(" ")):
        if 9 <= len(re.sub(r"\D", "", m)) <= 15:
            phones.add(m.strip())
    return emails, phones


async def fetch(client: httpx.AsyncClient, url: str):
    t0 = time.perf_counter()
    try:
        r = await client.get(url)
        ms = int((time.perf_counter() - t0) * 1000)
        if r.status_code == 200 and "text/html" in r.headers.get("content-type", ""):
            return r.text, ms, str(r.url)
    except httpx.HTTPError:
        pass
    return None, 0, url


async def sitemap_urls(client, root: str, limit: int = 200):
    found, queue, seen = [], [urljoin(root, "/sitemap.xml")], set()
    while queue and len(found) < limit and len(seen) < 4:
        sm = queue.pop(0)
        if sm in seen:
            continue
        seen.add(sm)
        try:
            r = await client.get(sm)
        except httpx.HTTPError:
            continue
        if r.status_code == 200:
            for loc in re.findall(r"<loc>\s*(.*?)\s*</loc>", r.text):
                (queue if loc.endswith(".xml") else found).append(loc)
    return found


async def crawl(start_url: str, max_pages: int = 25):
    """Returns (pages, contacts, checks). pages: [{url,title,type,text,words}]."""
    start_url = normalize(start_url)
    base = host(start_url)
    pages, emails, phones = [], set(), set()
    checks = {"https": None, "response_ms": None, "mobile_viewport": None, "contact_form": False,
              "booking_found": False, "chat_or_whatsapp": False, "app_links": False,
              "cms": None, "copyright_year": None, "pages_read": 0, "refs": {}, "pages": [], "home_url": None}
    years, first = [], True
    visited, queue = set(), [start_url]
    sem = asyncio.Semaphore(5)

    def mark(name, cond, url):                  # remember the first page where each thing was found
        if cond and not checks[name]:
            checks["refs"][name] = url
        checks[name] = bool(checks[name] or cond)

    async with httpx.AsyncClient(headers={"User-Agent": UA}, timeout=15, follow_redirects=True) as client:
        for u in await sitemap_urls(client, start_url):
            u = normalize(u)
            if host(u) == base and not u.lower().endswith(SKIP_EXT):
                queue.append(u)

        async def work(u):
            async with sem:
                return (u, *await fetch(client, u))

        while queue and len(pages) < max_pages:
            batch = []
            while queue and len(batch) < 6 and len(visited) < max_pages * 3:
                u = queue.pop(0)
                if u not in visited:
                    visited.add(u)
                    batch.append(u)
            if not batch:
                break
            for url, html, ms, final in await asyncio.gather(*(work(u) for u in batch)):
                if not html or len(pages) >= max_pages:
                    continue
                soup = BeautifulSoup(html, "lxml")
                low = html.lower()
                e, p = contacts_from(html, soup)
                emails |= e
                phones |= p
                if first:
                    first = False
                    checks["https"] = final.startswith("https://")
                    checks["home_url"] = final
                    checks["response_ms"] = ms
                    checks["mobile_viewport"] = soup.find("meta", attrs={"name": "viewport"}) is not None
                    checks["cms"] = detect_cms(low, soup)
                mark("contact_form", has_real_form(soup), url)
                hrefs = " ".join(a["href"] for a in soup.find_all("a", href=True))
                visible = soup.get_text(" ")
                mark("booking_found", bool(BOOKING_RE.search(visible) or BOOKING_RE.search(hrefs)), url)
                mark("chat_or_whatsapp", any(t in low for t in CHAT_TOKENS), url)
                mark("app_links", ("apps.apple.com" in low or "play.google.com" in low), url)
                years += [int(y) for y in COPYRIGHT_RE.findall(visible)]
                for a in soup.find_all("a", href=True):
                    link = normalize(urljoin(url, a["href"]))
                    if (link.startswith("http") and host(link) == base and not link.lower().endswith(SKIP_EXT)
                            and link not in visited):
                        queue.append(link)
                title = soup.title.get_text(strip=True) if soup.title else ""
                for t in soup(["script", "style", "noscript", "svg", "iframe"]):
                    t.decompose()
                text = re.sub(r"\n{3,}", "\n\n", soup.get_text("\n", strip=True))
                if len(text) < 80:
                    continue
                pages.append({"url": url, "title": title, "type": page_type(url), "text": text, "words": len(text.split())})
                checks["pages"].append(url)
    checks["pages_read"] = len(pages)
    checks["copyright_year"] = max(years) if years else None
    return pages, {"emails": sorted(emails)[:10], "phones": sorted(phones)[:10]}, checks
