from fastapi import APIRouter, Header, HTTPException
from firebase_admin import auth as firebase_auth
from google.cloud import firestore
from app.services.firestore import db

router = APIRouter(prefix="/admin", tags=["Admin"])


# -----------------------------------------------------
# 🔒 Helper: Verify Firebase token & check admin role
# -----------------------------------------------------
def require_admin(authorization: str | None):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization.split(" ")[1]

    try:
        decoded = firebase_auth.verify_id_token(token)
        uid = decoded["uid"]

        # Fetch Firestore user record
        doc = db.collection("users").document(uid).get()

        if not doc.exists:
            raise HTTPException(status_code=403, detail="User not found in database")

        user = doc.to_dict()

        if user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")

        return uid

    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))


# -----------------------------------------------------
# 📌 GET ALL USERS  (includes lastActivity)
# -----------------------------------------------------
@router.get("/users")
def get_all_users(authorization: str | None = Header(default=None)):
    require_admin(authorization)

    users = []
    for doc in db.collection("users").stream():
        data = doc.to_dict()

        # Ensure expected fields exist
        data.setdefault("lastActivity", None)   # <-- 🔥 IMPORTANT
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
def add_credits(uid: str, credits: int = 10, authorization: str | None = Header(default=None)):
    require_admin(authorization)

    ref = db.collection("users").document(uid)
    doc = ref.get()

    if not doc.exists:
        raise HTTPException(status_code=404, detail="User not found")

    current = doc.to_dict().get("credits", 0)
    ref.update({"credits": current + credits})

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
    return {"status": "success", "message": "User banned"}


# -----------------------------------------------------
# 📌 Force logout
# -----------------------------------------------------
@router.post("/user/{uid}/force-logout")
def force_logout(uid: str, authorization: str | None = Header(default=None)):
    require_admin(authorization)

    firebase_auth.revoke_refresh_tokens(uid)
    return {"status": "success", "message": "User forced to logout"}


# -----------------------------------------------------
# ❌ Delete User
# -----------------------------------------------------
@router.delete("/user/{uid}")
def delete_user(uid: str, authorization: str | None = Header(default=None)):
    require_admin(authorization)

    # Delete Firestore
    db.collection("users").document(uid).delete()

    # Delete Firebase Auth
    try:
        firebase_auth.delete_user(uid)
    except:
        pass

    return {"status": "success", "message": "User deleted"}