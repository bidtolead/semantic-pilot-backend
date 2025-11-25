from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any

from app.services.google_ads import load_google_ads_client

router = APIRouter(prefix="/geo", tags=["Geo"])

# Only allow English/business-English locations
ALLOWED_COUNTRY_CODES = {
    "US", "CA", "GB", "IE", "AU", "NZ",
    "SG", "AE", "IL", "ZA", "PH", "IN", "NG"
}


@router.get("/suggest")
def suggest_geo_targets(q: str = Query(..., min_length=2, max_length=80)):
    """
    Suggest geo target locations using Google Ads API (NO YAML).
    """
    q = q.strip()
    if not q:
        raise HTTPException(status_code=400, detail="Query must not be empty")

    try:
        client, customer_id = load_google_ads_client()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Google Ads config error: {e}")

    service = client.get_service("GeoTargetConstantService")
    request = client.get_type("SuggestGeoTargetConstantsRequest")

    # Locale must be set
    request.locale = "en"

    # Search by name (correct field)
    request.location_names.names.append(q)

    try:
        response = service.suggest_geo_target_constants(request=request)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Google Ads geo suggestion failed: {e}",
        )

    results: List[Dict[str, Any]] = []

    for s in response.geo_target_constant_suggestions:
        geo = s.geo_target_constant

        # Skip disabled
        if geo.status.name != "ENABLED":
            continue

        country = geo.country_code.upper() if geo.country_code else ""

        if country and country not in ALLOWED_COUNTRY_CODES:
            continue

        results.append({
            "id": str(geo.id),
            "name": geo.name,
            "countryCode": country,
           "targetType": geo.target_type,  # <-- FIXED
        })

    priority = {"COUNTRY": 0, "REGION": 1, "METRO": 2, "CITY": 3}

    results.sort(
        key=lambda x: (
            priority.get(x["targetType"], 99),
            x["name"].lower(),
        )
    )

    return {"items": results}