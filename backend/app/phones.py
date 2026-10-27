import re

CC = {"AE": "971", "SA": "966", "GB": "44", "AU": "61", "US": "1"}
PREFIX_MARKET = [("+971", "AE"), ("+966", "SA"), ("+44", "GB"), ("+61", "AU"), ("+1", "US")]


def normalize(raw, market: str = "") -> str | None:
    """Returns E.164 (+9715...) or None if the number cannot be trusted."""
    s = re.sub(r"[^\d+]", "", str(raw or ""))
    if not s:
        return None
    if s.startswith("00"):
        s = "+" + s[2:]
    if s.startswith("+"):
        digits = s[1:]
    else:
        digits = s
        cc = CC.get(market)
        if not cc:
            return None
        if digits.startswith("0"):
            digits = cc + digits[1:]
        elif digits.startswith(cc) and len(digits) >= len(cc) + 8:
            pass
        elif market == "US" and len(digits) == 10:
            digits = "1" + digits
        else:
            return None
    if not digits.isdigit() or not (8 <= len(digits) <= 15) or digits.startswith("0"):
        return None
    return "+" + digits


def market_of(e164: str) -> str:
    for pre, code in PREFIX_MARKET:
        if e164.startswith(pre):
            return code
    return ""
