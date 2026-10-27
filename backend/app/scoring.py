"""HY Developer evidence-first lead scoring (from the owner's scoring document), with every number editable in Settings > Lead Scoring.
Five factors, each rated 0 to 5. Points = rating / 5 x weight. Default weights: pain 50, service fit 25, evidence 15, buying signals 5, business fit 5.
Rules: no verified pain caps the score; if the key pain is only inferred, points are subtracted; a business type you avoid caps the score.
The score is a priority for outreach, NOT a probability that the business will buy."""
import copy
from datetime import date

from .phones import normalize

DEFAULTS = {
    "icp": {"target_industries": [], "avoid_industries": [], "target_markets": ["AE", "SA", "GB", "US", "AU"]},
    "weights": {"pain": 50, "fit": 25, "evidence": 15, "buying": 5, "business": 5},
    "rules": {"unverified_cap": 49, "inferred_penalty": 5, "avoid_cap": 39, "high_from": 80, "medium_from": 60,
              "verified_min_pain": 3, "verified_min_evidence": 3},
    "gap_points": {"low": 6, "medium": 12, "high": 20, "hypothesis_factor": 0.5},
    "pain_steps": [6, 12, 20, 32],
    "buying": {"one": 3, "two_or_more": 5},
    "business": {"both": 5, "type_only": 3, "market_only": 2, "neither": 1, "no_types_market_ok": 3, "no_types_other": 1},
}
NAMES = {"pain": "Pain point and impact", "fit": "HY service fit", "evidence": "Evidence quality", "buying": "Buying signals", "business": "Business fit"}
LABELS = ["None", "Very weak", "Weak", "Moderate", "Strong", "Very strong"]
BASIS_TEXT = {"measured": "Measured by the program", "verified": "Exact quote found on the page", "inferred": "AI inference, please confirm"}


def merge(saved: dict | None, legacy_targets: list | None = None) -> dict:
    """Your saved choices laid over the defaults, so a missing value never breaks scoring."""
    cfg = copy.deepcopy(DEFAULTS)
    for section, vals in (saved or {}).items():
        if section in cfg and isinstance(cfg[section], dict) and isinstance(vals, dict):
            cfg[section].update(vals)
        elif section in cfg:
            cfg[section] = vals
    if legacy_targets and not cfg["icp"]["target_industries"]:
        cfg["icp"]["target_industries"] = list(legacy_targets)
    return cfg


def sev_w(cfg, sev: int) -> float:
    g = cfg["gap_points"]
    return {1: g["low"], 2: g["medium"], 3: g["high"]}[sev]


def weight(g: dict, cfg: dict) -> float:
    return sev_w(cfg, g["severity"]) * (1.0 if g["direct"] else cfg["gap_points"]["hypothesis_factor"])


def bucket(s: float, steps) -> int:
    if s <= 0:
        return 0
    return 1 + sum(1 for x in steps if s >= x)           # below the first step is 1, at or above the last is 5


def priority_of(score: float, cfg: dict) -> str:
    r = cfg["rules"]
    return "High" if score >= r["high_from"] else "Medium" if score >= r["medium_from"] else "Low"


def build_report(gaps, already, signals, checks, ctx, industry, contacts, pages_read, dropped, listing_only=False, cfg=None) -> dict:
    cfg = cfg or merge(None)
    W, R, icp = cfg["weights"], cfg["rules"], cfg["icp"]
    direct = [g for g in gaps if g["direct"]]
    hyp = [g for g in gaps if not g["direct"]]
    key = max(gaps, key=lambda g: weight(g, cfg)) if gaps else None
    w_dir = sum(sev_w(cfg, g["severity"]) for g in direct)
    w_hyp = sum(sev_w(cfg, g["severity"]) for g in hyp) * cfg["gap_points"]["hypothesis_factor"]
    pain_r, dir_r = bucket(w_dir + w_hyp, cfg["pain_steps"]), bucket(w_dir, cfg["pain_steps"])
    why = {}

    why["pain"] = (f"{len(direct)} verified problem{'s' if len(direct) != 1 else ''} and {len(hyp)} to confirm. Strongest: {key['pain']}." if key else "No problem found.")

    if not key:
        fit_r = 0
    elif key["direct"]:
        fit_r = {3: 5, 2: 4, 1: 3}[key["severity"]]
    else:
        fit_r = 2 if key["basis"] == "measured" else 1
    svc = [g["service"] for g in direct]
    if svc and max(svc.count(s) for s in set(svc)) >= 2:
        fit_r = min(5, fit_r + 1)
    why["fit"] = (f"The strongest gap points to: {key['service']}." if key else "No clear service fit.")

    if not gaps:
        ev_r = 0
    elif direct:
        ev_r = 3 if (listing_only or pages_read < 3) else 4
        if ev_r == 4 and (any(g["basis"] == "verified" for g in direct) or (len(direct) >= 2 and pages_read >= 8)):
            ev_r = 5
    else:
        ev_r = 2 if any(g["basis"] == "measured" for g in hyp) else 1
    why["evidence"] = ("Based on a Google listing only." if listing_only else f"{pages_read} pages read; " + ("includes an exact quote from a page." if any(g["basis"] == "verified" for g in direct) else "findings are measured by the program." if direct else "nothing directly observed, only hypotheses."))

    n = len(signals)
    b = cfg["buying"]
    buy_r = b["two_or_more"] if (any(s.get("explicit") for s in signals) or n >= 2) else b["one"] if n == 1 else 0
    why["buying"] = f"{n} public signal{'s' if n != 1 else ''} found." if n else "No public buying signal found. This is 0, not a rejection."

    targets = [t.strip().lower() for t in icp["target_industries"] if t.strip()]
    avoid = [t.strip().lower() for t in icp["avoid_industries"] if t.strip()]
    market = (ctx.get("market") or "")
    market_ok = market in icp["target_markets"]
    ind = (ctx.get("industry") or industry or "").strip().lower()
    hit = lambda lst: bool(lst and ind and any(t in ind or ind in t for t in lst))
    match, avoided = hit(targets), hit(avoid)
    bz = cfg["business"]
    if targets:
        biz_r = bz["both"] if (match and market_ok) else bz["type_only"] if match else bz["market_only"] if market_ok else bz["neither"]
        why["business"] = ("Matches your target business types" if match else "Not in your target business types") + (" and a target market." if market_ok else " and not in a target market.")
    else:
        biz_r = bz["no_types_market_ok"] if market_ok else bz["no_types_other"]
        why["business"] = ("In a target market. " if market_ok else "Not in a target market. ") + "Add your target business types in Settings > Lead Scoring for a sharper rating."
    if avoided:
        biz_r = 0
        why["business"] = "This business type is on your avoid list."

    ratings = {}
    for k, r in (("pain", pain_r), ("fit", fit_r), ("evidence", ev_r), ("buying", buy_r), ("business", biz_r)):
        ratings[k] = {"name": NAMES[k], "rating": r, "label": LABELS[r], "weight": W[k], "points": round(r / 5 * W[k], 1), "why": why[k]}
    raw = round(sum(x["points"] for x in ratings.values()))
    adjustments, score = [], raw
    verified = dir_r >= R["verified_min_pain"] and ev_r >= R["verified_min_evidence"]
    if gaps and key and not key["direct"]:
        score = max(0, score - R["inferred_penalty"])
        adjustments.append({"label": "Key pain is only inferred (hypothesis)", "points": -R["inferred_penalty"]})
    if not verified and score > R["unverified_cap"]:
        adjustments.append({"label": f"No verified pain, so the score is capped at {R['unverified_cap']}", "points": R["unverified_cap"] - score})
        score = R["unverified_cap"]
    if avoided and score > R["avoid_cap"]:
        adjustments.append({"label": f"Business type on your avoid list, capped at {R['avoid_cap']}", "points": R["avoid_cap"] - score})
        score = R["avoid_cap"]
    pain_status = "UNVERIFIED" if not verified else "HYPOTHESIS" if (key and not key["direct"]) else "VERIFIED"
    prio = priority_of(score, cfg)

    conf = "High" if (ev_r >= 4 and pages_read >= 8) else "Medium" if ev_r >= 3 else "Low"
    conf_why = {"High": "Strong evidence from many pages.", "Medium": "Some direct evidence, but thin or from one source.", "Low": "Little direct evidence. Research more before relying on this."}[conf]

    phone = ctx.get("phone") or (contacts.get("phones") or [""])[0]
    missing = []
    if listing_only: missing.append("Whether the business really has no website. Google may not list one that exists. Search the name.")
    if not normalize(phone, market): missing.append("A valid phone number. The lead cannot be called yet.")
    if not contacts.get("emails"): missing.append("An email address.")
    if not ctx.get("contact_person"): missing.append("The name of the owner or decision maker.")
    if ctx.get("reviews") is None: missing.append("Google review data, which would show how active the business is.")
    if not n: missing.append("Any public sign they plan to improve, expand or hire.")
    if not targets: missing.append("Your target business types (Settings > Lead Scoring) to rate business fit properly.")
    if hyp: missing.append("Confirmation of: " + "; ".join(g["pain"].lower() for g in hyp[:3]) + ".")

    if key and verified and key["direct"]:
        angle = (f"Open with one verified observation: {key['pain'].lower()} ({key['evidence']}). Then ask a soft question, such as whether they are planning to improve it. "
                 "Do not say they are losing money or that it is urgent.")
    elif key:
        angle = f"No verified pain yet, so do not make a pain-based pitch. First confirm: {key['pain'].lower()}."
    else:
        angle = "No clear fit found. Hold this lead."
    caveats = []
    if dropped:
        caveats.append(f"{dropped} AI statement{'s were' if dropped > 1 else ' was'} left out because the quote could not be found on the page.")

    return {"method": "v3-evidence-first", "score": score, "raw_score": raw, "band": prio, "priority": f"{prio} priority", "confidence": conf, "confidence_why": conf_why,
            "pain_status": pain_status, "ratings": ratings, "adjustments": adjustments, "gaps": gaps, "already_has": already, "buying_signals": signals,
            "missing_information": missing, "angle": angle, "caveats": caveats, "checked_at": date.today().isoformat(),
            "inputs": {"pages_read": pages_read, "dropped": dropped, "listing_only": listing_only},
            "verdict": f"{prio} priority, {score} out of 100. Pain: {pain_status.lower()}. Confidence: {conf.lower()}. This is a priority for outreach, not a chance to buy."}
