from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any
from app.services.google_ads import load_google_ads_client

router = APIRouter(prefix="/geo", tags=["Geo"])

ALLOWED_COUNTRY_CODES = {
    "US", "CA", "GB", "IE", "AU", "NZ",
    "SG", "AE", "IL", "ZA", "PH", "IN", "NG"
}

@router.get("/suggest")
def suggest_geo_targets(q: str = Query(..., min_length=2, max_length=80)):
    q = q.strip()
    if not q:
        raise HTTPException(status_code=400, detail="Query must not be empty")

    try:
        client, customer_id = load_google_ads_client()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Google Ads config error: {e}")

    service = client.get_service("GeoTargetConstantService")
    request = client.get_type("SuggestGeoTargetConstantsRequest")

    request.locale = "en"
    request.location_names.names.append(q)

    try:
        response = service.suggest_geo_target_constants(request=request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Geo suggestion failed: {e}")

    results = []

    for s in response.geo_target_constant_suggestions:
        geo = s.geo_target_constant

        if geo.status.name != "ENABLED":
            continue

        country = (geo.country_code or "").upper()
        if country and country not in ALLOWED_COUNTRY_CODES:
            continue

        results.append({
            "id": str(geo.id),
            "name": geo.name,
            "countryCode": country,
            "targetType": geo.target_type,
        })

    priority = {"COUNTRY": 0, "REGION": 1, "METRO": 2, "CITY": 3}

    results.sort(
        key=lambda x: (priority.get(x["targetType"], 99), x["name"].lower())
    )

    return {"items": results}