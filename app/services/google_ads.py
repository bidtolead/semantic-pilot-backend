import os
from google.ads.googleads.client import GoogleAdsClient


def load_google_ads_client():
    """
    Initializes the Google Ads client using environment variables instead
    of a google-ads.yaml file.
    """

    developer_token = os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN")
    client_id = os.getenv("GOOGLE_ADS_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_ADS_CLIENT_SECRET")
    refresh_token = os.getenv("GOOGLE_ADS_REFRESH_TOKEN")
    login_customer_id = os.getenv("GOOGLE_ADS_LOGIN_CUSTOMER_ID")  # manager
    client_customer_id = os.getenv("GOOGLE_ADS_CUSTOMER_ID")  # actual account

    # Validate required variables
    missing = [
        key for key, value in {
            "GOOGLE_ADS_DEVELOPER_TOKEN": developer_token,
            "GOOGLE_ADS_CLIENT_ID": client_id,
            "GOOGLE_ADS_CLIENT_SECRET": client_secret,
            "GOOGLE_ADS_REFRESH_TOKEN": refresh_token,
        }.items() if not value
    ]

    if missing:
        raise ValueError(f"Missing Google Ads env vars: {', '.join(missing)}")

    config = {
        "developer_token": developer_token,
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "login_customer_id": login_customer_id,
        "use_proto_plus": True,
    }

    return GoogleAdsClient.load_from_dict(config), client_customer_id