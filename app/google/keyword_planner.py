from app.services.google_ads import load_google_ads_client
from google.ads.googleads.errors import GoogleAdsException


def fetch_keyword_ideas(query: str, location_id: str):
    """
    Fetch keyword ideas using Google Ads API without google-ads.yaml.
    Uses environment variables instead of local files.
    """

    # Load client & customer ID (passed from load_google_ads_client)
    client, customer_id = load_google_ads_client()

    if not customer_id:
        raise ValueError(
            "GOOGLE_ADS_CUSTOMER_ID is missing. Set it in Render Dashboard."
        )

    service = client.get_service("KeywordPlanIdeaService")

    request = client.get_type("GenerateKeywordIdeasRequest")
    request.customer_id = str(customer_id)

    # ENUM (stable across versions)
    request.keyword_plan_network = (
        client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH
    )

    # Seed keywords
    request.keyword_seed.keywords.append(query)

    # Location targeting
    request.geo_target_constants.append(f"geoTargetConstants/{location_id}")

    try:
        response = service.generate_keyword_ideas(request=request)
    except GoogleAdsException as ex:
        raise RuntimeError(
            f"Google Ads KeywordPlan error: {ex.failure.errors}"
        )
    except Exception as e:
        raise RuntimeError(str(e))

    results = []
    for idea in response:
        metrics = idea.keyword_idea_metrics

        results.append({
            "keyword": idea.text,
            "avg_monthly_searches": metrics.avg_monthly_searches,
            "competition": metrics.competition.name,
        })

    return results