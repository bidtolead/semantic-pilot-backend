from fastapi import APIRouter, Header, HTTPException
from app.models.seo_models import ResearchRequest
from firebase_admin import auth as firebase_auth
from app.google.keyword_planner import fetch_keyword_ideas
from app.services.firestore import db

router = APIRouter()

# Helper to authenticate user
def get_uid(authorization: str | None):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization.split(" ")[1]
    decoded = firebase_auth.verify_id_token(token)
    return decoded["uid"]


@router.post("/seo/research")
async def run_research(
    req: ResearchRequest,
    authorization: str | None = Header(default=None)
):

    uid = get_uid(authorization)

    # Firestore increment
    user_ref = db.collection("users").document(uid)
    user_ref.update({
        "researchCount": db.SERVER_TIMESTAMP,  # ensure doc exists
    })
    user_ref.update({
        "researchCount": db.Increment(1),
        "lastActivity": db.SERVER_TIMESTAMP,
        "online": True,
    })

    # RUN YOUR KEYWORD RESEARCH
    raw_keywords = fetch_keyword_ideas(
        seed_keywords=req.suggested_keywords,
        geo_id=req.location_id,
    )

    return {
        "keywords_raw": raw_keywords,
        "location_used": req.location,
        "location_id": req.location_id,
    }