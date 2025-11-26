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


@router.get("/keyword-research/run/{userId}/{intakeId}")
async def run_keyword_research(
    userId: str,
    intakeId: str,
    authorization: str | None = Header(default=None)
):
    """
    Execute keyword research based on a stored intake form.
    
    This endpoint:
    1. Loads intake from Firestore
    2. Resolves target location to GEO_ID
    3. Prepares seed keywords from intake fields
    4. Calls Google Keyword Planner API
    5. Saves raw results to Firestore under intakes/{userId}/{intakeId}/keyword_research/raw_output
    """
    uid = get_uid(authorization)
    
    # Security check: ensure the authenticated user matches the userId in path
    if uid != userId:
        raise HTTPException(status_code=403, detail="Unauthorized access to this intake")
    
    # Check user credits before proceeding
    user_ref = db.collection("users").document(userId)
    user_snapshot = user_ref.get()
    
    if not user_snapshot.exists:
        user_ref.set({
            "researchCount": 0,
            "tokenUsage": 0,
            "credits": 50,  # Initial credits for new users
            "createdAt": gcfirestore.SERVER_TIMESTAMP,
            "lastActivity": gcfirestore.SERVER_TIMESTAMP,
            "online": True,
        })
        user_snapshot = user_ref.get()
    
    user_data = user_snapshot.to_dict() or {}
    current_credits = user_data.get("credits", 0)
    
    # Check if user has enough credits (1 credit per research)
    if current_credits < 1:
        raise HTTPException(
            status_code=402,
            detail="Insufficient credits. Please contact support to add more credits."
        )
    
    # Deduct 1 credit and increment research count atomically
    user_ref.update({
        "credits": gcfirestore.Increment(-1),
        "researchCount": gcfirestore.Increment(1),
        "lastActivity": gcfirestore.SERVER_TIMESTAMP,
        "online": True,
    })
    
    # 1. Load intake from Firestore
    # Document ID format: {userId}_{intakeId}
    doc_id = f"{userId}_{intakeId}"
    intake_ref = db.collection("research_intakes").document(doc_id)
    intake_doc = intake_ref.get()
    
    if not intake_doc.exists:
        raise HTTPException(
            status_code=404, 
            detail=f"Intake not found for userId={userId}, intakeId={intakeId}"
        )
    
    intake = intake_doc.to_dict()
    
    # 2. Extract target location and resolve to GEO_ID
    target_location = intake.get("target_location", "").strip()
    if not target_location:
        raise HTTPException(
            status_code=400, 
            detail="target_location is missing in intake data"
        )
    
    # Clean location string - remove parentheses and extra info
    # Example: "Auckland (City - NZ)" -> "Auckland"
    if "(" in target_location:
        target_location = target_location.split("(")[0].strip()
    
    # Call geo suggest service to find matching GEO_ID
    geo_id = None
    try:
        client, _ = load_google_ads_client()
        service = client.get_service("GeoTargetConstantService")
        geo_request = client.get_type("SuggestGeoTargetConstantsRequest")
        geo_request.locale = "en"
        geo_request.location_names.names.append(target_location)
        
        response = service.suggest_geo_target_constants(request=geo_request)
        
        # Find first enabled geo target
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
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to resolve location '{target_location}': {str(e)}"
        )
    
    # 3. Prepare seed keywords from intake
    # Combine relevant fields into seed keywords
    seed_keywords = []
    
    # Add suggested_search_terms (split by comma)
    suggested_terms = intake.get("suggested_search_terms", "").strip()
    if suggested_terms:
        terms = [t.strip() for t in suggested_terms.split(",") if t.strip()]
        seed_keywords.extend(terms)
    
    # Optionally add product/service description as a seed
    product_desc = intake.get("product_service_description", "").strip()
    if product_desc and len(product_desc) < 100:  # Only if reasonably short
        seed_keywords.append(product_desc)
    
    # If no seed keywords found, return error
    if not seed_keywords:
        raise HTTPException(
            status_code=400,
            detail="No seed keywords found. Please provide 'suggested_search_terms' in the intake."
        )
    
    # 4. Call fetch_keyword_ideas() from google_ads.py
    try:
        raw_output = fetch_keyword_ideas(
            seed_keywords=seed_keywords,
            geo_id=int(geo_id)
        )
        
        # Log raw Google API response for debugging
        print(f"📊 Google Ads API returned {len(raw_output)} keywords")
        if raw_output:
            print(f"📊 Sample raw data (first 3 keywords):")
            for i, kw in enumerate(raw_output[:3]):
                print(f"   {i+1}. {kw.get('keyword')}: avg_monthly_searches={kw.get('avg_monthly_searches')}")
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Google Keyword Planner API failed: {str(e)}"
        )
    
    # 5. Save raw results to Firestore
    # Path: intakes/{userId}/{intakeId}/keyword_research/raw_output
    try:
        # Create nested collection structure
        keyword_research_ref = (
            db.collection("intakes")
            .document(userId)
            .collection(intakeId)
            .document("keyword_research")
        )
        
        keyword_research_ref.set({
            "raw_output": raw_output,
            "createdAt": gcfirestore.SERVER_TIMESTAMP,
            "status": "completed",
            "geo_id": geo_id,
            "target_location": target_location,
            "seed_keywords_used": seed_keywords,
            # Store first 10 keywords for easy debugging in Firestore console
            "raw_sample": raw_output[:10] if isinstance(raw_output, list) else [],
            # Store metadata from intake for reference
            "metadata": {
                "keyword_intent": intake.get("keyword_intent"),
                "buyer_journey_stage": intake.get("buyer_journey_stage"),
                "keyword_performance": intake.get("keyword_performance"),
            }
        })
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save results to Firestore: {str(e)}"
        )
    
    # 6. Step 3: Run AI keyword filtering to produce structured results
    try:
        from app.services.keyword_ai_filter import run_keyword_ai_filter
        structured = run_keyword_ai_filter(
            intake=intake,
            raw_output=raw_output,
            user_id=userId,
            research_id=intakeId,
        )

        # Mirror structured results back into the intake keyword_research doc
        # so existing frontend views that read from the intakes path work
        try:
            mirror_ref = (
                db.collection("intakes")
                .document(userId)
                .collection(intakeId)
                .document("keyword_research")
            )
            mirror_ref.set({
                "primary_keywords": structured.get("primary_keywords", []),
                "secondary_keywords": structured.get("secondary_keywords", []),
                "long_tail_keywords": structured.get("long_tail_keywords", []),
                "status": "completed",
            }, merge=True)
        except Exception:
            # Non-fatal: if mirroring fails, the canonical copy still exists under research/{userId}/{intakeId}
            pass
    except Exception as e:
        # Do not fail the entire flow if AI post-processing fails; return raw stats with error
        raise HTTPException(
            status_code=500,
            detail=f"AI keyword filtering failed: {str(e)}"
        )

    # 7. Return success response (final structured results are saved under research/{userId}/{intakeId})
    return {
        "success": True,
        "message": "Keyword research completed successfully",
        "keywords_found": len(raw_output),
        "userId": userId,
        "intakeId": intakeId,
        "structured_saved": True
    }