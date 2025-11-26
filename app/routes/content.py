from fastapi import APIRouter, HTTPException, Depends, Query
from app.utils.auth import verify_token
from app.services.firestore import db
from app.services.content_generator import generate_blog_ideas, generate_meta_tags, generate_page_content

router = APIRouter(prefix="/content", tags=["content"])


@router.get("/blog-ideas/{user_id}/{research_id}")
async def handle_blog_ideas(
    user_id: str,
    research_id: str,
    token_data: dict = Depends(verify_token),
    generate: bool = Query(default=True, description="Generate new ideas if true, otherwise just retrieve"),
):
    """Generate or retrieve blog ideas based on intake and keywords."""
    
    # Verify user owns this research
    if token_data["uid"] != user_id:
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
