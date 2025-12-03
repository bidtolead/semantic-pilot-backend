from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any

router = APIRouter(prefix="/geo", tags=["Geo"])

# Hardcoded major cities to avoid memory issues with DataForSEO's 100k+ locations
# This is a temporary solution until we can properly handle the large dataset
HARDCODED_LOCATIONS = [
    # US
    {"id": "1023191", "name": "New York, NY, United States", "countryCode": "US", "targetType": "City"},
    {"id": "1014044", "name": "Los Angeles, CA, United States", "countryCode": "US", "targetType": "City"},
    {"id": "1012728", "name": "Chicago, IL, United States", "countryCode": "US", "targetType": "City"},
    {"id": "1021224", "name": "Houston, TX, United States", "countryCode": "US", "targetType": "City"},
    {"id": "1023040", "name": "Phoenix, AZ, United States", "countryCode": "US", "targetType": "City"},
    {"id": "1025197", "name": "San Francisco, CA, United States", "countryCode": "US", "targetType": "City"},
    {"id": "1026201", "name": "Seattle, WA, United States", "countryCode": "US", "targetType": "City"},
    {"id": "1013962", "name": "Miami, FL, United States", "countryCode": "US", "targetType": "City"},
    {"id": "2840", "name": "United States", "countryCode": "US", "targetType": "Country"},
    
    # Canada
    {"id": "9000093", "name": "Toronto, ON, Canada", "countryCode": "CA", "targetType": "City"},
    {"id": "9000071", "name": "Vancouver, BC, Canada", "countryCode": "CA", "targetType": "City"},
    {"id": "9000040", "name": "Montreal, QC, Canada", "countryCode": "CA", "targetType": "City"},
    {"id": "2124", "name": "Canada", "countryCode": "CA", "targetType": "Country"},
    
    # UK
    {"id": "1006886", "name": "London, United Kingdom", "countryCode": "GB", "targetType": "City"},
    {"id": "1006099", "name": "Manchester, United Kingdom", "countryCode": "GB", "targetType": "City"},
    {"id": "2826", "name": "United Kingdom", "countryCode": "GB", "targetType": "Country"},
    
    # Australia  
    {"id": "1000339", "name": "Sydney NSW, Australia", "countryCode": "AU", "targetType": "City"},
    {"id": "1000318", "name": "Melbourne VIC, Australia", "countryCode": "AU", "targetType": "City"},
    {"id": "1000310", "name": "Brisbane QLD, Australia", "countryCode": "AU", "targetType": "City"},
    {"id": "2036", "name": "Australia", "countryCode": "AU", "targetType": "Country"},
    
    # New Zealand
    {"id": "1011036", "name": "Auckland, New Zealand", "countryCode": "NZ", "targetType": "City"},
    {"id": "1001460", "name": "Wellington, New Zealand", "countryCode": "NZ", "targetType": "City"},
    {"id": "2554", "name": "New Zealand", "countryCode": "NZ", "targetType": "Country"},
]

@router.get("/locations")
def get_all_locations():
    """Get hardcoded locations to avoid memory issues.
    
    Returns a curated list of major cities in English-speaking countries.
    This avoids loading 100k+ locations from DataForSEO which crashes the 512MB server.
    """
    return {"items": HARDCODED_LOCATIONS}


@router.get("/suggest")
def suggest_geo_targets(
    q: str = Query(..., min_length=2, max_length=80),
    limit: int = Query(default=50, ge=1, le=200)
):
    """Search locations by query string.
    
    Searches hardcoded location list server-side.
    Returns max 50 results by default.
    """
    q = q.strip()
    if not q:
        raise HTTPException(status_code=400, detail="Query must not be empty")
    
    # Get hardcoded locations
    all_locs = HARDCODED_LOCATIONS
    
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
    
    # Limit results
    return {"items": results[:limit]}