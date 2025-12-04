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
    """Extract a city and country from a location ID or display string.
    
    Handles both:
    1. Location IDs from geo.py (e.g., "1011036" for Auckland)
    2. Display strings like 'Auckland (City · NZ)'
    
    Returns tuple (city_name, gl, location_string) where:
    - city_name: Short city name
    - gl: Country code for Serper (lowercase)
    - location_string: Full location string for Serper API
    """
    # Mapping of location IDs to Serper-friendly location strings
    LOCATION_ID_MAP = {
        # US
        "1023191": {"name": "New York", "gl": "us", "location": "New York, NY, United States"},
        "1014044": {"name": "Los Angeles", "gl": "us", "location": "Los Angeles, CA, United States"},
        "1012728": {"name": "Chicago", "gl": "us", "location": "Chicago, IL, United States"},
        "1021224": {"name": "Houston", "gl": "us", "location": "Houston, TX, United States"},
        "1023040": {"name": "Phoenix", "gl": "us", "location": "Phoenix, AZ, United States"},
        "1025197": {"name": "San Francisco", "gl": "us", "location": "San Francisco, CA, United States"},
        "1026201": {"name": "Seattle", "gl": "us", "location": "Seattle, WA, United States"},
        "1013962": {"name": "Miami", "gl": "us", "location": "Miami, FL, United States"},
        "2840": {"name": "United States", "gl": "us", "location": "United States"},
        # Canada
        "9000093": {"name": "Toronto", "gl": "ca", "location": "Toronto, ON, Canada"},
        "9000071": {"name": "Vancouver", "gl": "ca", "location": "Vancouver, BC, Canada"},
        "9000040": {"name": "Montreal", "gl": "ca", "location": "Montreal, QC, Canada"},
        "2124": {"name": "Canada", "gl": "ca", "location": "Canada"},
        # UK
        "1006886": {"name": "London", "gl": "gb", "location": "London, United Kingdom"},
        "1006099": {"name": "Manchester", "gl": "gb", "location": "Manchester, United Kingdom"},
        "2826": {"name": "United Kingdom", "gl": "gb", "location": "United Kingdom"},
        # Australia
        "1000339": {"name": "Sydney", "gl": "au", "location": "Sydney, NSW, Australia"},
        "1000318": {"name": "Melbourne", "gl": "au", "location": "Melbourne, VIC, Australia"},
        "1000310": {"name": "Brisbane", "gl": "au", "location": "Brisbane, QLD, Australia"},
        "2036": {"name": "Australia", "gl": "au", "location": "Australia"},
        # New Zealand
        "1011036": {"name": "Auckland", "gl": "nz", "location": "Auckland, New Zealand"},
        "1001460": {"name": "Wellington", "gl": "nz", "location": "Wellington, New Zealand"},
        "2554": {"name": "New Zealand", "gl": "nz", "location": "New Zealand"},
    }
    
    try:
        loc_str = str(loc).strip() if loc else ""
        
        # Check if this is a location ID
        if loc_str in LOCATION_ID_MAP:
            loc_data = LOCATION_ID_MAP[loc_str]
            return loc_data["name"], loc_data["gl"], loc_data["location"]
        
        # Otherwise parse as display string format: 'Auckland (City · NZ)'
        name = loc_str
        gl = None
        country_full = None

        if "(" in loc_str and ")" in loc_str:
            # e.g., 'Auckland (City · NZ)'
            name = loc_str.split("(", 1)[0].strip()
            inside = loc_str.split("(", 1)[1].split(")", 1)[0]
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
            name = loc_str
        if not country_full and gl:
            country_full = gl.upper()

        # Construct location string
        rich_location = name
        if name and country_full:
            rich_location = f"{name}, {country_full}"

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
