from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any
import json
import os
import httpx

router = APIRouter(prefix="/geo", tags=["Geo"])

# GitHub raw URL for locations JSON (to avoid memory issues with SQLite on Render)
LOCATIONS_JSON_URL = "https://raw.githubusercontent.com/bidtolead/semantic-pilot-backend/main/app/data/locations.json"

# Cache for locations data
_locations_cache = None

def get_locations_data() -> List[Dict[str, Any]]:
    """Get locations data from GitHub or local file as fallback."""
    global _locations_cache
    
    if _locations_cache is not None:
        return _locations_cache
    
    try:
        # Try fetching from GitHub first
        response = httpx.get(LOCATIONS_JSON_URL, timeout=5.0)
        response.raise_for_status()
        _locations_cache = response.json()
        print(f"[GEO] Loaded {len(_locations_cache)} locations from GitHub")
        return _locations_cache
    except Exception as e:
        print(f"[GEO] Failed to fetch from GitHub: {e}, trying local file")
        # Fallback to local file
        try:
            local_path = os.path.join(os.path.dirname(__file__), "..", "data", "locations.json")
            with open(local_path, 'r') as f:
                _locations_cache = json.load(f)
                print(f"[GEO] Loaded {len(_locations_cache)} locations from local file")
                return _locations_cache
        except Exception as local_err:
            print(f"[GEO] Failed to load local file: {local_err}")
            return []

@router.get("/locations")
def get_all_locations(limit: int = Query(default=1000, ge=1, le=5000)):
    """Get all available locations from GitHub JSON.
    
    Returns locations from JSON file hosted on GitHub.
    Use limit parameter to control how many locations to return.
    Default is 1000 for reasonable response size.
    """
    locations = get_locations_data()
    
    # Apply limit
    limited_locations = locations[:limit]
    
    return {"items": limited_locations}


@router.get("/location/{location_id}")
def get_location_by_id(location_id: str):
    """Get location details by ID from GitHub JSON.
    
    Returns location information for a specific location code.
    """
    print(f"[GEO] Fetching location: {location_id}")
    
    locations = get_locations_data()
    
    # Find the location by ID
    location = next((loc for loc in locations if loc.get("id") == location_id), None)
    
    if not location:
        print(f"[GEO] Location not found: {location_id}")
        raise HTTPException(status_code=404, detail="Location not found")
    
    print(f"[GEO] Found location: {location}")
    return {
        "id": location["id"],
        "name": location["name"],
        "countryCode": location["countryCode"],
        "targetType": location["targetType"]
    }


@router.get("/suggest")
def suggest_geo_targets(
    q: str = Query(..., min_length=2, max_length=80),
    limit: int = Query(default=50, ge=1, le=200)
):
    """Search locations by query string.
    
    Searches SQLite database for matching locations.
    Returns max 50 results by default, sorted by relevance.
    """
    q = q.strip()
    if not q:
        raise HTTPException(status_code=400, detail="Query must not be empty")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Case-insensitive search with LIKE, prioritize exact/starts-with matches
    # Use CASE to sort: exact match first, then starts-with, then contains
    cursor.execute(
        """
        SELECT location_code, location_name, country_iso_code, location_type,
               CASE
                   WHEN LOWER(location_name) = LOWER(?) THEN 0
                   WHEN LOWER(location_name) LIKE LOWER(?) THEN 1
                   ELSE 2
               END AS priority
        FROM locations
        WHERE location_name LIKE ?
        ORDER BY priority, location_name
        LIMIT ?
        """,
        (q, f"{q}%", f"%{q}%", limit)
    )
    
    items = [
        {
            "id": str(row[0]),
            "name": row[1],
            "countryCode": row[2],
            "targetType": row[3]
        }
        for row in cursor.fetchall()
    ]
    
    conn.close()
    
    return {"items": items}