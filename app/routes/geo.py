from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any
import os

from google.ads.googleads.client import GoogleAdsClient

router = APIRouter(prefix="/geo", tags=["Geo"])

# Cache a single GoogleAdsClient instance for performance
_google_ads_client: GoogleAdsClient | None = None


def get_google_ads_client() -> GoogleAdsClient:
    """
    Load Google Ads client from environment-based config.

    You can either:
    - Set GOOGLE_ADS_CONFIGURATION_FILE to point to your google-ads.yaml, or
    - Use GOOGLE_ADS_DEVELOPER_TOKEN, GOOGLE_ADS_CLIENT_ID, GOOGLE_ADS_CLIENT_SECRET,
      GOOGLE_ADS_REFRESH_TOKEN, GOOGLE_ADS_LOGIN_CUSTOMER_ID, etc.
    """
    global _google_ads_client
    if _google_ads_client is not None:
        return _google_ads_client

    config_file = os.getenv("GOOGLE_ADS_CONFIGURATION_FILE")

    if config_file and os.path.exists(config_file):
        _google_ads_client = GoogleAdsClient.load_from_storage(path=config_file)
    else:
        # Fallback: load from environment variables
        config: Dict[str, Any] = {
            "developer_token": os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN"),
            "login_customer_id": os.getenv("GOOGLE_ADS_LOGIN_CUSTOMER_ID"),
            "use_proto_plus": True,
            "client_id": os.getenv("GOOGLE_ADS_CLIENT_ID"),
            "client_secret": os.getenv("GOOGLE_ADS_CLIENT_SECRET"),
            "refresh_token": os.getenv("GOOGLE_ADS_REFRESH_TOKEN"),
        }

        missing = [k for k, v in config.items() if not v]
        if missing:
            raise RuntimeError(
                f"Missing Google Ads config values: {', '.join(missing)}"
            )

        _google_ads_client = GoogleAdsClient.load_from_dict(config)

    return _google_ads_client


# Only allow English-speaking / business-English locations
ALLOWED_COUNTRY_CODES = {
    "US",  # United States
    "CA",  # Canada
    "GB",  # United Kingdom
    "IE",  # Ireland
    "AU",  # Australia
    "NZ",  # New Zealand
    "SG",  # Singapore
    "AE",  # United Arab Emirates (Dubai etc.)
    "IL",  # Israel
    "ZA",  # South Africa
    "PH",  # Philippines
    "IN",  # India
    "NG",  # Nigeria
}


@router.get("/suggest")
def suggest_geo_targets(q: str = Query(..., min_length=2, max_length=80)):
    """
    Proxy to Google Ads GeoTargetConstantService.suggest_geo_target_constants.

    Returns a list of locations similar to Google Ads UI:
    city, region, country, etc. Filtered to ALLOWED_COUNTRY_CODES.
    """
    q = q.strip()
    if not q:
        raise HTTPException(status_code=400, detail="Query must not be empty")

    try:
        client = get_google_ads_client()
    except Exception as e:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Google Ads config error: {e}")

    service = client.get_service("GeoTargetConstantService")
    request = client.get_type("SuggestGeoTargetConstantsRequest")

    # Use English and don't restrict to a single country
    request.locale = "en"
    # If you want, you can set request.country_code = "NZ" etc. for biasing.

    # Use location_names search mode
    request.location_names.names.append(q)

    try:
        response = service.suggest_geo_target_constants(request=request)
    except Exception as e:  # pragma: no cover
        raise HTTPException(
            status_code=500,
            detail=f"Google Ads geo suggestion failed: {e}",
        )

    results: List[Dict[str, Any]] = []

    for suggestion in response.geo_target_constant_suggestions:
        geo = suggestion.geo_target_constant

        # geo.target_type and geo.status are enums; use .name for readability
        target_type = geo.target_type.name if hasattr(geo.target_type, "name") else str(geo.target_type)
        status = geo.status.name if hasattr(geo.status, "name") else str(geo.status)

        # Only active locations
        if status != "ENABLED":
            continue

        country_code = geo.country_code.upper() if geo.country_code else ""

        # Filter to our English/business-English countries
        if country_code and country_code not in ALLOWED_COUNTRY_CODES:
            continue

        results.append(
            {
                "id": str(geo.id),                 # e.g. "1023191"
                "name": geo.name,                  # e.g. "Auckland, New Zealand"
                "countryCode": country_code,       # e.g. "NZ"
                "targetType": target_type,         # e.g. "CITY", "REGION", "COUNTRY"
            }
        )

    # Sort a bit like Google: country/region above city, then name
    priority = {"COUNTRY": 0, "REGION": 1, "METRO": 2, "CITY": 3}

    results.sort(
        key=lambda x: (
            priority.get(x["targetType"], 99),
            x["name"].lower(),
        )
    )

    return {"items": results}