from fastapi import APIRouter, Header, HTTPException
from firebase_admin import auth as firebase_auth

from app.services.firestore import db
from google.cloud import firestore as gcfirestore

router = APIRouter(prefix="/auth", tags=["Auth"])

@router.get("/me")
async def get_current_user(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    try:
        # 1️⃣ Verify Firebase ID token
        token = authorization.replace("Bearer ", "")
        decoded = firebase_auth.verify_id_token(token)

        uid = decoded["uid"]
        email = decoded.get("email")

        # 2️⃣ Reference user doc in Firestore
        user_ref = db.collection("users").document(uid)
        doc = user_ref.get()

        if not doc.exists:
            # 3️⃣ Create a new user document with defaults
            profile_data = {
                "uid": uid,
                "email": email,
                "plan": "free",           # default plan
                "credits": 100,           # starting credits
                "createdAt": gcfirestore.SERVER_TIMESTAMP,
                "lastLoginAt": gcfirestore.SERVER_TIMESTAMP,
            }
            user_ref.set(profile_data)
        else:
            # 4️⃣ Update existing doc with latest email + last login
            profile_data = doc.to_dict() or {}
            user_ref.update(
                {
                    "email": email,
                    "lastLoginAt": gcfirestore.SERVER_TIMESTAMP,
                }
            )
            # keep local copy roughly in sync
            profile_data["email"] = email

        # 5️⃣ Return profile to frontend
        return profile_data

    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
