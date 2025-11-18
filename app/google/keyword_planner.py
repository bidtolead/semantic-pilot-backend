from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException


def fetch_keyword_ideas(query: str, location_id: str):
    client = GoogleAdsClient.load_from_storage("google-ads.yaml")

    customer_id = client.login_customer_id

    keyword_plan_idea_service = client.get_service("KeywordPlanIdeaService")

    # Build request dynamically (v28 uses get_type)
    request = client.get_type("GenerateKeywordIdeasRequest")
    request.customer_id = str(customer_id)
    request.keyword_plan_network = client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH

    request.keyword_seed.keywords.append(query)
    request.geo_target_constants.append(f"geoTargetConstants/{location_id}")

    response = keyword_plan_idea_service.generate_keyword_ideas(request=request)

    results = []
    for idea in response:
        metrics = idea.keyword_idea_metrics
        results.append({
            "keyword": idea.text,
            "avg_monthly_searches": metrics.avg_monthly_searches,
            "competition": metrics.competition.name,
        })

    return results