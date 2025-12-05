from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel
from app.models.seo_models import ResearchRequest
from firebase_admin import auth as firebase_auth
from google.cloud import firestore as gcfirestore
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
    
    # Track DataForSEO spend
    try:
        from app.services.dataforseo import get_dataforseo_cost
        dataforseo_cost = get_dataforseo_cost()
        user_ref.update({
            "dataforseoSpend": gcfirestore.Increment(dataforseo_cost)
        })
    except Exception:
        pass  # Non-critical
    
    # DEBUG: Return first keyword's raw data to inspect DataForSEO response
    debug_sample = None
    if raw_keywords and len(raw_keywords) > 0:
        debug_sample = raw_keywords[0]

    return {
        "keywords_raw": raw_keywords,
        "location_used": req.location,
        "location_id": req.location_id,
        "debug_first_keyword": debug_sample,
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
        
        # Track DataForSEO spend
        try:
            from app.services.dataforseo import get_dataforseo_cost
            dataforseo_cost = get_dataforseo_cost()
            user_ref.update({
                "dataforseoSpend": gcfirestore.Increment(dataforseo_cost)
            })
        except Exception:
            pass  # Non-critical
            
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
            "credits": 30,  # Monthly credits
            "monthlyCredits": 30,
            "dailyCreditsUsed": 0,
            "dailyLimit": 5,
            "lastCreditReset": gcfirestore.SERVER_TIMESTAMP,
            "lastDailyReset": gcfirestore.SERVER_TIMESTAMP,
            "createdAt": gcfirestore.SERVER_TIMESTAMP,
            "lastActivity": gcfirestore.SERVER_TIMESTAMP,
            "online": True,
        })
        user_snapshot = user_ref.get()
    
    user_data = user_snapshot.to_dict() or {}
    current_credits = user_data.get("credits", 0)
    daily_credits_used = user_data.get("dailyCreditsUsed", 0)
    user_role = user_data.get("role", "user")
    
    # Set daily limit based on role: 50 for admin, 5 for regular users
    daily_limit = 50 if user_role == "admin" else user_data.get("dailyLimit", 5)
    monthly_credits = user_data.get("monthlyCredits", 30)
    last_daily_reset = user_data.get("lastDailyReset")
    last_credit_reset = user_data.get("lastCreditReset")
    
    # Check and reset daily credits if needed
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    
    updates = {}
    
    # Reset daily counter if it's a new day
    if last_daily_reset:
        if isinstance(last_daily_reset, str):
            last_daily_reset = datetime.fromisoformat(last_daily_reset.replace('Z', '+00:00'))
        elif hasattr(last_daily_reset, 'replace'):
            last_daily_reset = last_daily_reset.replace(tzinfo=timezone.utc)
        
        if last_daily_reset.date() < now.date():
            updates["dailyCreditsUsed"] = 0
            updates["lastDailyReset"] = now.isoformat()
            daily_credits_used = 0
    
    # Reset monthly credits if it's a new month
    if last_credit_reset:
        if isinstance(last_credit_reset, str):
            last_credit_reset = datetime.fromisoformat(last_credit_reset.replace('Z', '+00:00'))
        elif hasattr(last_credit_reset, 'replace'):
            last_credit_reset = last_credit_reset.replace(tzinfo=timezone.utc)
        
        if last_credit_reset.month != now.month or last_credit_reset.year != now.year:
            updates["credits"] = monthly_credits
            updates["lastCreditReset"] = now.isoformat()
            current_credits = monthly_credits
    
    # Apply resets if any
    if updates:
        user_ref.update(updates)
    
    # Check daily limit first
    if daily_credits_used >= daily_limit:
        raise HTTPException(
            status_code=429,
            detail=f"Daily limit reached. You can use up to {daily_limit} credits per day. Resets tomorrow."
        )
    
    # Check if user has enough monthly credits (1 credit per research)
    if current_credits < 1:
        raise HTTPException(
            status_code=402,
            detail=f"Insufficient monthly credits. You have {current_credits}/{monthly_credits} credits remaining this month."
        )
    
    # Deduct 1 credit, increment daily usage, and increment research count atomically
    user_ref.update({
        "credits": gcfirestore.Increment(-1),
        "dailyCreditsUsed": gcfirestore.Increment(1),
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
    
    # Location cleaning is now handled inside dataforseo.fetch_keyword_ideas()
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
        # Get target URL from intake
        target_url = intake.get("target_page_url", "").strip()
        
        raw_output = dfs_fetch_keyword_ideas(
            seed_keywords=seed_keywords,
            location_name=target_location,
            url=target_url if target_url else None,
        )
        
        # Track DataForSEO spend
        try:
            from app.services.dataforseo import get_dataforseo_cost
            dataforseo_cost = get_dataforseo_cost()
            print(f"💰 DataForSEO cost tracked: ${dataforseo_cost:.4f}", flush=True)
            user_ref.update({
                "dataforseoSpend": gcfirestore.Increment(dataforseo_cost)
            })
        except Exception as e:
            print(f"⚠️ Failed to track DataForSEO cost: {e}", flush=True)
        
        # Filter keywords based on intake data (negative keywords, excluded brands, location relevance)
        try:
            from app.services.dataforseo import filter_keywords_by_intake
            negative_kws = intake.get("negative_keywords", "").strip()
            excluded_brands = intake.get("excluded_brands", "").strip()
            
            print(f"\n📋 Applying multi-stage filters...")
            raw_output = filter_keywords_by_intake(
                keywords=raw_output,
                negative_keywords=negative_kws if negative_kws else None,
                excluded_brands=excluded_brands if excluded_brands else None,
                location_name=target_location,  # Pass the target location for relevance filtering
            )
        except Exception as e:
            print(f"⚠️ Local filtering failed: {e}", flush=True)
            # Continue without filtering if it fails
            
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"DataForSEO API failed: {str(e)}"
        )
    
    # 5. Run AI keyword filtering to produce structured results
    try:
        from app.services.keyword_ai_filter import run_keyword_ai_filter
        structured = run_keyword_ai_filter(
            intake=intake,
            raw_output=raw_output,
            user_id=userId,
            research_id=intakeId,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"AI keyword filtering failed: {str(e)}"
        )
    
    # 6. Save both raw and structured results to Firestore in ONE operation
    # Path: intakes/{userId}/{intakeId}/keyword_research
    try:
        # DEBUG: Log what we're about to save
        print(f"\n=== SAVING TO FIRESTORE ===")
        print(f"User: {userId}, Intake: {intakeId}")
        print(f"Raw keywords: {len(raw_output)}")
        print(f"Primary: {len(structured.get('primary_keywords', []))}")
        print(f"Secondary: {len(structured.get('secondary_keywords', []))}")
        print(f"Long-tail: {len(structured.get('long_tail_keywords', []))}")
        
        # Log first 3 keywords from raw_output to see DataForSEO data
        print(f"\n=== FIRST 3 RAW KEYWORDS FROM DATAFORSEO ===")
        for idx, raw_kw in enumerate(raw_output[:3]):
            print(f"[{idx}] {raw_kw.get('keyword')}: avg_monthly_searches={raw_kw.get('avg_monthly_searches')}, competition={raw_kw.get('competition')}")
        
        # Log first primary keyword with all fields
        if structured.get("primary_keywords"):
            pk = structured["primary_keywords"][0]
            print(f"\n=== FIRST PRIMARY KEYWORD (FINAL FOR FIRESTORE) ===")
            print(f"  keyword: {pk.get('keyword')}")
            print(f"  search_volume: {pk.get('search_volume')} (type: {type(pk.get('search_volume'))})")
            print(f"  competition: {pk.get('competition')}")
            print(f"  competition_index: {pk.get('competition_index')}")
            print(f"  low_bid: {pk.get('low_top_of_page_bid_micros')}")
            print(f"  high_bid: {pk.get('high_top_of_page_bid_micros')}")
            print(f"  trend_yoy: {pk.get('trend_yoy')}")
            print(f"  Full object: {pk}")
        
        # Log first secondary keyword
        if structured.get("secondary_keywords"):
            sk = structured["secondary_keywords"][0]
            print(f"\n=== FIRST SECONDARY KEYWORD ===")
            print(f"  keyword: {sk.get('keyword')}")
            print(f"  search_volume: {sk.get('search_volume')} (type: {type(sk.get('search_volume'))})")
        
        
        keyword_research_ref = (
            db.collection("intakes")
            .document(userId)
            .collection(intakeId)
            .document("keyword_research")
        )
        
        # Single write with all data - use merge=False to fully replace any stale data
        keyword_research_ref.set({
            # Structured results (for frontend display)
            "primary_keywords": structured.get("primary_keywords", []),
            "secondary_keywords": structured.get("secondary_keywords", []),
            "long_tail_keywords": structured.get("long_tail_keywords", []),
            # Raw data (for debugging and audit trail)
            "raw_output": raw_output,
            "raw_sample": raw_output[:10] if isinstance(raw_output, list) else [],
            # Metadata
            "status": "completed",
            "geo_id": geo_id,
            "target_location": target_location,
            "seed_keywords_used": seed_keywords,
            "createdAt": gcfirestore.SERVER_TIMESTAMP,
            "metadata": {
                "keyword_intent": intake.get("keyword_intent"),
                "buyer_journey_stage": intake.get("buyer_journey_stage"),
                "keyword_performance": intake.get("keyword_performance"),
            }
        }, merge=False)
        
        print(f"✅ Saved to Firestore successfully")
    except Exception as e:
        print(f"❌ Failed to save: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save results to Firestore: {str(e)}"
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


@router.delete("/keyword-research/delete/{userId}/{intakeId}")
async def delete_keyword_research(
    userId: str,
    intakeId: str,
    authorization: str | None = Header(default=None)
):
    """
    Delete keyword research data to allow re-running with fresh data.
    Useful for clearing stale cached results.
    """
    uid = get_uid(authorization)
    
    # Security check
    if uid != userId:
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    try:
        # Delete the keyword_research document
        keyword_research_ref = (
            db.collection("intakes")
            .document(userId)
            .collection(intakeId)
            .document("keyword_research")
        )
        keyword_research_ref.delete()
        
        return {
            "success": True,
            "message": f"Deleted keyword research for intakeId={intakeId}. You can now re-run the research."
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete research: {str(e)}"
        )


@router.post("/keyword-research/reprocess/{userId}/{intakeId}")
async def reprocess_keyword_research(
    userId: str,
    intakeId: str,
    authorization: str | None = Header(default=None)
):
    """
    Re-run the AI filter on existing raw_output to fix stale data.
    Use this to update old research with new DataForSEO metrics without re-running the API.
    """
    uid = get_uid(authorization)
    
    # Security check
    if uid != userId:
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    try:
        # Get existing keyword_research document
        keyword_research_ref = (
            db.collection("intakes")
            .document(userId)
            .collection(intakeId)
            .document("keyword_research")
        )
        doc = keyword_research_ref.get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail="No keyword research found")
        
        data = doc.to_dict()
        raw_output = data.get("raw_output", [])
        
        if not raw_output:
            raise HTTPException(status_code=400, detail="No raw_output data found to reprocess")
        
        # Get intake data
        intake_doc_id = f"{userId}_{intakeId}"
        intake_ref = db.collection("research_intakes").document(intake_doc_id)
        intake_doc = intake_ref.get()
        
        if not intake_doc.exists:
            raise HTTPException(status_code=404, detail="Intake not found")
        
        intake = intake_doc.to_dict()
        
        # Re-run AI filter
        from app.services.keyword_ai_filter import run_keyword_ai_filter
        structured = run_keyword_ai_filter(
            intake=intake,
            raw_output=raw_output,
            user_id=userId,
            research_id=intakeId,
        )
        
        # Save updated structured data (merge=False to fully replace)
        keyword_research_ref.set({
            "primary_keywords": structured.get("primary_keywords", []),
            "secondary_keywords": structured.get("secondary_keywords", []),
            "long_tail_keywords": structured.get("long_tail_keywords", []),
            "raw_output": raw_output,
            "raw_sample": raw_output[:10] if isinstance(raw_output, list) else [],
            "status": "completed",
            "geo_id": data.get("geo_id"),
            "target_location": data.get("target_location"),
            "seed_keywords_used": data.get("seed_keywords_used", []),
            "createdAt": data.get("createdAt"),
            "reprocessedAt": gcfirestore.SERVER_TIMESTAMP,
            "metadata": data.get("metadata", {}),
        }, merge=False)
        
        return {
            "success": True,
            "message": "Research reprocessed successfully",
            "primary_keywords_count": len(structured.get("primary_keywords", [])),
            "secondary_keywords_count": len(structured.get("secondary_keywords", [])),
            "long_tail_keywords_count": len(structured.get("long_tail_keywords", [])),
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reprocess research: {str(e)}"
        )