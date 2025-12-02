from app.schemas.seo import SEOIntakeRequest
from app.services.dataforseo import fetch_keyword_ideas

async def process_seo_request(payload: SEOIntakeRequest) -> str:
    # 1) Use suggested keywords from intake as seeds
    seed_keywords = payload.suggested_keywords

    # 2) Use DataForSEO for keyword research
    keyword_ideas = fetch_keyword_ideas(
        seed_keywords=seed_keywords,
        location_name="United States"
    )

    # 3) Return the raw keyword ideas as a string
    return str(keyword_ideas)
