"""Google Places API (New) Text Search. Up to 60 results per search (3 pages of 20)."""
import os

import httpx

BASE = os.getenv("PLACES_BASE_URL", "https://places.googleapis.com")
FIELDS = ("places.id,places.displayName,places.formattedAddress,places.internationalPhoneNumber,"
          "places.websiteUri,places.rating,places.userRatingCount,nextPageToken")


def configured() -> bool:
    return bool(os.getenv("GOOGLE_PLACES_API_KEY"))


async def search(query: str, region: str, limit: int) -> list[dict]:
    key = os.getenv("GOOGLE_PLACES_API_KEY")
    if not key:
        raise RuntimeError("The Google Places key is missing. Add it in Settings > Integrations.")
    out, token = [], None
    async with httpx.AsyncClient(timeout=30) as c:
        while len(out) < limit:
            body = {"textQuery": query, "pageSize": min(20, limit - len(out)), "regionCode": region}
            if token:
                body["pageToken"] = token
            r = await c.post(f"{BASE}/v1/places:searchText", json=body,
                             headers={"X-Goog-Api-Key": key, "X-Goog-FieldMask": FIELDS})
            if r.status_code >= 300:
                raise RuntimeError(f"Google Places error {r.status_code}: {r.text[:200]}")
            data = r.json()
            places = data.get("places", [])
            out += places
            token = data.get("nextPageToken")
            if not token or not places:
                break
    return [{"name": (p.get("displayName") or {}).get("text", ""), "address": p.get("formattedAddress", ""),
             "phone": p.get("internationalPhoneNumber", ""), "website": p.get("websiteUri", ""),
             "rating": p.get("rating"), "reviews": p.get("userRatingCount")} for p in out[:limit]]
