import logging
from fastapi import APIRouter, HTTPException, Header
from app.services.firestore import db
import firebase_admin
from firebase_admin import auth as firebase_auth
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/support", tags=["support"])


# ----------------------------------------
# REPORT AN ISSUE
# ----------------------------------------
@router.post("/report-issue")
def report_issue(body: dict, authorization: str | None = Header(default=None)):
    """
    Allow users to report bugs, issues, or feature requests.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization.split(" ")[1]

    try:
        decoded = firebase_auth.verify_id_token(token)
        uid = decoded["uid"]
        email = decoded.get("email", "unknown")

        title = body.get("title", "").strip()
        description = body.get("description", "").strip()

        if not title or not description:
            raise HTTPException(status_code=400, detail="Title and description are required")

        if len(title) > 200:
            raise HTTPException(status_code=400, detail="Title must be 200 characters or less")

        if len(description) > 5000:
            raise HTTPException(status_code=400, detail="Description must be 5000 characters or less")

        # Create issue report in Firestore
        issue_id = str(uuid.uuid4())
        
        issues_ref = db.collection("support_issues").document(issue_id)
        issues_ref.set({
            "issueId": issue_id,
            "userId": uid,
            "userEmail": email,
            "title": title,
            "description": description,
            "status": "open",
            "createdAt": datetime.utcnow().isoformat(),
            "updatedAt": datetime.utcnow().isoformat()
        })

        # Also save a reference under the user's issues subcollection for easy retrieval
        user_issues_ref = db.collection("users").document(uid).collection("issues").document(issue_id)
        user_issues_ref.set({
            "issueId": issue_id,
            "title": title,
            "status": "open",
            "createdAt": datetime.utcnow().isoformat()
        })

        return {
            "status": "submitted",
            "issueId": issue_id,
            "message": "Issue report submitted successfully. Our team will review it shortly."
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to submit issue report: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to submit issue report. Please try again later.")


# ----------------------------------------
# GET USER'S ISSUE REPORTS
# ----------------------------------------
@router.get("/my-issues")
def get_user_issues(authorization: str | None = Header(default=None)):
    """
    Get all issue reports submitted by the current user.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization.split(" ")[1]

    try:
        decoded = firebase_auth.verify_id_token(token)
        uid = decoded["uid"]

        # Get user's issues from their subcollection
        user_issues = db.collection("users").document(uid).collection("issues").stream()
        
        issues = []
        for doc in user_issues:
            issue_data = doc.to_dict()
            issue_data["issueId"] = doc.id
            issues.append(issue_data)

        # Sort by creation date (newest first)
        issues.sort(key=lambda x: x.get("createdAt", ""), reverse=True)

        return {
            "issues": issues,
            "total": len(issues)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve issues: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve issues. Please try again later.")
