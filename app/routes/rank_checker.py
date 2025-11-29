from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.serper import SerperClient
from app.services.firestore import db
from google.cloud import firestore as gcf


router = APIRouter(prefix="/rank", tags=["rank"])



class RankRequest(BaseModel):
    query: str
    target_url: str
    location: str | None = None



@router.post("/check")
def check_rank(payload: RankRequest):
    try:
        client = SerperClient()
        result = client.find_url_rank(q=payload.query, target_url=payload.target_url, location=payload.location, max_results=20)
        return {"ok": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))



class BatchRankRequest(BaseModel):
    keywords: list[str]
    target_url: str
    location: str
    top: int | None = 50  # number of organic results to check (default 50)
    user_id: str | None = None  # optional: attribute Serper credits to a user



def _parse_location(loc: str):
    """Extract a city and country from a display string like
    'Auckland (City · NZ)'. Returns tuple (city_name, gl, location_string)
    where gl is a lowercased country code for Serper and location_string is a
    human-friendly string that Serper recognizes better, e.g.,
    'Auckland, Auckland, New Zealand'. If parsing fails, falls back to (loc, None, loc).
    """
    try:
        name = loc.strip() if isinstance(loc, str) else ""
        gl = None
        country_full = None

        if isinstance(loc, str) and ("(" in loc and ")" in loc):
            # e.g., 'Auckland (City · NZ)'
            name = loc.split("(", 1)[0].strip()
            inside = loc.split("(", 1)[1].split(")", 1)[0]
            parts = [p.strip() for p in inside.split("·")]
            if parts:
                cc = parts[-1].strip().upper()
                if len(cc) == 2:
                    gl = cc.lower()
                    COUNTRY_MAP = {
                        "NZ": "New Zealand",
                        "AU": "Australia",
                        "US": "United States",
                        "GB": "United Kingdom",
                        "CA": "Canada",
                    }
                    country_full = COUNTRY_MAP.get(cc)

        # Fallbacks
        if not name:
            name = str(loc)
        if not country_full and gl:
            # naive fallback: use code as-is
            country_full = gl.upper()

        # Construct a richer location string to bias Serper better
        # Format: "City, City, Country"
        rich_location = name
        if name and country_full:
            rich_location = f"{name}, {name}, {country_full}"

        return name, gl, rich_location
    except Exception:
        return loc, None, loc


@router.post("/batch")
def batch_rank(payload: BatchRankRequest):
    try:
        if not payload.keywords:
            raise ValueError("No keywords provided")
        if len(payload.keywords) > 15:
            raise ValueError("Maximum of 15 final keywords per research")
        client = SerperClient()
        # Normalize location and derive gl from the LocationCombobox format
        norm_location, gl, rich_location = _parse_location(payload.location)
        top = int(payload.top or 20)
        top = 20 if top < 1 else min(top, 100)
        results = []
        for kw in payload.keywords:
            r = client.find_url_rank(
                q=kw,
                target_url=payload.target_url,
                location=rich_location or norm_location,
                gl=gl,
                hl="en",
                top=top,
            )
            # Map rank None to "Not in top 20"
            results.append({
                "keyword": kw,
                "rank": r.get("rank") if r.get("rank") is not None else f"Not in top {top}",
                "url": r.get("url"),
            })

        # Track Serper credits usage (global and per-user)
        try:
            credit_inc = len(payload.keywords)
            usage_ref = db.collection("system_settings").document("usage")
            usage_ref.set({
                "serperTotalCredits": gcf.Increment(credit_inc),
                "updated_at": gcf.SERVER_TIMESTAMP,
            }, merge=True)

            if payload.user_id:
                user_ref = db.collection("users").document(payload.user_id)
                user_ref.set({
                    "serperCredits": gcf.Increment(credit_inc),
                    "lastSerperUseAt": gcf.SERVER_TIMESTAMP,
                }, merge=True)
        except Exception:
            # Don't fail rank API if usage tracking fails
            pass
        return {"ok": True, "location": norm_location, "gl": gl, "target_url": payload.target_url, "top": top, "results": results}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
