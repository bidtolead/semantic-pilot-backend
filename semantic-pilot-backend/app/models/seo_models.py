from pydantic import BaseModel

class LocationModel(BaseModel):
    country: str
    region: str
    city: str

class ResearchRequest(BaseModel):
    platform: str
    target_page_url: str
    service_or_topic: str
    suggested_keywords: list[str]
    negative_keywords: list[str]
    excluded_brands: list[str]
    competitors: list[str]
    keyword_intent: str
    common_questions: list[str]
    target_audience: str
    page_type: str
    funnel_stage: str
    competition_preference: str

    location: LocationModel
    location_id: int | None = None
