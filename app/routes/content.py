from fastapi import APIRouter, HTTPException, Depends, Query, Request
from app.utils.auth import verify_token
from app.services.firestore import db
from app.services.content_generator import (
    generate_blog_ideas, 
    generate_meta_tags, 
    generate_page_content,
    generate_google_ads_ad_copy,
    generate_google_ads_landing_page,
    generate_google_ads_negative_keywords
)
from google.cloud import firestore as gcfirestore
from slowapi import Limiter
from slowapi.util import get_remote_address

router = APIRouter(prefix="/content", tags=["content"])
limiter = Limiter(key_func=get_remote_address)


@router.get("/blog-ideas/{user_id}/{research_id}")
@limiter.limit("20/hour")  # Max 20 content generations per hour per IP
async def handle_blog_ideas(
    request: Request,
    user_id: str,
    research_id: str,
    token_data: dict = Depends(verify_token),
    generate: bool = Query(default=True, description="Generate new ideas if true, otherwise just retrieve"),
):
    """Generate or retrieve blog ideas based on intake and keywords. ADMIN ONLY. Rate limited: 20/hour."""
    
    # Verify admin access AND user owns this research
    uid = token_data["uid"]
    user_ref = db.collection("users").document(uid)
    user_doc = user_ref.get()
    if not user_doc.exists or user_doc.to_dict().get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    if uid != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    try:
        # Check if blog ideas already exist
        doc_ref = db.collection("intakes").document(user_id).collection(research_id).document("blog_ideas")
        doc = doc_ref.get()
        
        # If exists and not forcing regeneration, return existing
        if doc.exists and not generate:
            return {
                "status": "success",
                "data": doc.to_dict(),
            }
        
        # Check user credits before generating new content
        user_ref = db.collection("users").document(user_id)
        user_snapshot = user_ref.get()
        
        if not user_snapshot.exists:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_data = user_snapshot.to_dict() or {}
        current_credits = user_data.get("credits", 0)
        user_role = user_data.get("role", "user")
        
        # Skip credit check for admin users
        if user_role != "admin":
            # Check if user has enough credits (1 credit per content generation)
            if current_credits < 1:
                raise HTTPException(
                    status_code=402,
                    detail="Insufficient credits. Please contact support to add more credits."
                )
            
            # Deduct 1 credit
            user_ref.update({
                "credits": gcfirestore.Increment(-1),
                "lastActivity": gcfirestore.SERVER_TIMESTAMP,
            })
        
        # Generate new blog ideas
        doc_id = f"{user_id}_{research_id}"
        intake_ref = db.collection("research_intakes").document(doc_id)
        intake_doc = intake_ref.get()
        
        if not intake_doc.exists:
            raise HTTPException(status_code=404, detail="Intake not found")
        
        intake = intake_doc.to_dict()
        
        # Fetch keyword research results
        keywords_ref = db.collection("intakes").document(user_id).collection(research_id).document("keyword_research")
        keywords_doc = keywords_ref.get()
        
        if not keywords_doc.exists:
            raise HTTPException(status_code=404, detail="Keywords not found")
        
        keywords = keywords_doc.to_dict()
        
        # Generate blog ideas
        result = generate_blog_ideas(
            intake=intake,
            keywords=keywords,
            user_id=user_id,
            research_id=research_id,
        )
        
        return {
            "status": "success",
            "data": result,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/meta-tags/{user_id}/{research_id}")
async def handle_meta_tags(
    user_id: str,
    research_id: str,
    token_data: dict = Depends(verify_token),
    generate: bool = Query(default=True, description="Generate new meta tags if true, otherwise just retrieve"),
):
    """Generate or retrieve meta tags based on intake and keywords."""
    
    # Verify user owns this research
    if token_data["uid"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    try:
        # Check if meta tags already exist
        doc_ref = db.collection("intakes").document(user_id).collection(research_id).document("meta_tags")
        doc = doc_ref.get()
        
        # If exists and not forcing regeneration, return existing
        if doc.exists and not generate:
            return {
                "status": "success",
                "data": doc.to_dict(),
            }
        
        # Check user credits before generating new content
        user_ref = db.collection("users").document(user_id)
        user_snapshot = user_ref.get()
        
        if not user_snapshot.exists:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_data = user_snapshot.to_dict() or {}
        current_credits = user_data.get("credits", 0)
        user_role = user_data.get("role", "user")
        
        # Skip credit check for admin users
        if user_role != "admin":
            # Check if user has enough credits (1 credit per content generation)
            if current_credits < 1:
                raise HTTPException(
                    status_code=402,
                    detail="Insufficient credits. Please contact support to add more credits."
                )
            
            # Deduct 1 credit
            user_ref.update({
                "credits": gcfirestore.Increment(-1),
                "lastActivity": gcfirestore.SERVER_TIMESTAMP,
            })
        
        # Generate new meta tags
        doc_id = f"{user_id}_{research_id}"
        intake_ref = db.collection("research_intakes").document(doc_id)
        intake_doc = intake_ref.get()
        
        if not intake_doc.exists:
            raise HTTPException(status_code=404, detail="Intake not found")
        
        intake = intake_doc.to_dict()
        
        # Fetch keyword research results
        keywords_ref = db.collection("intakes").document(user_id).collection(research_id).document("keyword_research")
        keywords_doc = keywords_ref.get()
        
        if not keywords_doc.exists:
            raise HTTPException(status_code=404, detail="Keywords not found")
        
        keywords = keywords_doc.to_dict()
        
        # Generate meta tags
        result = generate_meta_tags(
            intake=intake,
            keywords=keywords,
            user_id=user_id,
            research_id=research_id,
        )
        
        return {
            "status": "success",
            "data": result,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/page-content/{user_id}/{research_id}")
async def handle_page_content(
    user_id: str,
    research_id: str,
    token_data: dict = Depends(verify_token),
    generate: bool = Query(default=True, description="Generate new content if true, otherwise just retrieve"),
):
    """Generate or retrieve full page content based on intake and keywords."""
    
    # Verify user owns this research
    if token_data["uid"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    try:
        # Check if page content already exists
        doc_ref = db.collection("intakes").document(user_id).collection(research_id).document("page_content")
        doc = doc_ref.get()
        
        # If exists and not forcing regeneration, return existing
        if doc.exists and not generate:
            return {
                "status": "success",
                "data": doc.to_dict(),
            }
        
        # Check user credits before generating new content
        user_ref = db.collection("users").document(user_id)
        user_snapshot = user_ref.get()
        
        if not user_snapshot.exists:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_data = user_snapshot.to_dict() or {}
        current_credits = user_data.get("credits", 0)
        user_role = user_data.get("role", "user")
        
        # Skip credit check for admin users
        if user_role != "admin":
            # Check if user has enough credits (1 credit per content generation)
            if current_credits < 1:
                raise HTTPException(
                    status_code=402,
                    detail="Insufficient credits. Please contact support to add more credits."
                )
            
            # Deduct 1 credit
            user_ref.update({
                "credits": gcfirestore.Increment(-1),
                "lastActivity": gcfirestore.SERVER_TIMESTAMP,
            })
        
        # Generate new page content
        doc_id = f"{user_id}_{research_id}"
        intake_ref = db.collection("research_intakes").document(doc_id)
        intake_doc = intake_ref.get()
        
        if not intake_doc.exists:
            raise HTTPException(status_code=404, detail="Intake not found")
        
        intake = intake_doc.to_dict()
        
        # Fetch keyword research results
        keywords_ref = db.collection("intakes").document(user_id).collection(research_id).document("keyword_research")
        keywords_doc = keywords_ref.get()
        
        if not keywords_doc.exists:
            raise HTTPException(status_code=404, detail="Keywords not found")
        
        keywords = keywords_doc.to_dict()
        
        # Generate page content
        result = generate_page_content(
            intake=intake,
            keywords=keywords,
            user_id=user_id,
            research_id=research_id,
        )
        
        return {
            "status": "success",
            "data": result,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# POST endpoints for direct content generation (used by frontend)
@router.post("/page-content/")
async def generate_page_content_post(request: Request):
    """Generate page content directly from frontend request"""
    user_data = await verify_token(request)
    user_id = user_data.get("uid")
    
    try:
        body = await request.json()
        primary_keywords = body.get("primary_keywords", [])
        secondary_keywords = body.get("secondary_keywords", [])
        long_tail_keywords = body.get("long_tail_keywords", [])
        user_intake_form = body.get("user_intake_form", {})
        research_data = body.get("research_data", {})
        
        # Check if user is admin
        user_role = user_data.get("role", "user")
        if user_role != "admin":
            # For regular users, check credits
            user_doc = db.collection("users").document(user_id).get()
            if not user_doc.exists():
                raise HTTPException(status_code=404, detail="User not found")
            
            credits = user_doc.get("credits") or 0
            if credits < 1:
                raise HTTPException(status_code=402, detail="Insufficient credits. Please purchase more credits.")
            
            # Deduct 1 credit
            db.collection("users").document(user_id).update({
                "credits": gcfirestore.Increment(-1)
            })
        
        result = generate_page_content(
            primary_keywords=primary_keywords,
            secondary_keywords=secondary_keywords,
            long_tail_keywords=long_tail_keywords,
            user_intake_form=user_intake_form,
            research_data=research_data,
            user_id=user_id,
        )
        
        return {
            "status": "success",
            "data": result,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/blog-ideas/")
async def generate_blog_ideas_post(request: Request):
    """Generate blog ideas directly from frontend request"""
    user_data = await verify_token(request)
    user_id = user_data.get("uid")
    
    try:
        body = await request.json()
        primary_keywords = body.get("primary_keywords", [])
        user_intake_form = body.get("user_intake_form", {})
        research_data = body.get("research_data", {})
        
        # Check if user is admin
        user_role = user_data.get("role", "user")
        if user_role != "admin":
            # For regular users, check credits
            user_doc = db.collection("users").document(user_id).get()
            if not user_doc.exists():
                raise HTTPException(status_code=404, detail="User not found")
            
            credits = user_doc.get("credits") or 0
            if credits < 1:
                raise HTTPException(status_code=402, detail="Insufficient credits. Please purchase more credits.")
            
            # Deduct 1 credit
            db.collection("users").document(user_id).update({
                "credits": gcfirestore.Increment(-1)
            })
        
        result = generate_blog_ideas(
            primary_keywords=primary_keywords,
            user_intake_form=user_intake_form,
            research_data=research_data,
            user_id=user_id,
        )
        
        return {
            "status": "success",
            "data": result,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/meta-tags/")
async def generate_meta_tags_post(request: Request):
    """Generate meta tags directly from frontend request"""
    user_data = await verify_token(request)
    user_id = user_data.get("uid")
    
    try:
        body = await request.json()
        primary_keywords = body.get("primary_keywords", [])
        secondary_keywords = body.get("secondary_keywords", [])
        long_tail_keywords = body.get("long_tail_keywords", [])
        user_intake_form = body.get("user_intake_form", {})
        research_data = body.get("research_data", {})
        
        # Check if user is admin
        user_role = user_data.get("role", "user")
        if user_role != "admin":
            # For regular users, check credits
            user_doc = db.collection("users").document(user_id).get()
            if not user_doc.exists():
                raise HTTPException(status_code=404, detail="User not found")
            
            credits = user_doc.get("credits") or 0
            if credits < 1:
                raise HTTPException(status_code=402, detail="Insufficient credits. Please purchase more credits.")
            
            # Deduct 1 credit
            db.collection("users").document(user_id).update({
                "credits": gcfirestore.Increment(-1)
            })
        
        result = generate_meta_tags(
            primary_keywords=primary_keywords,
            secondary_keywords=secondary_keywords,
            long_tail_keywords=long_tail_keywords,
            user_intake_form=user_intake_form,
            research_data=research_data,
            user_id=user_id,
        )
        
        return {
            "status": "success",
            "data": result,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ad-copy/{user_id}/{research_id}")
@limiter.limit("20/hour")
async def handle_ad_copy(
    request: Request,
    user_id: str,
    research_id: str,
    token_data: dict = Depends(verify_token),
    generate: bool = Query(default=True),
):
    """Generate or retrieve Google Ads ad copy. ADMIN AND TESTER. Rate limited: 20/hour."""
    
    uid = token_data["uid"]
    user_ref = db.collection("users").document(uid)
    user_doc = user_ref.get()
    user_role = user_doc.to_dict().get("role") if user_doc.exists else None
    
    # Allow both admin and tester roles
    if not user_doc.exists or user_role not in ["admin", "tester"]:
        raise HTTPException(status_code=403, detail="Admin or Tester access required")
    
    if uid != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    try:
        doc_ref = db.collection("intakes").document(user_id).collection(research_id).document("ad_copy")
        doc = doc_ref.get()
        
        if doc.exists and not generate:
            return {"status": "success", "data": doc.to_dict()}
        
        # Credit check
        user_snapshot = user_ref.get()
        if not user_snapshot.exists:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_data = user_snapshot.to_dict() or {}
        if user_data.get("credits", 0) < 1:
            raise HTTPException(status_code=402, detail="Insufficient credits")
        
        user_ref.update({
            "credits": gcfirestore.Increment(-1),
            "lastActivity": gcfirestore.SERVER_TIMESTAMP,
        })
        
        # Load intake and keywords
        doc_id = f"{user_id}_{research_id}"
        intake_doc = db.collection("research_intakes").document(doc_id).get()
        if not intake_doc.exists:
            raise HTTPException(status_code=404, detail="Intake not found")
        
        keywords_doc = db.collection("intakes").document(user_id).collection(research_id).document("keyword_research").get()
        if not keywords_doc.exists:
            raise HTTPException(status_code=404, detail="Keywords not found")
        
        result = generate_google_ads_ad_copy(
            intake=intake_doc.to_dict(),
            keywords=keywords_doc.to_dict(),
            user_id=user_id,
            research_id=research_id,
        )
        
        return {"status": "success", "data": result}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/landing-page/{user_id}/{research_id}")
@limiter.limit("20/hour")
async def handle_landing_page(
    request: Request,
    user_id: str,
    research_id: str,
    token_data: dict = Depends(verify_token),
    generate: bool = Query(default=True),
):
    """Generate or retrieve Google Ads landing page recommendations. ADMIN AND TESTER. Rate limited: 20/hour."""
    
    uid = token_data["uid"]
    user_ref = db.collection("users").document(uid)
    user_doc = user_ref.get()
    user_role = user_doc.to_dict().get("role") if user_doc.exists else None
    
    # Allow both admin and tester roles
    if not user_doc.exists or user_role not in ["admin", "tester"]:
        raise HTTPException(status_code=403, detail="Admin or Tester access required")
    
    if uid != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    try:
        doc_ref = db.collection("intakes").document(user_id).collection(research_id).document("landing_page")
        doc = doc_ref.get()
        
        if doc.exists and not generate:
            return {"status": "success", "data": doc.to_dict()}
        
        user_snapshot = user_ref.get()
        if not user_snapshot.exists:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_data = user_snapshot.to_dict() or {}
        if user_data.get("credits", 0) < 1:
            raise HTTPException(status_code=402, detail="Insufficient credits")
        
        user_ref.update({
            "credits": gcfirestore.Increment(-1),
            "lastActivity": gcfirestore.SERVER_TIMESTAMP,
        })
        
        doc_id = f"{user_id}_{research_id}"
        intake_doc = db.collection("research_intakes").document(doc_id).get()
        if not intake_doc.exists:
            raise HTTPException(status_code=404, detail="Intake not found")
        
        keywords_doc = db.collection("intakes").document(user_id).collection(research_id).document("keyword_research").get()
        if not keywords_doc.exists:
            raise HTTPException(status_code=404, detail="Keywords not found")
        
        result = generate_google_ads_landing_page(
            intake=intake_doc.to_dict(),
            keywords=keywords_doc.to_dict(),
            user_id=user_id,
            research_id=research_id,
        )
        
        return {"status": "success", "data": result}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/negative-keywords/{user_id}/{research_id}")
@limiter.limit("20/hour")
async def handle_negative_keywords(
    request: Request,
    user_id: str,
    research_id: str,
    token_data: dict = Depends(verify_token),
    generate: bool = Query(default=True),
):
    """Generate or retrieve negative keyword recommendations. ADMIN AND TESTER. Rate limited: 20/hour."""
    
    uid = token_data["uid"]
    user_ref = db.collection("users").document(uid)
    user_doc = user_ref.get()
    user_role = user_doc.to_dict().get("role") if user_doc.exists else None
    
    # Allow both admin and tester roles
    if not user_doc.exists or user_role not in ["admin", "tester"]:
        raise HTTPException(status_code=403, detail="Admin or Tester access required")
    
    if uid != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    try:
        doc_ref = db.collection("intakes").document(user_id).collection(research_id).document("negative_keywords")
        doc = doc_ref.get()
        
        if doc.exists and not generate:
            return {"status": "success", "data": doc.to_dict()}
        
        user_snapshot = user_ref.get()
        if not user_snapshot.exists:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_data = user_snapshot.to_dict() or {}
        if user_data.get("credits", 0) < 1:
            raise HTTPException(status_code=402, detail="Insufficient credits")
        
        user_ref.update({
            "credits": gcfirestore.Increment(-1),
            "lastActivity": gcfirestore.SERVER_TIMESTAMP,
        })
        
        doc_id = f"{user_id}_{research_id}"
        intake_doc = db.collection("research_intakes").document(doc_id).get()
        if not intake_doc.exists:
            raise HTTPException(status_code=404, detail="Intake not found")
        
        keywords_doc = db.collection("intakes").document(user_id).collection(research_id).document("keyword_research").get()
        if not keywords_doc.exists:
            raise HTTPException(status_code=404, detail="Keywords not found")
        
        result = generate_google_ads_negative_keywords(
            intake=intake_doc.to_dict(),
            keywords=keywords_doc.to_dict(),
            user_id=user_id,
            research_id=research_id,
        )
        
        return {"status": "success", "data": result}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
