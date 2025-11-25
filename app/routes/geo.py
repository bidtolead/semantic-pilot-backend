from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any

from app.services.google_ads import load_google_ads_client

router = APIRouter(prefix="/google-ads/geo", tags=["Geo"])


# Allowed English-speaking countries only
ALLOWED_COUNTRY_CODES = {
    "US", "CA", "GB", "IE", "AU", "NZ",
    "SG", "AE", "IL", "ZA", "PH", "IN", "NG"
}

# Sorting priority
PRIORITY = {
    "CITY": 1,
    "REGION": 2,
    "COUNTRY": 3,
    "POSTAL CODE": 4,
    "METRO": 5,
}


@router.get("/suggest")
def suggest_geo_targets(q: str = Query(..., min_length=2, max_length=80)):
    """
    Suggest geo targets using Google Ads API.
    Sorted: City → Region → Country → Postal Code
    Postal codes only shown if query has digits.
    """
    q = q.strip()
    if not q:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    # Detect numeric queries → allow postal codes only if digits present
    include_postal = any(ch.isdigit() for ch in q)

    # Load Google Ads API client
    try:
        client, customer_id = load_google_ads_client()
        service = client.get_service("GeoTargetConstantService")
        request = client.get_type("SuggestGeoTargetConstantsRequest")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Google Ads config error: {e}")

    # Search by name
    request.locale = "en"
    request.location_names.names.append(q)

    # Query Google Ads API
    try:
        response = service.suggest_geo_target_constants(request=request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Geo API failed: {e}")

    items: List[Dict[str, Any]] = []
    seen_ids = set()

    for s in response.geo_target_constant_suggestions:
        geo = s.geo_target_constant

        # Skip disabled locations
        if geo.status.name != "ENABLED":
            continue

        # Allowed countries only
        country = (geo.country_code or "").upper()
        if country and country not in ALLOWED_COUNTRY_CODES:
            continue

        raw_type = geo.target_type  # STRING e.g. CITY, POSTAL_CODE
        target_type = raw_type.replace("_", " ").upper()  # POSTAL_CODE → POSTAL CODE

        # If query has no digits → hide postal codes
        if target_type == "POSTAL CODE" and not include_postal:
            continue

        # Deduplicate
        if geo.id in seen_ids:
            continue
        seen_ids.add(geo.id)

        items.append({
            "id": str(geo.id),
            "name": geo.name,
            "country": country,
            "targetType": target_type,  # required by your frontend
        })

    # Sort by priority and alphabetically
    items.sort(
        key=lambda x: (
            PRIORITY.get(x["targetType"], 999),
            x["name"].lower()
        )
    )

    # Limit results to top 10
    items = items[:10]

    return {"items": items}