from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import StreamingResponse
from app.services.firestore import db
import firebase_admin
from firebase_admin import auth as firebase_auth
from datetime import datetime
import csv
import io

router = APIRouter(prefix="/auth", tags=["account"])


# ----------------------------------------
# EXPORT RESEARCH REPORTS AS CSV
# ----------------------------------------
@router.get("/export-data")
def export_research_data(authorization: str | None = Header(default=None)):
    """
    Export all user research reports as CSV file.
    Returns CSV with research history for easy analysis in Excel/Google Sheets.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization.split(" ")[1]

    try:
        decoded = firebase_auth.verify_id_token(token)
        uid = decoded["uid"]

        # Get all research history
        research_docs = db.collection("seo_research").where("uid", "==", uid).stream()
        research_list = []
        for doc in research_docs:
            research_data = doc.to_dict() or {}
            research_data["research_id"] = doc.id
            research_list.append(research_data)

        if not research_list:
            raise HTTPException(status_code=404, detail="No research data found to export")

        # Create CSV in memory
        output = io.StringIO()
        
        # Collect all keyword results across all research
        rows = []
        
        for research in research_list:
            business_name = research.get('businessName', '')
            created_at = research.get('createdAt', '')
            location = research.get('location', '')
            
            if 'keywordData' in research and research['keywordData']:
                kw_data = research['keywordData']
                
                # Export primary keywords
                if 'primary' in kw_data and isinstance(kw_data['primary'], list):
                    for kw in kw_data['primary']:
                        rows.append({
                            'business_name': business_name,
                            'research_date': created_at,
                            'location': location,
                            'keyword_type': 'Primary',
                            'keyword': kw.get('keyword', ''),
                            'search_volume': kw.get('search_volume', 0),
                            'competition': kw.get('competition', ''),
                            'cpc': kw.get('cpc', 0),
                        })
                
                # Export secondary keywords
                if 'secondary' in kw_data and isinstance(kw_data['secondary'], list):
                    for kw in kw_data['secondary']:
                        rows.append({
                            'business_name': business_name,
                            'research_date': created_at,
                            'location': location,
                            'keyword_type': 'Secondary',
                            'keyword': kw.get('keyword', ''),
                            'search_volume': kw.get('search_volume', 0),
                            'competition': kw.get('competition', ''),
                            'cpc': kw.get('cpc', 0),
                        })
        
        if not rows:
            raise HTTPException(status_code=404, detail="No keyword results found to export")
        
        # Define CSV columns - only keyword results
        fieldnames = [
            'business_name',
            'research_date',
            'location',
            'keyword_type',
            'keyword',
            'search_volume',
            'competition',
            'cpc',
        ]
        
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        
        # Prepare response
        output.seek(0)
        csv_content = output.getvalue()
        
        return StreamingResponse(
            iter([csv_content]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=semantic-pilot-research-{datetime.utcnow().strftime('%Y%m%d')}.csv"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


# ----------------------------------------
# UPDATE EMAIL PREFERENCES
# ----------------------------------------
@router.post("/update-preferences")
def update_email_preferences(body: dict, authorization: str | None = Header(default=None)):
    """
    Update user email notification preferences.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization.split(" ")[1]

    try:
        decoded = firebase_auth.verify_id_token(token)
        uid = decoded["uid"]

        email_notifications = body.get("emailNotifications", True)
        marketing_emails = body.get("marketingEmails", False)

        user_ref = db.collection("users").document(uid)
        user_ref.update({
            "emailNotifications": email_notifications,
            "marketingEmails": marketing_emails,
            "updatedAt": datetime.utcnow().isoformat()
        })

        return {
            "status": "updated",
            "emailNotifications": email_notifications,
            "marketingEmails": marketing_emails
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update preferences: {str(e)}")


# ----------------------------------------
# CHANGE EMAIL ADDRESS
# ----------------------------------------
@router.post("/change-email")
def change_email_address(body: dict, authorization: str | None = Header(default=None)):
    """
    Change user's email address in both Firebase Auth and Firestore.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization.split(" ")[1]

    try:
        decoded = firebase_auth.verify_id_token(token)
        uid = decoded["uid"]

        new_email = body.get("newEmail", "").strip()
        if not new_email:
            raise HTTPException(status_code=400, detail="New email is required")

        # Basic email validation
        if "@" not in new_email or "." not in new_email.split("@")[1]:
            raise HTTPException(status_code=400, detail="Invalid email format")

        # Update Firebase Auth
        firebase_auth.update_user(uid, email=new_email)

        # Update Firestore
        user_ref = db.collection("users").document(uid)
        user_ref.update({
            "email": new_email,
            "updatedAt": datetime.utcnow().isoformat()
        })

        return {
            "status": "updated",
            "email": new_email,
            "message": "Email address updated successfully"
        }

    except firebase_admin.exceptions.FirebaseError as e:
        # Handle Firebase-specific errors (e.g., email already in use)
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to change email: {str(e)}")


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
