from fastapi import APIRouter, HTTPException, Depends
from app.utils.auth import verify_token
from app.services.firestore import db
from app.services.content_generator import generate_blog_ideas, generate_meta_tags

router = APIRouter(prefix="/content", tags=["content"])


@router.post("/blog-ideas/{user_id}/{research_id}")
async def create_blog_ideas(
    user_id: str,
    research_id: str,
    token_data: dict = Depends(verify_token),
):
    """Generate blog ideas based on intake and keywords."""
    
    # Verify user owns this research
    if token_data["uid"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    try:
        # Fetch intake data
        intake_ref = db.collection("intakes").document(user_id).collection(research_id).document("intake")
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
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/meta-tags/{user_id}/{research_id}")
async def create_meta_tags(
    user_id: str,
    research_id: str,
    token_data: dict = Depends(verify_token),
):
    """Generate meta tags based on intake and keywords."""
    
    # Verify user owns this research
    if token_data["uid"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    try:
        # Fetch intake data
        intake_ref = db.collection("intakes").document(user_id).collection(research_id).document("intake")
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
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/blog-ideas/{user_id}/{research_id}")
async def get_blog_ideas(
    user_id: str,
    research_id: str,
    token_data: dict = Depends(verify_token),
):
    """Retrieve generated blog ideas."""
    
    if token_data["uid"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    try:
        doc_ref = db.collection("intakes").document(user_id).collection(research_id).document("blog_ideas")
        doc = doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Blog ideas not found")
        
        return {
            "status": "success",
            "data": doc.to_dict(),
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/meta-tags/{user_id}/{research_id}")
async def get_meta_tags(
    user_id: str,
    research_id: str,
    token_data: dict = Depends(verify_token),
):
    """Retrieve generated meta tags."""
    
    if token_data["uid"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    try:
        doc_ref = db.collection("intakes").document(user_id).collection(research_id).document("meta_tags")
        doc = doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Meta tags not found")
        
        return {
            "status": "success",
            "data": doc.to_dict(),
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
