from fastapi import APIRouter, HTTPException, Query
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
import os

router = APIRouter()

# -------------------------------------------------
# Load Google Ads Config
# -------------------------------------------------
def load_google_ads_client():
    """
    Loads Google Ads client from google-ads.yaml file.
    Looks in:
      /app/google/google-ads.yaml
      /google-ads.yaml
    """
    yaml_paths = [
        "/app/google/google-ads.yaml",
        "google-ads.yaml",
        "./google-ads.yaml",
        "/Users/timur/semantic-pilot/semantic-pilot-backend/google-ads.yaml"
    ]

    for path in yaml_paths:
        if os.path.exists(path):
            return GoogleAdsClient.load_from_storage(path)

    raise FileNotFoundError("google-ads.yaml not found in expected locations.")


# -------------------------------------------------
# Format Google Location Criteria
# -------------------------------------------------
def format_location_result(row):
    """
    Converts Google Ads API response into a clean format
    for the frontend dropdown.
    """
    criterion = row.geo_target_constant

    return {
        "id": criterion.resource_name,
        "name": criterion.name,
        "country_code": criterion.country_code,
        "target_type": criterion.target_type,  # CITY, REGION, NEIGHBORHOOD, etc.
        "status": criterion.status.name,
    }


# -------------------------------------------------
# Location Autocomplete Route
# -------------------------------------------------
@router.get("/locations")
def search_locations(query: str = Query(..., min_length=2)):
    """
    Search Google Ads geo target constants.
    Works like Google Keyword Planner -> Locations search.

    Example:
    GET /google/locations?query=auckland
    """

    try:
        client = load_google_ads_client()
        service = client.get_service("GeoTargetConstantService")

        request = client.get_type("SuggestGeoTargetConstantsRequest")
        request.locale = "en"
        request.country_code = ""   # allow all countries
        request.prefix = query

        response = service.suggest_geo_target_constants(request=request)

        results = [format_location_result(r.geo_target_constant) for r in response.geo_target_constant_suggestions]

        return {"results": results}

    except GoogleAdsException as ex:
        raise HTTPException(
            status_code=500,
            detail=f"Google Ads API error: {ex}"
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )