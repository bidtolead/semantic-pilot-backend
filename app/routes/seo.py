from fastapi import APIRouter, Header, HTTPException
from app.models.seo_models import ResearchRequest
from app.google.keyword_planner import fetch_keyword_ideas
from firebase_admin import auth as firebase_auth
from app.services.firestore import db
from google.cloud import firestore
from openai import OpenAI
import os

router = APIRouter()

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


@router.post("/seo/research")
async def run_research(
    req: ResearchRequest,
    authorization: str | None = Header(default=None),
):
    # -----------------------------------
    # AUTH CHECK
    # -----------------------------------
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")

    token = authorization.split(" ")[1]

    try:
        decoded = firebase_auth.verify_id_token(token)
        uid = decoded["uid"]
        email = decoded.get("email")
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

    # -----------------------------------
    # STEP 1: Google Keyword Planner
    # -----------------------------------
    raw_keywords = fetch_keyword_ideas(
        seed_keywords=req.suggested_keywords,
        geo_id=req.location_id,
    )

    # -----------------------------------
    # STEP 2: OpenAI call to enrich keywords
    # -----------------------------------
    prompt = f"""
    You are an SEO expert. Analyze these raw Google Keyword Planner keywords:

    {raw_keywords}

    Return only structured JSON with:
    - primary_keyword
    - intent
    - difficulty
    - suggestions (list of improved SEO keyword ideas)
    """

    gpt = client.responses.create(
        model="gpt-4.1-mini",
        input=prompt,
    )

    ai_output = gpt.output_text  # clean extracted output
    total_tokens = gpt.usage.total_tokens if gpt.usage else 0

    # -----------------------------------
    # STEP 3: Update user statistics
    # -----------------------------------
    user_ref = db.collection("users").document(uid)

    user_ref.update({
        "researchCount": firestore.Increment(1),
        "openaiTokensUsed": firestore.Increment(total_tokens),
        "lastActive": firestore.SERVER_TIMESTAMP,
    })

    # -----------------------------------
    # FINAL RESPONSE
    # -----------------------------------
    return {
        "keywords_raw": raw_keywords,
        "ai_analysis": ai_output,
        "tokens_used": total_tokens,
        "location_used": req.location,
        "location_id": req.location_id,
        "user": {
            "uid": uid,
            "email": email,
        }
    }