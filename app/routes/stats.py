from fastapi import APIRouter
from app.services.firestore import db
from google.cloud import firestore as gcfirestore

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
                "searches_ran": stats_data.get("searches_ran", 2500),
                "meta_tags_generated": stats_data.get("meta_tags_generated", 15000),
                "blog_ideas_created": stats_data.get("blog_ideas_created", 8500),
                "keywords_analyzed": stats_data.get("keywords_analyzed", 12000),
            }
        else:
            # Initialize the document with default values if it doesn't exist
            initial_stats = {
                "searches_ran": 2500,
                "meta_tags_generated": 15000,
                "blog_ideas_created": 8500,
                "keywords_analyzed": 12000,
            }
            db.collection("system").document("stats").set(initial_stats)
            return initial_stats
            
    except Exception as e:
        print(f"Error fetching stats: {e}")
        # Return fallback numbers if there's an error
        return {
            "searches_ran": 2500,
            "meta_tags_generated": 15000,
            "blog_ideas_created": 8500,
            "keywords_analyzed": 12000,
        }
