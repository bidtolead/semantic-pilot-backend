from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel
from app.models.seo_models import ResearchRequest
from firebase_admin import auth as firebase_auth
from google.cloud import firestore as gcfirestore
from app.services.google_ads import load_google_ads_client
from app.services.dataforseo import fetch_keyword_ideas as dfs_fetch_keyword_ideas
from app.services.firestore import db
from app.services.keyword_planner_builder import build_keyword_planner_request
from slowapi import Limiter
from slowapi.util import get_remote_address

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

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
    # Switch to DataForSEO for keyword collection
    raw_keywords = dfs_fetch_keyword_ideas(
        seed_keywords=req.suggested_keywords,
        location_name=req.location,
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
@limiter.limit("10/hour")  # Max 10 keyword research requests per hour per IP
async def keyword_research(
    request: Request,
    req: KeywordResearchRequest,
    authorization: str | None = Header(default=None)
):
    """
    Execute keyword research based on a stored intake form.
    ADMIN ONLY - Consumes Google Ads API quota.
    Rate limited: 10 requests/hour per IP.
    
    1. Loads intake from Firestore
    2. Resolves target location to GEO_ID
    3. Builds Keyword Planner request
    4. Fetches keyword ideas from Google Ads
    5. Saves results to Firestore
    """
    # Verify admin access
    uid = get_uid(authorization)
    user_ref = db.collection("users").document(uid)
    user_doc = user_ref.get()
    if not user_doc.exists or user_doc.to_dict().get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
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
    # DataForSEO uses location_name directly, skip Google Ads geo resolution
    geo_id = None
    
    # 3. Build Keyword Planner request using helper function
    kp_payload = build_keyword_planner_request(intake, geo_id)
    
    # 4. Fetch keyword ideas from Google Ads
    try:
        raw_keyword_data = dfs_fetch_keyword_ideas(
            seed_keywords=kp_payload["seed_keywords"],
            location_name=target_location,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"DataForSEO keyword research failed: {str(e)}"
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
    # DataForSEO flow: no geo_id required, use location_name directly
    
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
        raw_output = dfs_fetch_keyword_ideas(
            seed_keywords=seed_keywords,
            location_name=target_location,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"DataForSEO API failed: {str(e)}"
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

    # 7. Increment public stats counter
    try:
        db.collection("system").document("stats").update({
            "searches_ran": gcfirestore.Increment(1)
        })
    except Exception:
        pass  # Non-critical
    
    # 8. Return success response (final structured results are saved under research/{userId}/{intakeId})
    return {
        "success": True,
        "message": "Keyword research completed successfully",
        "keywords_found": len(raw_output),
        "userId": userId,
        "intakeId": intakeId,
        "structured_saved": True
    }


@router.get("/keyword-research/debug/{userId}/{intakeId}")
async def debug_keyword_research(
    userId: str,
    intakeId: str,
    authorization: str | None = Header(default=None)
):
    """
    Debug endpoint to view raw Google Ads data vs AI-processed data.
    Returns both the raw Google API response and the final structured keywords.
    """
    uid = get_uid(authorization)
    
    # Security check
    if uid != userId:
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    # Fetch raw Google data
    raw_ref = (
        db.collection("intakes")
        .document(userId)
        .collection(intakeId)
        .document("keyword_research")
    )
    raw_doc = raw_ref.get()
    
    if not raw_doc.exists:
        raise HTTPException(status_code=404, detail="No keyword research found")
    
    raw_data = raw_doc.to_dict()
    raw_output = raw_data.get("raw_output", [])
    
    # Fetch processed/structured data
    structured_keywords = {
        "primary_keywords": raw_data.get("primary_keywords", []),
        "secondary_keywords": raw_data.get("secondary_keywords", []),
        "long_tail_keywords": raw_data.get("long_tail_keywords", []),
    }
    
    # Build comparison report
    comparison = []
    all_structured = (
        structured_keywords.get("primary_keywords", []) +
        structured_keywords.get("secondary_keywords", []) +
        structured_keywords.get("long_tail_keywords", [])
    )
    
    for kw in all_structured:
        keyword_text = kw.get("keyword", "").lower()
        ai_volume = kw.get("search_volume")
        
        # Find matching keyword in raw Google data
        google_match = next(
            (item for item in raw_output if item.get("keyword", "").lower() == keyword_text),
            None
        )
        
        google_volume = google_match.get("avg_monthly_searches") if google_match else None
        
        comparison.append({
            "keyword": kw.get("keyword"),
            "google_volume": google_volume,
            "ai_volume": ai_volume,
            "match": google_volume == ai_volume if google_volume is not None else None,
            "category": "primary" if kw in structured_keywords.get("primary_keywords", []) else 
                       "secondary" if kw in structured_keywords.get("secondary_keywords", []) else "long_tail"
        })
    
    return {
        "userId": userId,
        "intakeId": intakeId,
        "total_google_keywords": len(raw_output),
        "total_structured_keywords": len(all_structured),
        "comparison": comparison,
        "raw_google_sample": raw_output[:10],  # First 10 for inspection
        "mismatches": [c for c in comparison if c.get("match") == False],
    }