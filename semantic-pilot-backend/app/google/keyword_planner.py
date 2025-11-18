from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.v13.enums.types.keyword_plan_network import KeywordPlanNetworkEnum
from google.ads.googleads.v13.services.types.keyword_plan_idea_service import GenerateKeywordIdeasRequest

def fetch_keyword_ideas(query: str, location_id: str):
    client = GoogleAdsClient.load_from_storage("google-ads.yaml")

    customer_id = client.login_customer_id
    service = client.get_service("KeywordPlanIdeaService")

    request = GenerateKeywordIdeasRequest(
        customer_id=str(customer_id),
        keyword_plan_network=KeywordPlanNetworkEnum.GOOGLE_SEARCH,
        keyword_seed={"keywords": [query]},
        geo_target_constants=[f"geoTargetConstants/{location_id}"],
    )

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
