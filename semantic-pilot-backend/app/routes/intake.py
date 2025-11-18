from fastapi import APIRouter
from pydantic import BaseModel
import uuid

router = APIRouter()

# temporary in-memory storage
INTAKE_STORE = {}


class IntakeForm(BaseModel):
    platform: str | None = None
    business_name: str | None = None
    target_page_url: str | None = None
    target_audience: str | None = None
    target_location: str | None = None
    word_count_limit: int | None = None
    product_service_description: str | None = None
    usps: str | None = None
    competitor1: str | None = None
    competitor2: str | None = None
    page_type: str | None = None
    page_type_other_text: str | None = None
    page_objective: list[str] | None = None
    page_objective_other_text: str | None = None
    suggested_search_terms: str | None = None
    common_questions: str | None = None
    keyword_intent: str | None = None
    negative_keywords: str | None = None
    excluded_brands: str | None = None
    buyer_journey_stage: str | None = None
    keyword_performance: str | None = None


@router.post("/seo/intake")
def save_intake(form: IntakeForm):
    intake_id = str(uuid.uuid4())
    INTAKE_STORE[intake_id] = form.dict()
    return {"intake_id": intake_id}
