from fastapi import APIRouter, Header, HTTPException
from firebase_admin import auth as firebase_auth
from app.services.firestore import db
from app.utils.cost_calculator import get_cost_per_1k_tokens, calculate_openai_cost

router = APIRouter(prefix="/admin", tags=["Admin"])


# -----------------------------------------------------
# 🔒 Helper: Verify Firebase token & check admin role
# -----------------------------------------------------
def require_admin(authorization: str | None):
    """
    Extract the Firebase ID token from the Authorization header,
    verify it, look up the user in Firestore, and ensure they
    have role == "admin".
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid Authorization header",
        )

    token = authorization.split(" ")[1]

    try:
        decoded = firebase_auth.verify_id_token(token)
        uid = decoded["uid"]

        # Fetch user record from Firestore
        doc = db.collection("users").document(uid).get()

        if not doc.exists:
            raise HTTPException(status_code=403, detail="User not found in database")

        user = doc.to_dict() or {}

        if user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")

        return uid

    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))


# -----------------------------------------------------
# ✅ Quick admin check (lightweight)
# -----------------------------------------------------
@router.get("/ping")
def admin_ping(authorization: str | None = Header(default=None)):
    """Return a simple OK if the requester is an admin."""
    uid = require_admin(authorization)
    return {"status": "ok", "uid": uid}


# -----------------------------------------------------
# 📌 GET ALL USERS (includes heartbeat → lastActivity)
# -----------------------------------------------------
@router.get("/users")
def get_all_users(authorization: str | None = Header(default=None)):
    """
    Return all users with normalized fields so the frontend
    can safely display them. In particular we normalize the
    heartbeat field into `lastActivity`.
    """
    require_admin(authorization)

    users_ref = db.collection("users").stream()
    users = []

    for doc in users_ref:
        data = doc.to_dict() or {}

        # ---------------------------------------------
        # 🔥 Normalize heartbeat → lastActivity
        # ---------------------------------------------
        # The heartbeat endpoint writes `lastHeartbeatAt`.
        # The admin frontend expects `lastActivity`.
        last_hb = data.get("lastHeartbeatAt")
        if last_hb and "lastActivity" not in data:
            data["lastActivity"] = last_hb

        # Ensure expected fields exist so TS/front-end
        # can rely on them without lots of undefined checks.
        data.setdefault("lastActivity", None)
        data.setdefault("createdAt", None)
        data.setdefault("lastLoginAt", None)
        data.setdefault("credits", 0)
        data.setdefault("plan", "free")
        data.setdefault("researchCount", 0)
        data.setdefault("tokenUsage", 0)
        data.setdefault("totalSpend", 0)
        data.setdefault("role", "user")
        
        # Recalculate totalSpend if it's 0 but tokenUsage exists
        if data["totalSpend"] == 0 and data["tokenUsage"] > 0:
            token_usage = data["tokenUsage"]
            estimated_prompt_tokens = token_usage // 2
            estimated_completion_tokens = token_usage - estimated_prompt_tokens
            
            estimated_cost = calculate_openai_cost(
                prompt_tokens=estimated_prompt_tokens,
                completion_tokens=estimated_completion_tokens,
                model="gpt-4o-mini"
            )
            
            # Update in Firestore
            db.collection("users").document(doc.id).update({
                "totalSpend": estimated_cost
            })
            
            data["totalSpend"] = estimated_cost

        # Add Firestore document ID as userId
        data["userId"] = doc.id
        users.append(data)

    return {"users": users}


# -----------------------------------------------------
# 📌 Reset Credits
# -----------------------------------------------------
@router.post("/user/{uid}/reset-credits")
def reset_credits(uid: str, authorization: str | None = Header(default=None)):
    require_admin(authorization)

    db.collection("users").document(uid).update({"credits": 50})
    return {"status": "success", "message": "Credits reset to 50"}


# -----------------------------------------------------
# 📌 Add Credits
# -----------------------------------------------------
@router.post("/user/{uid}/add-credits")
def add_credits(
    uid: str,
    credits: int = 10,
    authorization: str | None = Header(default=None),
):
    """
    Add `credits` to the user's current credit balance.
    Frontend should send `{ "credits": <amount> }` in JSON.
    """
    require_admin(authorization)

    user_ref = db.collection("users").document(uid)
    doc = user_ref.get()

    if not doc.exists:
        raise HTTPException(status_code=404, detail="User not found")

    current = doc.to_dict().get("credits", 0)
    user_ref.update({"credits": current + credits})

    return {"status": "success", "credits_added": credits}


# -----------------------------------------------------
# 📌 Make Admin
# -----------------------------------------------------
@router.post("/user/{uid}/make-admin")
def make_admin(uid: str, authorization: str | None = Header(default=None)):
    require_admin(authorization)

    db.collection("users").document(uid).update({"role": "admin"})
    return {"status": "success", "message": "User promoted to admin"}


# -----------------------------------------------------
# 📌 Remove Admin
# -----------------------------------------------------
@router.post("/user/{uid}/remove-admin")
def remove_admin(uid: str, authorization: str | None = Header(default=None)):
    require_admin(authorization)

    db.collection("users").document(uid).update({"role": "user"})
    return {"status": "success", "message": "Admin role removed"}


# -----------------------------------------------------
# 📌 Ban User
# -----------------------------------------------------
@router.post("/user/{uid}/ban")
def ban_user(uid: str, authorization: str | None = Header(default=None)):
    require_admin(authorization)

    db.collection("users").document(uid).update({"banned": True})
    return {"status": "success", "message": "User has been banned"}


# -----------------------------------------------------
# 📌 Force logout (revoke tokens)
# -----------------------------------------------------
@router.post("/user/{uid}/force-logout")
def force_logout(uid: str, authorization: str | None = Header(default=None)):
    require_admin(authorization)

    firebase_auth.revoke_refresh_tokens(uid)
    return {"status": "success", "message": "User will logout on next refresh"}


# -----------------------------------------------------
# ❌ Delete User
# -----------------------------------------------------
@router.delete("/user/{uid}")
def delete_user(uid: str, authorization: str | None = Header(default=None)):
    require_admin(authorization)

    # Delete Firestore record
    db.collection("users").document(uid).delete()

    # Try to delete from Firebase Auth as well
    try:
        firebase_auth.delete_user(uid)
    except Exception:
        # Ignore if user doesn't exist in Auth
        pass

    return {"status": "success", "message": "User deleted"}


# -----------------------------------------------------
# 📌 UPDATE SYSTEM SETTINGS (OpenAI Model)
# -----------------------------------------------------
from pydantic import BaseModel

class ModelUpdateRequest(BaseModel):
    model: str

@router.post("/settings/model")
def update_openai_model(
    req: ModelUpdateRequest,
    authorization: str | None = Header(default=None)
):
    """Update the OpenAI model to use for keyword research"""
    require_admin(authorization)
    
    # Validate model name
    allowed_models = ["gpt-4o-mini", "gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"]
    if req.model not in allowed_models:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid model. Allowed: {', '.join(allowed_models)}"
        )
    
    # Store in Firestore settings collection
    settings_ref = db.collection("system_settings").document("openai")
    settings_ref.set({
        "model": req.model,
        "updated_at": firestore.SERVER_TIMESTAMP,
    }, merge=True)
    
    return {"status": "success", "model": req.model}


@router.get("/settings/model")
def get_openai_model(authorization: str | None = Header(default=None)):
    """Get the current OpenAI model setting with cost information"""
    require_admin(authorization)
    
    settings_ref = db.collection("system_settings").document("openai")
    settings_doc = settings_ref.get()
    
    current_model = "gpt-4o-mini"
    if settings_doc.exists:
        data = settings_doc.to_dict()
        current_model = data.get("model", "gpt-4o-mini")
    
    # Get cost per 1000 tokens for current model
    cost_per_1k = get_cost_per_1k_tokens(current_model)
    
    return {
        "model": current_model,
        "cost_per_1k_tokens": cost_per_1k
    }


@router.post("/recalculate-spend")
def recalculate_user_spend(authorization: str | None = Header(default=None)):
    """Recalculate totalSpend for all users based on existing tokenUsage"""
    require_admin(authorization)
    
    users_ref = db.collection("users").stream()
    updated_count = 0
    total_spend_calculated = 0.0
    
    for user_doc in users_ref:
        user_data = user_doc.to_dict() or {}
        token_usage = user_data.get("tokenUsage", 0)
        
        if token_usage > 0:
            # Assume 50/50 split between prompt and completion tokens
            # This is an approximation since we don't have the exact split for old data
            estimated_prompt_tokens = token_usage // 2
            estimated_completion_tokens = token_usage - estimated_prompt_tokens
            
            # Calculate cost using gpt-4o-mini pricing (most common model)
            estimated_cost = calculate_openai_cost(
                prompt_tokens=estimated_prompt_tokens,
                completion_tokens=estimated_completion_tokens,
                model="gpt-4o-mini"
            )
            
            # Update user's totalSpend
            db.collection("users").document(user_doc.id).update({
                "totalSpend": estimated_cost
            })
            
            updated_count += 1
            total_spend_calculated += estimated_cost
    
    return {
        "status": "success",
        "users_updated": updated_count,
        "total_spend_calculated": round(total_spend_calculated, 4)
    }


from google.cloud import firestore