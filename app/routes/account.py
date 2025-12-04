from fastapi import APIRouter, HTTPException, Header
from app.services.firestore import db
import firebase_admin
from firebase_admin import auth as firebase_auth
from datetime import datetime

router = APIRouter(prefix="/auth", tags=["account"])


# ----------------------------------------
# EXPORT USER DATA (GDPR Compliance)
# ----------------------------------------
@router.get("/export-data")
def export_user_data(authorization: str | None = Header(default=None)):
    """
    Export all user data including profile and research history.
    Returns JSON with all user information for GDPR compliance.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization.split(" ")[1]

    try:
        decoded = firebase_auth.verify_id_token(token)
        uid = decoded["uid"]

        # Get user profile
        user_ref = db.collection("users").document(uid)
        user_snapshot = user_ref.get()
        
        if not user_snapshot.exists:
            raise HTTPException(status_code=404, detail="User not found")

        user_data = user_snapshot.to_dict() or {}
        
        # Get all research history
        research_docs = db.collection("seo_research").where("uid", "==", uid).stream()
        research_history = []
        for doc in research_docs:
            research_data = doc.to_dict() or {}
            research_data["id"] = doc.id
            research_history.append(research_data)

        # Get reviews if any
        review_docs = db.collection("reviews").where("uid", "==", uid).stream()
        reviews = []
        for doc in review_docs:
            review_data = doc.to_dict() or {}
            review_data["id"] = doc.id
            reviews.append(review_data)

        export_data = {
            "exportDate": datetime.utcnow().isoformat(),
            "userProfile": user_data,
            "researchHistory": research_history,
            "reviews": reviews,
            "totalResearches": len(research_history),
            "totalReviews": len(reviews),
        }

        return export_data

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


# ----------------------------------------
# DELETE USER ACCOUNT (GDPR Compliance)
# ----------------------------------------
@router.delete("/delete-account")
def delete_user_account(authorization: str | None = Header(default=None)):
    """
    Permanently delete user account and all associated data.
    This action is irreversible and complies with GDPR right to erasure.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization.split(" ")[1]

    try:
        decoded = firebase_auth.verify_id_token(token)
        uid = decoded["uid"]
        email = decoded.get("email", "unknown")

        # Delete all user's research documents
        research_docs = db.collection("seo_research").where("uid", "==", uid).stream()
        for doc in research_docs:
            doc.reference.delete()

        # Delete all user's reviews
        review_docs = db.collection("reviews").where("uid", "==", uid).stream()
        for doc in review_docs:
            doc.reference.delete()

        # Delete user profile from Firestore
        user_ref = db.collection("users").document(uid)
        user_ref.delete()

        # Delete user from Firebase Auth
        firebase_auth.delete_user(uid)

        return {
            "status": "deleted",
            "message": f"Account {email} and all associated data have been permanently deleted",
            "deletedAt": datetime.utcnow().isoformat()
        }

    except firebase_admin.auth.UserNotFoundError:
        raise HTTPException(status_code=404, detail="User not found in authentication system")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Account deletion failed: {str(e)}")
