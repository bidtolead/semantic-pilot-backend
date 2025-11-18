from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException


def fetch_keyword_ideas(query: str, location_id: str):
    client = GoogleAdsClient.load_from_storage("google-ads.yaml")

    customer_id = client.login_customer_id
    service = client.get_service("KeywordPlanIdeaService")

    request = client.get_type("GenerateKeywordIdeasRequest")
    request.customer_id = str(customer_id)

    # ENUM — dynamic, never version-specific
    request.keyword_plan_network = client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH

    # Seeds
    request.keyword_seed.keywords.append(query)
    request.geo_target_constants.append(f"geoTargetConstants/{location_id}")

    response = service.generate_keyword_ideas(request=request)

    results = []
    for idea in response:
        metrics = idea.keyword_idea_metrics
        results.append({
            "keyword": idea.text,
            "avg_monthly_searches": metrics.avg_monthly_searches,
            "competition": metrics.competition.name,
        })

    return results