from app.schemas.seo import SEOIntakeRequest
from app.services.google_ads import fetch_keyword_ideas

async def process_seo_request(payload: SEOIntakeRequest) -> str:
    # 1) Use suggested keywords from intake as seeds
    seed_keywords = payload.suggested_keywords

    # 2) Optionally map location.country to geo IDs later.
    # For now, use default USA (2840) as set in google_ads.py
    keyword_ideas = fetch_keyword_ideas(seed_keywords)

    # 3) For now just return the raw keyword ideas as a string
    # (later we’ll feed this into OpenAI for the smart keyword selection)
    return str(keyword_ideas)
