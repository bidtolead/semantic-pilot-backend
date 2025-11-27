from fastapi import APIRouter, HTTPException, Depends, Query, Request
from app.utils.auth import verify_token
from app.services.firestore import db
from app.services.content_generator import generate_blog_ideas, generate_meta_tags, generate_page_content
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
