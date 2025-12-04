from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import sqlite3
import os

from app.services.serper import SerperClient
from app.services.firestore import db
from google.cloud import firestore as gcf


router = APIRouter(prefix="/rank", tags=["rank"])

# Path to SQLite database
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "locations.db")



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
    try:
        loc_str = str(loc).strip() if loc else ""
        
        # Check if this is a location ID (numeric string)
        if loc_str.isdigit():
            # Look up in database
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT location_name, country_iso_code FROM locations WHERE location_code = ?",
                (int(loc_str),)
            )
            row = cursor.fetchone()
            conn.close()
            
            if row:
                location_name, country_code = row
                gl = country_code.lower()
                
                # Map country code to full name for location string
                COUNTRY_MAP = {
                    "NZ": "New Zealand",
                    "AU": "Australia",
                    "US": "United States",
                    "GB": "United Kingdom",
                    "CA": "Canada",
                    "IN": "India",
                    "PH": "Philippines",
                    "SG": "Singapore",
                    "AE": "United Arab Emirates",
                    "IL": "Israel",
                    "ZA": "South Africa",
                    "NG": "Nigeria",
                    "IE": "Ireland",
                    "MY": "Malaysia",
                    "PK": "Pakistan",
                    "KE": "Kenya",
                    "GH": "Ghana",
                }
                country_full = COUNTRY_MAP.get(country_code, country_code)
                
                # Build Serper-friendly location string
                # For cities, use "City, Country" format
                # For countries, just use country name
                if "," in location_name:
                    # Location name already has format like "Auckland,New Zealand"
                    rich_location = location_name.replace(",", ", ")
                else:
                    rich_location = f"{location_name}, {country_full}"
                
                return location_name.split(",")[0], gl, rich_location
        
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
