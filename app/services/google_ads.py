import os
from google.ads.googleads.client import GoogleAdsClient


def load_google_ads_client():
    """Initialize Google Ads client using environment variables.

    Raises:
        ValueError: if required environment variables are missing.
    Returns:
        tuple[GoogleAdsClient, str | None]: client instance and customer ID.
    """
    developer_token = os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN")
    client_id = os.getenv("GOOGLE_ADS_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_ADS_CLIENT_SECRET")
    refresh_token = os.getenv("GOOGLE_ADS_REFRESH_TOKEN")
    login_customer_id = os.getenv("GOOGLE_ADS_LOGIN_CUSTOMER_ID")
    customer_id = os.getenv("GOOGLE_ADS_CUSTOMER_ID")

    required = {
        "GOOGLE_ADS_DEVELOPER_TOKEN": developer_token,
        "GOOGLE_ADS_CLIENT_ID": client_id,
        "GOOGLE_ADS_CLIENT_SECRET": client_secret,
        "GOOGLE_ADS_REFRESH_TOKEN": refresh_token,
    }
    missing = [k for k, v in required.items() if not v]
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

    client = GoogleAdsClient.load_from_dict(config)
    return client, customer_id


def fetch_keyword_ideas(
    seed_keywords: list[str] = None,
    geo_id: int = 2840,
    landing_page: str = None,
    competitor_urls: list[str] = None
):
    """Fetch keyword ideas from Google Ads KeywordPlanIdeaService.

    Args:
        seed_keywords: List of seed keywords.
        geo_id: Geo target constant ID (default USA 2840).
        landing_page: Optional landing page URL to analyze.
        competitor_urls: Optional list of competitor URLs to analyze.
    Returns:
        list[dict]: Simplified keyword idea metrics.
    """
    seed_keywords = seed_keywords or []
    competitor_urls = competitor_urls or []
    
    if not seed_keywords and not landing_page and not competitor_urls:
        return []

    client, customer_id = load_google_ads_client()
    if not customer_id:
        raise ValueError("GOOGLE_ADS_CUSTOMER_ID missing.")

    service = client.get_service("KeywordPlanIdeaService")
    request = client.get_type("GenerateKeywordIdeasRequest")
    request.customer_id = customer_id

    # Language set to English (language constant resource name)
    request.language = "languageConstants/1000"

    # Geo target constants
    request.geo_target_constants.append(f"geoTargetConstants/{geo_id}")

    # Add seed keywords
    for kw in seed_keywords:
        if kw and isinstance(kw, str):
            request.keyword_seed.keywords.append(kw)
    
    # Add landing page URL if provided
    if landing_page:
        request.url_seed.url = landing_page
    
    # Add competitor URLs if provided
    for url in competitor_urls:
        if url and isinstance(url, str):
            request.url_seed.url = url

    try:
        response = service.generate_keyword_ideas(request=request)
    except Exception as e:
        raise Exception(f"Google Ads generate_keyword_ideas failed: {e}")

    results: list[dict] = []
    for idea in response:
        metrics = idea.keyword_idea_metrics
        results.append({
            "keyword": idea.text,
            "avg_monthly_searches": metrics.avg_monthly_searches,
            "competition": metrics.competition.name if metrics.competition else None,
            "competition_index": metrics.competition_index,
            "low_top_of_page_bid_micros": metrics.low_top_of_page_bid_micros,
            "high_top_of_page_bid_micros": metrics.high_top_of_page_bid_micros,
        })

    return results