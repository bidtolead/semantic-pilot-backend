from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from app.models.seo_models import ResearchRequest
from firebase_admin import auth as firebase_auth
from google.cloud import firestore as gcfirestore
from app.services.google_ads import fetch_keyword_ideas, load_google_ads_client
from app.services.firestore import db
from app.services.keyword_planner_builder import build_keyword_planner_request

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


# Request model for keyword research endpoint
class KeywordResearchRequest(BaseModel):
    userId: str
    intakeId: str


@router.post("/google-ads/keyword-research")
async def keyword_research(
    req: KeywordResearchRequest,
    authorization: str | None = Header(default=None)
):
    """
    Execute keyword research based on a stored intake form.
    
    1. Loads intake from Firestore
    2. Resolves target location to GEO_ID
    3. Builds Keyword Planner request
    4. Fetches keyword ideas from Google Ads
    5. Saves results to Firestore
    """
    uid = get_uid(authorization)
    
    # 1. Load intake from Firestore
    intake_ref = db.collection("research_intakes").document(req.intakeId)
    intake_doc = intake_ref.get()
    
    if not intake_doc.exists:
        raise HTTPException(status_code=404, detail=f"Intake {req.intakeId} not found")
    
    intake = intake_doc.to_dict()
    
    # 2. Extract target location and resolve to GEO_ID
    target_location = intake.get("target_location", "").strip()
    if not target_location:
        raise HTTPException(status_code=400, detail="target_location is required in intake")
    
    # Call geo suggest service to find matching GEO_ID
    try:
        client, _ = load_google_ads_client()
        service = client.get_service("GeoTargetConstantService")
        request = client.get_type("SuggestGeoTargetConstantsRequest")
        request.locale = "en"
        request.location_names.names.append(target_location)
        
        response = service.suggest_geo_target_constants(request=request)
        
        # Find first enabled geo target
        geo_id = None
        for suggestion in response.geo_target_constant_suggestions:
            geo = suggestion.geo_target_constant
            if geo.status.name == "ENABLED":
                geo_id = str(geo.id)
                break
        
        if not geo_id:
            raise HTTPException(
                status_code=400,
                detail=f"No matching geo target found for location: {target_location}"
            )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to resolve location '{target_location}': {str(e)}"
        )
    
    # 3. Build Keyword Planner request using helper function
    kp_payload = build_keyword_planner_request(intake, geo_id)
    
    # 4. Fetch keyword ideas from Google Ads
    try:
        raw_keyword_data = fetch_keyword_ideas(
            seed_keywords=kp_payload["seed_keywords"],
            geo_id=int(kp_payload["geo_id"]),
            landing_page=kp_payload["landing_page"],
            competitor_urls=kp_payload["competitor_urls"]
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Google Ads keyword research failed: {str(e)}"
        )
    
    # 5. Save results to Firestore
    results_ref = db.collection("keyword_research_results").document(req.intakeId)
    results_ref.set({
        "intakeId": req.intakeId,
        "userId": req.userId,
        "createdAt": gcfirestore.SERVER_TIMESTAMP,
        "raw_keyword_data": raw_keyword_data,
        "status": "completed"
    })
    
    # 6. Return success response
    return {
        "status": "ok",
        "intakeId": req.intakeId
    }