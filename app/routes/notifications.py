import logging
from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.utils.auth import get_current_user, admin_required
from firebase_admin import firestore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["notifications"])
db = firestore.client()


class SelfNotification(BaseModel):
    title: str
    message: str
    link: str = None

@router.get("")
async def list_notifications(user: dict = Depends(get_current_user)):
    """List all notifications for the current user"""
    try:
        notifications_ref = db.collection("notifications")
        # Query without order_by to avoid composite index requirement
        query = notifications_ref.where("userId", "==", user["uid"]).limit(100)
        docs = query.stream()
        
        items = []
        for doc in docs:
            data = doc.to_dict()
            created_at = data.get("createdAt")
            created_at_iso = created_at.isoformat() if hasattr(created_at, "isoformat") else (created_at or "")
            items.append({
                "id": doc.id,
                "title": data.get("title", ""),
                "message": data.get("message", ""),
                "link": data.get("link"),
                "read": data.get("read", False),
                "createdAt": created_at_iso,
            })
        
        # Sort by createdAt descending (newest first) on client side
        items.sort(key=lambda x: x.get("createdAt", ""), reverse=True)
        
        return {"items": items}
    except Exception as e:
        logger.error(f"Failed to fetch notifications: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch notifications. Please try again later.")

@router.post("/{notification_id}/read")
async def mark_notification_read(notification_id: str, user: dict = Depends(get_current_user)):
    """Mark a specific notification as read"""
    try:
        doc_ref = db.collection("notifications").document(notification_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Notification not found")
        
        data = doc.to_dict()
        if data.get("userId") != user["uid"]:
            raise HTTPException(status_code=403, detail="Not authorized")
        
        doc_ref.update({"read": True})
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to mark notification as read: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to mark as read. Please try again later.")

@router.delete("/{notification_id}")
async def delete_notification(notification_id: str, user: dict = Depends(get_current_user)):
    """Delete a specific notification owned by the current user"""
    try:
        doc_ref = db.collection("notifications").document(notification_id)
        doc = doc_ref.get()

        if not doc.exists:
            raise HTTPException(status_code=404, detail="Notification not found")

        data = doc.to_dict()
        if data.get("userId") != user["uid"]:
            raise HTTPException(status_code=403, detail="Not authorized")

        doc_ref.delete()
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete notification: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete notification. Please try again later.")

@router.post("/read-all")
async def mark_all_read(user: dict = Depends(get_current_user)):
    """Mark all notifications as read for the current user"""
    try:
        notifications_ref = db.collection("notifications")
        query = notifications_ref.where("userId", "==", user["uid"]).where("read", "==", False)
        docs = query.stream()
        
        batch = db.batch()
        count = 0
        for doc in docs:
            batch.update(doc.reference, {"read": True})
            count += 1
        
        if count > 0:
            batch.commit()
        
        return {"success": True, "updated": count}
    except Exception as e:
        logger.error(f"Failed to mark all as read: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to mark all as read. Please try again later.")


@router.post("/self")
async def create_self_notification(payload: SelfNotification, user: dict = Depends(get_current_user)):
    """Allow an authenticated user to create their own notification (e.g., background jobs finishing)."""
    try:
        notifications_ref = db.collection("notifications")
        timestamp = datetime.utcnow().isoformat() + "Z"

        doc_ref = notifications_ref.document()
        doc_ref.set({
            "userId": user["uid"],
            "title": payload.title,
            "message": payload.message,
            "link": payload.link,
            "read": False,
            "createdAt": timestamp,
        })

        return {
            "success": True,
            "id": doc_ref.id,
            "createdAt": timestamp,
        }
    except Exception as e:
        logger.error(f"Failed to create notification: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create notification. Please try again later.")

@router.post("/admin/send")
async def admin_send_notification(
    user: dict = Depends(admin_required),
    title: str = Body(...),
    message: str = Body(...),
    segment: Optional[str] = Body(None),
    userEmails: Optional[List[str]] = Body(None)
):
    """Admin endpoint to send notifications to users
    
    Segments:
    - 'all': Send to all users
    - 'free': Send to free plan users
    - 'paid': Send to paid plan users
    - 'admin': Send to admin users
    - None with userEmails: Send to specific users by email
    """
    try:
        users_ref = db.collection("users")
        target_users = []
        
        if segment == "all":
            docs = users_ref.stream()
            target_users = [{"uid": doc.id, "email": doc.to_dict().get("email")} for doc in docs]
        elif segment == "free":
            query = users_ref.where("plan", "==", "free")
            docs = query.stream()
            target_users = [{"uid": doc.id, "email": doc.to_dict().get("email")} for doc in docs]
        elif segment == "paid":
            query = users_ref.where("plan", "==", "paid")
            docs = query.stream()
            target_users = [{"uid": doc.id, "email": doc.to_dict().get("email")} for doc in docs]
        elif segment == "admin":
            query = users_ref.where("role", "==", "admin")
            docs = query.stream()
            target_users = [{"uid": doc.id, "email": doc.to_dict().get("email")} for doc in docs]
        elif userEmails:
            # Send to specific users by email
            for email in userEmails:
                query = users_ref.where("email", "==", email).limit(1)
                docs = list(query.stream())
                if docs:
                    target_users.append({"uid": docs[0].id, "email": email})
        else:
            raise HTTPException(status_code=400, detail="Must specify segment or userEmails")
        
        # Remove duplicates
        seen = set()
        unique_users = []
        for u in target_users:
            if u["uid"] not in seen:
                seen.add(u["uid"])
                unique_users.append(u)
        
        # Create notifications
        notifications_ref = db.collection("notifications")
        batch = db.batch()
        timestamp = datetime.utcnow().isoformat() + "Z"
        
        for u in unique_users:
            doc_ref = notifications_ref.document()
            batch.set(doc_ref, {
                "userId": u["uid"],
                "title": title,
                "message": message,
                "read": False,
                "createdAt": timestamp
            })
        
        if unique_users:
            batch.commit()
        
        return {
            "success": True,
            "sent": len(unique_users),
            "recipients": [u["email"] for u in unique_users]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to send notifications: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to send notifications. Please try again later.")
