from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any
from app.services.dataforseo import fetch_locations

router = APIRouter(prefix="/geo", tags=["Geo"])

ALLOWED_COUNTRY_CODES = {
    "US", "CA", "GB", "IE", "AU", "NZ",
    "SG", "AE", "IL", "ZA", "PH", "IN", "NG"
}

# Cache locations in memory after first call
_locations_cache: List[Dict] = None

@router.get("/locations")
def get_all_locations():
    """Get all available Google Ads locations from DataForSEO.
    
    Returns the full list for client-side caching. This is a free endpoint.
    Filters to allowed countries and excludes postal codes.
    """
    global _locations_cache
    
    if _locations_cache is None:
        try:
            raw_locations = fetch_locations()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"DataForSEO locations failed: {e}")
        
        # Filter and format
        filtered = []
        for loc in raw_locations:
            country = (loc.get("country_iso_code") or "").upper()
            loc_type = loc.get("location_type", "")
            
            # Skip postal codes and non-allowed countries
            if loc_type == "Postal code":
                continue
            if country and country not in ALLOWED_COUNTRY_CODES:
                continue
            
            filtered.append({
                "id": str(loc.get("location_code")),
                "name": loc.get("location_name"),
                "countryCode": country,
                "targetType": loc_type,
            })
        
        _locations_cache = filtered
    
    return {"items": _locations_cache}

@router.get("/suggest")
def suggest_geo_targets(
    q: str = Query(..., min_length=2, max_length=80),
    limit: int = Query(default=50, ge=1, le=200)
):
    """Search locations by query string.
    
    Uses DataForSEO locations list and filters server-side.
    Returns max 50 results by default to reduce memory and bandwidth.
    """
    q = q.strip()
    if not q:
        raise HTTPException(status_code=400, detail="Query must not be empty")
    
    # Get full locations list (cached)
    all_locs = get_all_locations()["items"]
    
    # Filter to matching names
    query_lower = q.lower()
    results = [loc for loc in all_locs if query_lower in loc["name"].lower()]
    
    # Sort by relevance: exact matches first, then starts-with, then contains
    def sort_key(item):
        name_lower = item["name"].lower()
        if name_lower == query_lower:
            return (0, name_lower)
        elif name_lower.startswith(query_lower):
            return (1, name_lower)
        else:
            return (2, name_lower)
    
    results.sort(key=sort_key)
    
    # Limit results to prevent memory issues
    return {"items": results[:limit]}