from fastapi import APIRouter, HTTPException, Depends, Query, Request, BackgroundTasks
from app.utils.auth import verify_token
from app.services.firestore import db
from app.services.content_generator import (
    generate_blog_ideas, 
    generate_meta_tags, 
    generate_page_content,
    generate_google_ads_ad_copy,
    generate_google_ads_landing_page,
    generate_google_ads_negative_keywords,
    generate_google_ads_structure,
)
from google.cloud import firestore as gcfirestore
from slowapi import Limiter
from slowapi.util import get_remote_address
import asyncio
import uuid
from datetime import datetime
import threading
import traceback

router = APIRouter(prefix="/content", tags=["content"])
limiter = Limiter(key_func=get_remote_address)

# Per-user rate limit key function
def get_user_id(request: Request) -> str:
    """Extract user_id from path for per-user rate limiting."""
    path_parts = request.url.path.split("/")
    # /content/ad-copy/{user_id}/{research_id} -> user_id is at index 3
    if len(path_parts) > 3:
        return path_parts[3]
    return "anonymous"


def generate_blog_draft_background(
    user_id: str,
    research_id: str,
    blog_index: int,
    primary_keywords: list,
    secondary_keywords: list,
    long_tail_keywords: list,
    user_intake_form: dict,
    research_data: dict,
    blog_idea_title: str,
    target_keyword: str,
    search_intent: str,
):
    """Background task to generate blog draft and save to Firestore"""
    try:
        print(f"\n[BackgroundBlog] 🚀 Starting generation")
        print(f"  User: {user_id}")
        print(f"  Research: {research_id}")
        print(f"  Index: {blog_index}")
        print(f"  Keyword: {target_keyword}")
        
        # Generate content
        print(f"[BackgroundBlog] Calling generate_page_content...")
        result = generate_page_content(
            primary_keywords=primary_keywords,
            secondary_keywords=secondary_keywords,
            long_tail_keywords=long_tail_keywords,
            user_intake_form=user_intake_form,
            research_data=research_data,
            user_id=user_id,
        )
        
        print(f"[BackgroundBlog] ✅ Content generated successfully")
        print(f"  Result type: {type(result)}")
        print(f"  Result keys: {result.keys() if isinstance(result, dict) else 'N/A'}")
        
        # Save to Firestore
        draft_data = {
            **result,
            "blogIdeaIndex": blog_index,
            "blogIdeaTitle": blog_idea_title,
            "targetKeyword": target_keyword,
            "searchIntent": search_intent,
            "createdAt": datetime.utcnow().isoformat(),
        }
        
        blog_draft_ref = (
            db.collection("intakes")
            .document(user_id)
            .collection(research_id)
            .document(f"blog_draft_{blog_index}")
        )
        blog_draft_ref.set(draft_data)
        
        print(f"[BackgroundBlog] ✅ Saved to Firestore at intakes/{user_id}/{research_id}/blog_draft_{blog_index}")
        
        # Create notification
        notification_data = {
            "title": "Blog Draft Complete",
            "message": f'"{blog_idea_title}" is ready to view.',
            "link": f"/research/results?researchId={research_id}",
            "timestamp": gcfirestore.SERVER_TIMESTAMP,
            "read": False,
        }
        
        db.collection("users").document(user_id).collection("notifications").add(notification_data)
        print(f"[BackgroundBlog] ✅ Notification created")
        print(f"[BackgroundBlog] 🎉 Blog generation complete!\n")
        
    except Exception as e:
        print(f"\n[BackgroundBlog] ❌ ERROR during generation:")
        print(f"  Error: {str(e)}")
        print(f"  Type: {type(e).__name__}")
        print(f"  Traceback:\n{traceback.format_exc()}\n")
        
        # Save error notification
        try:
            error_notification = {
                "title": "Blog Draft Failed",
                "message": f"Failed to generate blog: {str(e)[:200]}",
                "link": f"/research/results?researchId={research_id}",
                "timestamp": gcfirestore.SERVER_TIMESTAMP,
                "read": False,
            }
            db.collection("users").document(user_id).collection("notifications").add(error_notification)
            print(f"[BackgroundBlog] Error notification created")
        except Exception as notify_err:
            print(f"[BackgroundBlog] Failed to create error notification: {notify_err}")



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
        
        # If exists and has valid data, return existing
        if doc.exists:
            data = doc.to_dict()
            # Check if data actually has content (not just empty arrays)
            has_ideas = isinstance(data.get("ideas"), list) and len(data.get("ideas", [])) > 0
            
            if has_ideas:
                print(f"[BlogIdeas] Returning existing blog ideas for {research_id}")
                return {
                    "status": "success",
                    "data": data,
                }
            else:
                print(f"[BlogIdeas] Blog ideas exist but are empty, regenerating for {research_id}")
        
        # Only generate if they don't exist or are empty
        print(f"[BlogIdeas] Generating blog ideas for {research_id}")
        
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
    force: bool = Query(default=False, description="Force regeneration even if data exists"),
):
    """Generate or retrieve meta tags based on intake and keywords."""
    
    # Verify user owns this research
    if token_data["uid"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    try:
        # Check if meta tags already exist
        doc_ref = db.collection("intakes").document(user_id).collection(research_id).document("meta_tags")
        doc = doc_ref.get()
        
        # If force=True, always regenerate
        if force:
            print(f"[MetaTags] Force regeneration requested for {research_id}")
        # If exists and has valid data, return existing (don't waste credits)
        elif doc.exists:
            data = doc.to_dict()
            # Check if data actually has content (not just empty arrays)
            has_titles = isinstance(data.get("page_title_variations"), list) and len(data.get("page_title_variations", [])) > 0
            has_descriptions = isinstance(data.get("meta_description_variations"), list) and len(data.get("meta_description_variations", [])) > 0
            
            if has_titles and has_descriptions:
                print(f"[MetaTags] Returning existing meta tags for {research_id}")
                return {
                    "status": "success",
                    "data": data,
                }
            else:
                print(f"[MetaTags] Meta tags exist but are empty, regenerating for {research_id}")
        
        # Only generate if they don't exist or are empty
        print(f"[MetaTags] Generating meta tags for {research_id}")
        
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
        
        print(f"[MetaTags] Generation complete with {len(result.get('page_title_variations', []))} titles and {len(result.get('meta_description_variations', []))} descriptions")
        
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
    # Extract and verify token from Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    
    try:
        from firebase_admin import auth as firebase_auth
        token = auth_header.replace("Bearer ", "")
        user_data = firebase_auth.verify_id_token(token)
    except Exception as e:
        print(f"[Token Verify] Error: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    user_id = user_data.get("uid")
    
    try:
        body = await request.json()
        primary_keywords = body.get("primary_keywords", [])
        secondary_keywords = body.get("secondary_keywords", [])
        long_tail_keywords = body.get("long_tail_keywords", [])
        user_intake_form = body.get("user_intake_form", {})
        research_data = body.get("research_data", {})
        
        # Get user data from Firestore to check role
        user_doc = db.collection("users").document(user_id).get()
        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_firestore_data = user_doc.to_dict() or {}
        user_role = user_firestore_data.get("role", "user")
        
        # Skip credit check for admin and tester users
        should_deduct_credit = False
        if user_role not in ["admin", "tester"]:
            # For regular users, check credits
            credits = user_firestore_data.get("credits") or 0
            if credits < 1:
                raise HTTPException(status_code=402, detail="Insufficient credits. Please purchase more credits.")
            should_deduct_credit = True
        
        # Start content generation immediately (don't wait for credit deduction)
        result = generate_page_content(
            primary_keywords=primary_keywords,
            secondary_keywords=secondary_keywords,
            long_tail_keywords=long_tail_keywords,
            user_intake_form=user_intake_form,
            research_data=research_data,
            user_id=user_id,
        )
        
        # Deduct credit AFTER generation succeeds
        if should_deduct_credit:
            try:
                db.collection("users").document(user_id).update({
                    "credits": gcfirestore.Increment(-1)
                })
            except Exception as e:
                print(f"[Warning] Credit deduction failed but content was generated: {e}")
        
        return {
            "status": "success",
            "data": result,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/page-content-async/")
async def generate_page_content_async(request: Request, background_tasks: BackgroundTasks):
    """Generate page content asynchronously - returns immediately and processes in background"""
    # Extract and verify token from Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    
    try:
        from firebase_admin import auth as firebase_auth
        token = auth_header.replace("Bearer ", "")
        user_data = firebase_auth.verify_id_token(token)
    except Exception as e:
        print(f"[Token Verify] Error: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    user_id = user_data.get("uid")
    
    try:
        body = await request.json()
        primary_keywords = body.get("primary_keywords", [])
        secondary_keywords = body.get("secondary_keywords", [])
        long_tail_keywords = body.get("long_tail_keywords", [])
        user_intake_form = body.get("user_intake_form", {})
        research_data = body.get("research_data", {})
        research_id = body.get("research_id", "")
        blog_index = body.get("blog_index", 0)
        blog_idea_title = body.get("blog_idea_title", "")
        target_keyword = body.get("target_keyword", "")
        search_intent = body.get("search_intent", "")
        
        # Get user data from Firestore to check role and credits
        user_doc = db.collection("users").document(user_id).get()
        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_firestore_data = user_doc.to_dict() or {}
        user_role = user_firestore_data.get("role", "user")
        
        # Check credits before starting background task
        should_deduct_credit = False
        if user_role not in ["admin", "tester"]:
            credits = user_firestore_data.get("credits") or 0
            if credits < 1:
                raise HTTPException(status_code=402, detail="Insufficient credits. Please purchase more credits.")
            should_deduct_credit = True
            
            # Deduct credit immediately to prevent double-spending
            db.collection("users").document(user_id).update({
                "credits": gcfirestore.Increment(-1)
            })
        
        # Start background task using threading (more reliable than FastAPI BackgroundTasks)
        print(f"[AsyncEndpoint] Starting background thread for user {user_id}")
        thread = threading.Thread(
            target=generate_blog_draft_background,
            args=(
                user_id,
                research_id,
                blog_index,
                primary_keywords,
                secondary_keywords,
                long_tail_keywords,
                user_intake_form,
                research_data,
                blog_idea_title,
                target_keyword,
                search_intent,
            ),
            daemon=False,  # Keep thread alive even if main process ends
        )
        thread.start()
        print(f"[AsyncEndpoint] Background thread started successfully")
        
        # Return immediately
        return {
            "status": "processing",
            "message": "Blog draft generation started. You'll receive a notification when complete.",
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[AsyncEndpoint] Error: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/blog-ideas/")
async def generate_blog_ideas_post(request: Request):
    """Generate blog ideas directly from frontend request"""
    # Extract and verify token from Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    
    try:
        from firebase_admin import auth as firebase_auth
        token = auth_header.replace("Bearer ", "")
        user_data = firebase_auth.verify_id_token(token)
    except Exception as e:
        print(f"[Token Verify] Error: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    user_id = user_data.get("uid")
    
    try:
        body = await request.json()
        primary_keywords = body.get("primary_keywords", [])
        user_intake_form = body.get("user_intake_form", {})
        research_data = body.get("research_data", {})
        
        # Get user data from Firestore to check role
        user_doc = db.collection("users").document(user_id).get()
        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_firestore_data = user_doc.to_dict() or {}
        user_role = user_firestore_data.get("role", "user")
        
        # Skip credit check for admin and tester users
        should_deduct_credit = False
        if user_role not in ["admin", "tester"]:
            # For regular users, check credits
            credits = user_firestore_data.get("credits") or 0
            if credits < 1:
                raise HTTPException(status_code=402, detail="Insufficient credits. Please purchase more credits.")
            should_deduct_credit = True
        
        # Start generation immediately (don't wait for credit deduction)
        result = generate_blog_ideas(
            primary_keywords=primary_keywords,
            user_intake_form=user_intake_form,
            research_data=research_data,
            user_id=user_id,
        )
        
        # Deduct credit AFTER generation succeeds
        if should_deduct_credit:
            try:
                db.collection("users").document(user_id).update({
                    "credits": gcfirestore.Increment(-1)
                })
            except Exception as e:
                print(f"[Warning] Credit deduction failed but content was generated: {e}")
        
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
    # Extract and verify token from Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    
    try:
        from firebase_admin import auth as firebase_auth
        token = auth_header.replace("Bearer ", "")
        user_data = firebase_auth.verify_id_token(token)
    except Exception as e:
        print(f"[Token Verify] Error: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    user_id = user_data.get("uid")
    
    try:
        body = await request.json()
        primary_keywords = body.get("primary_keywords", [])
        secondary_keywords = body.get("secondary_keywords", [])
        long_tail_keywords = body.get("long_tail_keywords", [])
        user_intake_form = body.get("user_intake_form", {})
        research_data = body.get("research_data", {})
        
        # Get user data from Firestore to check role
        user_doc = db.collection("users").document(user_id).get()
        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_firestore_data = user_doc.to_dict() or {}
        user_role = user_firestore_data.get("role", "user")
        
        # Skip credit check for admin and tester users
        should_deduct_credit = False
        if user_role not in ["admin", "tester"]:
            # For regular users, check credits
            credits = user_firestore_data.get("credits") or 0
            if credits < 1:
                raise HTTPException(status_code=402, detail="Insufficient credits. Please purchase more credits.")
            should_deduct_credit = True
        
        # Start generation immediately (don't wait for credit deduction)
        result = generate_meta_tags(
            primary_keywords=primary_keywords,
            secondary_keywords=secondary_keywords,
            long_tail_keywords=long_tail_keywords,
            user_intake_form=user_intake_form,
            research_data=research_data,
            user_id=user_id,
        )
        
        # Deduct credit AFTER generation succeeds
        if should_deduct_credit:
            try:
                db.collection("users").document(user_id).update({
                    "credits": gcfirestore.Increment(-1)
                })
            except Exception as e:
                print(f"[Warning] Credit deduction failed but content was generated: {e}")
        
        return {
            "status": "success",
            "data": result,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ad-copy/{user_id}/{research_id}")
@limiter.limit("50/hour", key_func=get_user_id)
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
@limiter.limit("50/hour", key_func=get_user_id)
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
@limiter.limit("50/hour", key_func=get_user_id)
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

@router.get("/structure/{user_id}/{research_id}")
@limiter.limit("50/hour", key_func=get_user_id)
async def handle_structure(
    request: Request,
    user_id: str,
    research_id: str,
    token_data: dict = Depends(verify_token),
    generate: bool = Query(default=True),
):
    """Generate or retrieve Google Ads campaign structure. ADMIN AND TESTER. Rate limited: 50/hour."""
    
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
        doc_ref = db.collection("intakes").document(user_id).collection(research_id).document("structure")
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
        
        result = generate_google_ads_structure(
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
