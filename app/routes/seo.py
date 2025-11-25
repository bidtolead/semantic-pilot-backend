from fastapi import APIRouter, Header, HTTPException
from app.models.seo_models import ResearchRequest
from firebase_admin import auth as firebase_auth
from google.cloud import firestore as gcfirestore
from app.services.google_ads import fetch_keyword_ideas
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

    # Ensure user document exists before updates
    user_ref = db.collection("users").document(uid)
    snapshot = user_ref.get()
    if not snapshot.exists:
        user_ref.set({
            "researchCount": 0,
            "createdAt": gcfirestore.SERVER_TIMESTAMP,
            "lastActivity": gcfirestore.SERVER_TIMESTAMP,
            "online": True,
        })

    # Atomic increment + activity update
    user_ref.update({
        "researchCount": gcfirestore.Increment(1),
        "lastActivity": gcfirestore.SERVER_TIMESTAMP,
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