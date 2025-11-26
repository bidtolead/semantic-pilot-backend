from fastapi import APIRouter, HTTPException, Header
from app.services.firestore import db
import firebase_admin
from firebase_admin import auth as firebase_auth
from datetime import datetime

router = APIRouter()

# ----------------------------------------
# DEFAULT USER FIELDS (GLOBAL CONSTANT)
# ----------------------------------------
DEFAULT_USER_FIELDS = {
    "email": None,
    "firstName": None,
    "role": "user",
    "plan": "free",
    "credits": 100,
    "researchCount": 0,
    "tokenUsage": 0,
    "totalSpend": 0,
    "createdAt": None,
    "lastLoginAt": None,
    "uid": None,
}


# ----------------------------------------
# GET CURRENT USER (/me)
# ----------------------------------------
@router.get("/me")
def get_current_user(authorization: str | None = Header(default=None)):
    """
    Returns the authenticated user's full profile.
    Auto-creates missing Firestore user entry.
    Ensures all fields exist for consistency.
    """

    # Missing header
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    # Wrong format
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header")

    token = authorization.split(" ")[1]

    try:
        # Verify Firebase ID Token
        decoded = firebase_auth.verify_id_token(token)
        uid = decoded["uid"]
        email = decoded.get("email")

        # Reference to Firestore
        user_ref = db.collection("users").document(uid)
        snapshot = user_ref.get()

        # ----------------------------------------
        # CASE 1 — DOCUMENT EXISTS
        # ----------------------------------------
        if snapshot.exists:
            # Load data
            data = snapshot.to_dict()

            # Ensure ALL fields exist
            for key, default_value in DEFAULT_USER_FIELDS.items():
                if key not in data:
                    data[key] = default_value

            # Always update lastLoginAt on each request
            data["lastLoginAt"] = datetime.utcnow().isoformat()
            data["uid"] = uid

            # Save fixed document
            user_ref.set(data, merge=True)

            return data

        # ----------------------------------------
        # CASE 2 — USER DOES NOT EXIST (CREATE)
        # ----------------------------------------
        new_user = DEFAULT_USER_FIELDS.copy()
        new_user["email"] = email
        new_user["uid"] = uid
        new_user["createdAt"] = datetime.utcnow().isoformat()
        new_user["lastLoginAt"] = datetime.utcnow().isoformat()
        
        # Extract first name from Google displayName if available
        display_name = decoded.get("name")
        if display_name and not new_user["firstName"]:
            new_user["firstName"] = display_name.split()[0] if display_name else None

        user_ref.set(new_user)

        return new_user

    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))


# ----------------------------------------
# UPDATE USER PROFILE
# ----------------------------------------
@router.post("/auth/update-profile")
def update_profile(
    body: dict,
    authorization: str | None = Header(default=None)
):
    """Update user profile fields like firstName."""
    
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization.split(" ")[1]

    try:
        decoded = firebase_auth.verify_id_token(token)
        uid = decoded["uid"]
        
        user_ref = db.collection("users").document(uid)
        
        # Only allow updating specific fields
        allowed_fields = ["firstName"]
        update_data = {k: v for k, v in body.items() if k in allowed_fields}
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No valid fields to update")
        
        user_ref.update(update_data)
        
        return {"status": "success", "updated": update_data}
        
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))


# ----------------------------------------
# (Removed obsolete placeholder /login endpoint; Firebase handles auth client-side.)


@router.post("/register")
def register():
    return {"message": "register ok"}