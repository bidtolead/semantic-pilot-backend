from fastapi import APIRouter, HTTPException, Query
from google.ads.googleads.errors import GoogleAdsException
from app.services.google_ads import load_google_ads_client

router = APIRouter(prefix="/google-ads", tags=["Google Ads"])


def format_location_result(geo):
    """
    Converts Google Ads API response into frontend-friendly format.
    """
    return {
        "id": str(geo.id),                  # numeric ID
        "name": geo.name,                   # e.g. "Auckland, New Zealand"
        "country_code": geo.country_code,   # e.g. "NZ"
        "target_type": geo.target_type.name,  # CITY, REGION, COUNTRY
        "status": geo.status.name,
    }


@router.get("/locations")
def search_locations(query: str = Query(..., min_length=2)):
    """
    Search Google Ads geo target constants — YAML-free, using env vars only.

    Example:
    GET /google-ads/locations?query=auckland
    """
    query = query.strip()

    try:
        client, customer_id = load_google_ads_client()
        service = client.get_service("GeoTargetConstantService")

        request = client.get_type("SuggestGeoTargetConstantsRequest")
        request.locale = "en"
        request.location_names.names.append(query)  # correct modern field

        response = service.suggest_geo_target_constants(request=request)

        results = []
        for suggestion in response.geo_target_constant_suggestions:
            geo = suggestion.geo_target_constant

            # skip disabled locations
            if geo.status.name != "ENABLED":
                continue

            results.append(format_location_result(geo))

        return {"results": results}

    except GoogleAdsException as ex:
        raise HTTPException(status_code=500, detail=f"Google Ads API error: {ex}")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))