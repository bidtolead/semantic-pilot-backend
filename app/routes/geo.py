from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any
import sqlite3
import os

router = APIRouter(prefix="/geo", tags=["Geo"])

# Path to SQLite database
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "locations.db")

@router.get("/locations")
def get_all_locations(limit: int = Query(default=1000, ge=1, le=5000)):
    """Get all available locations from database.
    
    Returns locations from SQLite database.
    Use limit parameter to control how many locations to return.
    Default is 1000 for reasonable response size.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute(
        """
        SELECT location_code, location_name, country_iso_code, location_type
        FROM locations
        ORDER BY location_name
        LIMIT ?
        """,
        (limit,)
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


@router.get("/location/{location_id}")
def get_location_by_id(location_id: str):
    """Get location details by ID.
    
    Returns location information for a specific location code.
    """
    print(f"[GEO] Fetching location: {location_id}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute(
        """
        SELECT location_code, location_name, country_iso_code, location_type
        FROM locations
        WHERE location_code = ?
        LIMIT 1
        """,
        (location_id,)
    )
    
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        print(f"[GEO] Location not found: {location_id}")
        raise HTTPException(status_code=404, detail="Location not found")
    
    print(f"[GEO] Found location: {row}")
    return {
        "id": str(row[0]),
        "name": row[1],
        "countryCode": row[2],
        "targetType": row[3]
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