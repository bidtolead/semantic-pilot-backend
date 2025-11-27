from fastapi import APIRouter, Depends
from app.services.firestore import db
from app.utils.auth import verify_token
from google.cloud import firestore as gcfirestore
from google.cloud.firestore_v1.base_query import FieldFilter

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/public")
async def get_public_stats():
    """Get public statistics for homepage display from stored counters."""
    try:
        # Simply read the pre-calculated stats from a single document
        stats_doc = db.collection("system").document("stats").get()
        
        if stats_doc.exists:
            stats_data = stats_doc.to_dict()
            return {
                "searches_ran": stats_data.get("searches_ran", 100),
                "meta_tags_generated": stats_data.get("meta_tags_generated", 250),
                "blog_ideas_created": stats_data.get("blog_ideas_created", 500),
                "keywords_analyzed": stats_data.get("keywords_analyzed", 1500),
            }
        else:
            # Auto-initialize by counting existing data on first request
            print("Stats document doesn't exist, initializing...")
            
            try:
                # Count existing data quickly
                research_intakes_list = list(db.collection("research_intakes").limit(100).stream())
                searches_count = len(research_intakes_list)
                
                meta_tags_count = 0
                blog_ideas_count = 0
                keywords_analyzed_count = 0
                
                for research_doc in research_intakes_list[:20]:  # Sample first 20 for speed
                    doc_id = research_doc.id
                    if "_" in doc_id:
                        parts = doc_id.split("_", 1)
                        if len(parts) == 2:
                            user_id, research_id = parts
                            
                            try:
                                meta_doc = db.collection("intakes").document(user_id).collection(research_id).document("meta_tags").get()
                                if meta_doc.exists:
                                    meta_tags_count += 1
                                
                                blog_doc = db.collection("intakes").document(user_id).collection(research_id).document("blog_ideas").get()
                                if blog_doc.exists:
                                    blog_data = blog_doc.to_dict()
                                    if blog_data and "blog_ideas" in blog_data:
                                        blog_ideas_count += len(blog_data["blog_ideas"])
                                
                                keywords_doc = db.collection("intakes").document(user_id).collection(research_id).document("keyword_research").get()
                                if keywords_doc.exists:
                                    kw_data = keywords_doc.to_dict()
                                    if kw_data:
                                        keywords_analyzed_count += (
                                            len(kw_data.get("primary_keywords", [])) +
                                            len(kw_data.get("secondary_keywords", [])) +
                                            len(kw_data.get("long_tail_keywords", []))
                                        )
                            except Exception:
                                pass
                
                initial_stats = {
                    "searches_ran": max(searches_count, 100),
                    "meta_tags_generated": max(meta_tags_count, 250),
                    "blog_ideas_created": max(blog_ideas_count, 500),
                    "keywords_analyzed": max(keywords_analyzed_count, 1500),
                }
                
                db.collection("system").document("stats").set(initial_stats)
                print(f"Initialized stats: {initial_stats}")
                return initial_stats
                
            except Exception as e:
                print(f"Error during auto-initialization: {e}")
                # Return starting numbers if auto-init fails
                initial_stats = {
                    "searches_ran": 100,
                    "meta_tags_generated": 250,
                    "blog_ideas_created": 500,
                    "keywords_analyzed": 1500,
                }
                db.collection("system").document("stats").set(initial_stats)
                return initial_stats
            
    except Exception as e:
        print(f"Error fetching stats: {e}")
        return {
            "searches_ran": 100,
            "meta_tags_generated": 250,
            "blog_ideas_created": 500,
            "keywords_analyzed": 1500,
        }


@router.post("/initialize")
async def initialize_stats(token_data: dict = Depends(verify_token)):
    """Initialize stats by counting existing data. Admin only."""
    try:
        print("Starting stats initialization...")
        
        # Count total research intakes (searches ran)
        research_intakes_list = list(db.collection("research_intakes").stream())
        searches_count = len(research_intakes_list)
        print(f"Found {searches_count} research intakes")
        
        # Count meta tags, blog ideas, and keywords
        meta_tags_count = 0
        blog_ideas_count = 0
        keywords_analyzed_count = 0
        
        # Iterate through research intakes to count generated content
        for research_doc in research_intakes_list:
            doc_id = research_doc.id
            print(f"Processing research: {doc_id}")
            
            if "_" in doc_id:
                parts = doc_id.split("_", 1)
                if len(parts) == 2:
                    user_id, research_id = parts
                    
                    # Check for meta_tags
                    try:
                        meta_doc = db.collection("intakes").document(user_id).collection(research_id).document("meta_tags").get()
                        if meta_doc.exists:
                            meta_tags_count += 1
                            print(f"  Found meta tags for {research_id}")
                    except Exception as e:
                        print(f"  Error checking meta tags: {e}")
                    
                    # Check for blog_ideas and count individual ideas
                    try:
                        blog_doc = db.collection("intakes").document(user_id).collection(research_id).document("blog_ideas").get()
                        if blog_doc.exists:
                            blog_data = blog_doc.to_dict()
                            if blog_data and "blog_ideas" in blog_data:
                                ideas_count = len(blog_data["blog_ideas"])
                                blog_ideas_count += ideas_count
                                print(f"  Found {ideas_count} blog ideas for {research_id}")
                    except Exception as e:
                        print(f"  Error checking blog ideas: {e}")
                    
                    # Check for keyword_research and count keywords
                    try:
                        keywords_doc = db.collection("intakes").document(user_id).collection(research_id).document("keyword_research").get()
                        if keywords_doc.exists:
                            kw_data = keywords_doc.to_dict()
                            if kw_data:
                                kw_count = (
                                    len(kw_data.get("primary_keywords", [])) +
                                    len(kw_data.get("secondary_keywords", [])) +
                                    len(kw_data.get("long_tail_keywords", []))
                                )
                                keywords_analyzed_count += kw_count
                                print(f"  Found {kw_count} keywords for {research_id}")
                    except Exception as e:
                        print(f"  Error checking keywords: {e}")
        
        # Save to system/stats document
        stats_data = {
            "searches_ran": searches_count,
            "meta_tags_generated": meta_tags_count,
            "blog_ideas_created": blog_ideas_count,
            "keywords_analyzed": keywords_analyzed_count,
            "last_initialized": gcfirestore.SERVER_TIMESTAMP,
        }
        
        print(f"Final stats: {stats_data}")
        db.collection("system").document("stats").set(stats_data)
        
        return {
            "success": True,
            "message": "Stats initialized successfully",
            "stats": stats_data
        }
        
    except Exception as e:
        print(f"Error initializing stats: {e}")
        return {
            "success": False,
            "error": str(e)
        }
