from fastapi import APIRouter, Header, HTTPException
from firebase_admin import auth as firebase_auth
from app.services.firestore import db
from google.cloud import firestore

router = APIRouter(prefix="/admin", tags=["Admin"])


# -----------------------------------------------------
# Verify Firebase token + require admin
# -----------------------------------------------------
def require_admin(authorization: str | None):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization.split(" ")[1]

    try:
        decoded = firebase_auth.verify_id_token(token)
        uid = decoded["uid"]

        user_doc = db.collection("users").document(uid).get()
        if not user_doc.exists:
            raise HTTPException(status_code=403, detail="User not found in database")

        user = user_doc.to_dict()
        if user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")

        return uid

    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))


# -----------------------------------------------------
# GET ALL USERS
# -----------------------------------------------------
@router.get("/users")
def get_all_users(authorization: str | None = Header(default=None)):
    require_admin(authorization)

    users_ref = db.collection("users").stream()
    users = []

    for doc in users_ref:
        data = doc.to_dict()

        # Ensure all expected fields exist
        data.setdefault("lastActivity", None)      # ← IMPORTANT
        data.setdefault("createdAt", None)
        data.setdefault("lastLoginAt", None)
        data.setdefault("credits", 0)
        data.setdefault("plan", "free")
        data.setdefault("researchCount", 0)
        data.setdefault("tokenUsage", 0)
        data.setdefault("totalSpend", 0)
        data.setdefault("role", "user")

        data["userId"] = doc.id
        users.append(data)

    return {"users": users}


# -----------------------------------------------------
# RESET CREDITS
# -----------------------------------------------------
@router.post("/user/{uid}/reset-credits")
def reset_credits(uid: str, authorization: str | None = Header(default=None)):
    require_admin(authorization)

    db.collection("users").document(uid).update({"credits": 50})
    return {"status": "success", "message": "Credits reset to 50"}


# -----------------------------------------------------
# ADD CREDITS
# -----------------------------------------------------
@router.post("/user/{uid}/add-credits")
def add_credits(uid: str, credits: int = 10, authorization: str | None = Header(default=None)):
    require_admin(authorization)

    user_ref = db.collection("users").document(uid)
    doc = user_ref.get()

    if not doc.exists:
        raise HTTPException(status_code=404, detail="User not found")

    current = doc.to_dict().get("credits", 0)
    user_ref.update({"credits": current + credits})

    return {"status": "success", "credits_added": credits}


# -----------------------------------------------------
# MAKE ADMIN
# -----------------------------------------------------
@router.post("/user/{uid}/make-admin")
def make_admin(uid: str, authorization: str | None = Header(default=None)):
    require_admin(authorization)

    db.collection("users").document(uid).update({"role": "admin"})
    return {"status": "success", "message": "User promoted to admin"}


# -----------------------------------------------------
# REMOVE ADMIN
# -----------------------------------------------------
@router.post("/user/{uid}/remove-admin")
def remove_admin(uid: str, authorization: str | None = Header(default=None)):
    require_admin(authorization)

    db.collection("users").document(uid).update({"role": "user"})
    return {"status": "success", "message": "Admin role removed"}


# -----------------------------------------------------
# BAN USER
# -----------------------------------------------------
@router.post("/user/{uid}/ban")
def ban_user(uid: str, authorization: str | None = Header(default=None)):
    require_admin(authorization)

    db.collection("users").document(uid).update({"banned": True})
    return {"status": "success", "message": "User banned"}


# -----------------------------------------------------
# FORCE LOGOUT
# -----------------------------------------------------
@router.post("/user/{uid}/force-logout")
def force_logout(uid: str, authorization: str | None = Header(default=None)):
    require_admin(authorization)

    firebase_auth.revoke_refresh_tokens(uid)
    return {"status": "success", "message": "User will be logged out next refresh"}


# -----------------------------------------------------
# DELETE USER
# -----------------------------------------------------
@router.delete("/user/{uid}")
def delete_user(uid: str, authorization: str | None = Header(default=None)):
    require_admin(authorization)

    # Delete Firestore record
    db.collection("users").document(uid).delete()

    # Delete Firebase Auth account (ignore errors)
    try:
        firebase_auth.delete_user(uid)
    except:
        pass

    return {"status": "success", "message": "User deleted"}