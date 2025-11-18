from fastapi import APIRouter
from app.models.seo_models import ResearchRequest
from app.google.keyword_planner import fetch_keyword_ideas

router = APIRouter()

@router.post("/seo/research")
async def run_research(req: ResearchRequest):

    raw_keywords = fetch_keyword_ideas(
        seed_keywords=req.suggested_keywords,
        geo_id=req.location_id,
    )

    return {
        "keywords_raw": raw_keywords,
        "location_used": req.location,
        "location_id": req.location_id,
    }
