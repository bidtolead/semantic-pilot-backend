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
    NOTE: When sending to specific users, this bypasses preference checks 
    (assumes admin is sending important/transactional emails).
    For bulk marketing emails, use /send-to-all with emailType="marketing".
    
    Body:
    {
        "to": "user@example.com" OR ["user1@example.com", "user2@example.com"],
        "subject": "Your subject",
        "message": "HTML or plain text message",
        "respectPreferences": false  // Optional: set to true to check email preferences
    }
    """
    _verify_admin(authorization)
    
    to = body.get("to")
    subject = body.get("subject", "").strip()
    message = body.get("message", "").strip()
    respect_preferences = body.get("respectPreferences", False)
    
    if not to:
        raise HTTPException(status_code=400, detail="Recipient email(s) required")
    if not subject:
        raise HTTPException(status_code=400, detail="Subject required")
    if not message:
        raise HTTPException(status_code=400, detail="Message required")
    
    # Wrap plain text in basic HTML if not already HTML
    html_content = message if "<html" in message.lower() or "<p>" in message.lower() else f"<p>{message}</p>"
    
    try:
        # If respecting preferences, filter recipients
        if respect_preferences:
            filtered_to = []
            skipped = 0
            
            recipients = [to] if isinstance(to, str) else to
            
            for email in recipients:
                # Look up user by email
                user_query = db.collection("users").where("email", "==", email).limit(1).stream()
                user_docs = list(user_query)
                
                if user_docs:
                    user_data = user_docs[0].to_dict() or {}
                    # Check if user has notifications enabled (default True)
                    if user_data.get("emailNotifications", True):
                        filtered_to.append(email)
                    else:
                        skipped += 1
                else:
                    # User not found in DB, send anyway (might be new user)
                    filtered_to.append(email)
            
            if not filtered_to:
                return {
                    "status": "skipped",
                    "message": "All recipients have disabled email notifications",
                    "skipped": skipped
                }
            
            to = filtered_to[0] if len(filtered_to) == 1 else filtered_to
        
        # Single recipient
        if isinstance(to, str):
            result = send_email(to, subject, html_content)
            return {"status": "sent", "recipients": 1, "result": result}
        
        # Multiple recipients
        elif isinstance(to, list):
            result = send_bulk_email(to, subject, html_content)
            response = {
                "status": "completed",
                "sent": len(result["sent"]),
                "failed": len(result["failed"]),
                "details": result
            }
            if respect_preferences and 'skipped' in locals():
                response["skipped_due_to_preferences"] = skipped
            return response
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
    Respects user email preferences (emailNotifications for system emails, marketingEmails for marketing).
    
    Body:
    {
        "subject": "Your subject",
        "message": "HTML or plain text message",
        "emailType": "notification" or "marketing",  // Required: determines which preference to check
        "filter": {
            "role": "user",  // Optional: filter by role
            "plan": "free"   // Optional: filter by plan
        }
    }
    """
    _verify_admin(authorization)
    
    subject = body.get("subject", "").strip()
    message = body.get("message", "").strip()
    email_type = body.get("emailType", "notification")  # "notification" or "marketing"
    filters = body.get("filter", {})
    
    if not subject:
        raise HTTPException(status_code=400, detail="Subject required")
    if not message:
        raise HTTPException(status_code=400, detail="Message required")
    if email_type not in ["notification", "marketing"]:
        raise HTTPException(status_code=400, detail="emailType must be 'notification' or 'marketing'")
    
    # Fetch users from Firestore
    qry = db.collection("users")
    
    # Apply filters if provided
    if filters.get("role"):
        qry = qry.where("role", "==", filters["role"])
    if filters.get("plan"):
        qry = qry.where("plan", "==", filters["plan"])
    
    users = qry.stream()
    emails = []
    skipped_count = 0
    
    for user_doc in users:
        user_data = user_doc.to_dict() or {}
        email = user_data.get("email")
        
        if not email:
            continue
        
        # Check email preferences based on type
        if email_type == "notification":
            # For notification emails, check emailNotifications (default: True)
            if user_data.get("emailNotifications", True) == False:
                skipped_count += 1
                continue
        elif email_type == "marketing":
            # For marketing emails, check marketingEmails (default: True, users can opt-out)
            if user_data.get("marketingEmails", True) == False:
                skipped_count += 1
                continue
        
        emails.append(email)
    
    if not emails:
        return {
            "status": "no_recipients",
            "message": "No users match the criteria or all users have opted out",
            "skipped": skipped_count
        }
    
    # Wrap plain text in basic HTML if not already HTML
    html_content = message if "<html" in message.lower() or "<p>" in message.lower() else f"<p>{message}</p>"
    
    try:
        result = send_bulk_email(emails, subject, html_content)
        return {
            "status": "completed",
            "email_type": email_type,
            "total_matching_users": len(emails) + skipped_count,
            "skipped_due_to_preferences": skipped_count,
            "sent_to": len(emails),
            "sent": len(result["sent"]),
            "failed": len(result["failed"]),
            "details": result
        }
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send emails: {str(e)}")
