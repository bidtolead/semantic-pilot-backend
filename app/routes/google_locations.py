from fastapi import APIRouter, HTTPException, Query
from google.ads.googleads.errors import GoogleAdsException
from app.services.google_ads import load_google_ads_client

# IMPORTANT:
# No prefix here — prefix is applied in main.py using:
# app.include_router(google_locations_router, prefix="/google")
router = APIRouter(tags=["Google Ads"])


@router.get("/locations")
def search_locations(query: str = Query(..., min_length=2)):
    """
    Autocomplete location search using Google Ads API.
    Works at:  GET /google/locations?query=auckland
    """

    # Load Google Ads client (env-based config)
    try:
        client, _customer_id = load_google_ads_client()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Google Ads config error: {e}"
        )

    service = client.get_service("GeoTargetConstantService")

    # Build request
    request = client.get_type("SuggestGeoTargetConstantsRequest")
    request.locale = "en"
    request.location_names.names.append(query)

    try:
        response = service.suggest_geo_target_constants(request=request)
    except GoogleAdsException as ex:
        raise HTTPException(
            status_code=500,
            detail=f"Google Ads API error: {ex}"
        )

    results = []
    for suggestion in response.geo_target_constant_suggestions:
        geo = suggestion.geo_target_constant

        results.append({
            "id": str(geo.id),
            "name": geo.name,
            "countryCode": geo.country_code,
            "targetType": geo.target_type.name,
            "status": geo.status.name,
        })

    return {"results": results}