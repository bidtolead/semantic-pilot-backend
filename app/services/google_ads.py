import os
from google.ads.googleads.client import GoogleAdsClient


def load_google_ads_client():
    """
    Initializes the Google Ads client using environment variables instead
    of a google-ads.yaml file (recommended for Render deployments).
    """

    # Read env vars
    developer_token = os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN")
    client_id = os.getenv("GOOGLE_ADS_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_ADS_CLIENT_SECRET")
    refresh_token = os.getenv("GOOGLE_ADS_REFRESH_TOKEN")
    login_customer_id = os.getenv("GOOGLE_ADS_LOGIN_CUSTOMER_ID")  # Manager account ID
    customer_id = os.getenv("GOOGLE_ADS_CUSTOMER_ID")  # The actual Ads account

    # Validate required environment variables
    required = {
        "GOOGLE_ADS_DEVELOPER_TOKEN": developer_token,
        "GOOGLE_ADS_CLIENT_ID": client_id,
        "GOOGLE_ADS_CLIENT_SECRET": client_secret,
        "GOOGLE_ADS_REFRESH_TOKEN": refresh_token,
    }

    missing = [key for key, value in required.items() if not value]
    if missing:
        raise ValueError(f"Missing Google Ads env vars: {', '.join(missing)}")

    # Google Ads configuration dict
    config = {
        "developer_token": developer_token,
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "login_customer_id": login_customer_id,
        "use_proto_plus": True,
    }

    # Return both: client + customer_id for API calls
    client = GoogleAdsClient.load_from_dict(config)
    return client, customer_id