from fastapi import APIRouter, Header, HTTPException
from firebase_admin import auth as firebase_auth
from app.services.firestore import db
from app.services.email_service import send_email, send_bulk_email
from typing import Optional

router = APIRouter(prefix="/admin/email", tags=["Admin Email"])


def _verify_admin(authorization: str | None):
    """Verify admin authorization and return uid."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization.split(" ")[1]
    try:
        decoded = firebase_auth.verify_id_token(token)
        uid = decoded["uid"]
        user = db.collection("users").document(uid).get().to_dict() or {}
        if user.get("role") not in ["admin", "tester"]:
            raise HTTPException(status_code=403, detail="Admin access required")
        return uid
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


@router.post("/send")
def send_user_email(
    body: dict,
    authorization: str | None = Header(default=None)
):
    """
    Send email to a specific user or multiple users.
    
    Body:
    {
        "to": "user@example.com" OR ["user1@example.com", "user2@example.com"],
        "subject": "Your subject",
        "message": "HTML or plain text message"
    }
    """
    _verify_admin(authorization)
    
    to = body.get("to")
    subject = body.get("subject", "").strip()
    message = body.get("message", "").strip()
    
    if not to:
        raise HTTPException(status_code=400, detail="Recipient email(s) required")
    if not subject:
        raise HTTPException(status_code=400, detail="Subject required")
    if not message:
        raise HTTPException(status_code=400, detail="Message required")
    
    # Wrap plain text in basic HTML if not already HTML
    html_content = message if "<html" in message.lower() or "<p>" in message.lower() else f"<p>{message}</p>"
    
    try:
        # Single recipient
        if isinstance(to, str):
            result = send_email(to, subject, html_content)
            return {"status": "sent", "recipients": 1, "result": result}
        
        # Multiple recipients
        elif isinstance(to, list):
            result = send_bulk_email(to, subject, html_content)
            return {
                "status": "completed",
                "sent": len(result["sent"]),
                "failed": len(result["failed"]),
                "details": result
            }
        else:
            raise HTTPException(status_code=400, detail="Invalid recipient format")
    
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")


@router.post("/send-to-all")
def send_to_all_users(
    body: dict,
    authorization: str | None = Header(default=None)
):
    """
    Send email to all users in the system.
    
    Body:
    {
        "subject": "Your subject",
        "message": "HTML or plain text message",
        "filter": {
            "role": "user",  // Optional: filter by role
            "plan": "free"   // Optional: filter by plan
        }
    }
    """
    _verify_admin(authorization)
    
    subject = body.get("subject", "").strip()
    message = body.get("message", "").strip()
    filters = body.get("filter", {})
    
    if not subject:
        raise HTTPException(status_code=400, detail="Subject required")
    if not message:
        raise HTTPException(status_code=400, detail="Message required")
    
    # Fetch users from Firestore
    qry = db.collection("users")
    
    # Apply filters if provided
    if filters.get("role"):
        qry = qry.where("role", "==", filters["role"])
    if filters.get("plan"):
        qry = qry.where("plan", "==", filters["plan"])
    
    users = qry.stream()
    emails = []
    
    for user_doc in users:
        user_data = user_doc.to_dict() or {}
        email = user_data.get("email")
        if email:
            emails.append(email)
    
    if not emails:
        return {"status": "no_recipients", "message": "No users match the criteria"}
    
    # Wrap plain text in basic HTML if not already HTML
    html_content = message if "<html" in message.lower() or "<p>" in message.lower() else f"<p>{message}</p>"
    
    try:
        result = send_bulk_email(emails, subject, html_content)
        return {
            "status": "completed",
            "total_recipients": len(emails),
            "sent": len(result["sent"]),
            "failed": len(result["failed"]),
            "details": result
        }
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send emails: {str(e)}")
