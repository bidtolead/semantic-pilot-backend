from fastapi import APIRouter, Depends, HTTPException, Body
from typing import Optional, List
from datetime import datetime
from app.utils.auth import get_current_user, admin_required
from firebase_admin import firestore

router = APIRouter(prefix="/notifications", tags=["notifications"])
db = firestore.client()

@router.get("")
async def list_notifications(user: dict = Depends(get_current_user)):
    """List all notifications for the current user"""
    try:
        notifications_ref = db.collection("notifications")
        query = notifications_ref.where("userId", "==", user["uid"])
        docs = query.stream()
        
        items = []
        for doc in docs:
            data = doc.to_dict()
            items.append({
                "id": doc.id,
                "title": data.get("title", ""),
                "message": data.get("message", ""),
                "read": data.get("read", False),
                "createdAt": data.get("createdAt", "")
            })
        
        # Sort by createdAt descending (newest first)
        items.sort(key=lambda x: x.get("createdAt", ""), reverse=True)
        
        return {"items": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch notifications: {str(e)}")

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
        raise HTTPException(status_code=500, detail=f"Failed to mark as read: {str(e)}")

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
        raise HTTPException(status_code=500, detail=f"Failed to mark all as read: {str(e)}")

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
        raise HTTPException(status_code=500, detail=f"Failed to send notifications: {str(e)}")
