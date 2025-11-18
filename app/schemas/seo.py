# app/schemas/seo.py

from pydantic import BaseModel
from typing import Any, List, Optional


class Location(BaseModel):
    country: str
    city: Optional[str] = None
    region: Optional[str] = None


class SEOIntakeRequest(BaseModel):
    platform: str
    target_page_url: str
    location: Location
    service_or_topic: str

    suggested_keywords: List[str] = []
    negative_keywords: List[str] = []
    excluded_brands: List[str] = []
    competitors: List[str] = []

    keyword_intent: Optional[str] = None
    common_questions: List[str] = []

    target_audience: Optional[str] = None
    page_type: Optional[str] = None
    funnel_stage: Optional[str] = None
    competition_preference: Optional[str] = None


class SEOResponse(BaseModel):
    seo_report: Any
    google_ads_keywords: List[Any]
