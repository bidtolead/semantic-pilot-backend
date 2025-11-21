from fastapi import APIRouter, HTTPException, Query
from google.ads.googleads.errors import GoogleAdsException
from app.services.google_ads import load_google_ads_client

router = APIRouter(prefix="/google-ads", tags=["Google Ads"])


# ------------------------
# Location Search Endpoint
# ------------------------
@router.get("/locations")
def search_locations(query: str = Query(..., min_length=2)):
    """
    Location autocomplete using Google Ads API.
    Replaces old YAML-based version.
    """

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
            "id": geo.id,
            "name": geo.name,
            "countryCode": geo.country_code,
            "targetType": geo.target_type.name,
            "status": geo.status.name
        })

    return {"results": results}