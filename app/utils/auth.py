from fastapi import APIRouter, Header, HTTPException, Depends, Request
from firebase_admin import auth as firebase_auth

from app.services.firestore import db
from google.cloud import firestore as gcfirestore

router = APIRouter(prefix="/auth", tags=["Auth"])

def verify_token(authorization: str = Header(None)) -> dict:
    """FastAPI dependency to verify Firebase ID token.

    Returns the decoded token dict on success, or raises 401 on failure.
    This can be used in any route via `Depends(verify_token)`.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    try:
        token = authorization.replace("Bearer ", "")
        decoded = firebase_auth.verify_id_token(token)
        return decoded
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def require_admin(authorization: str = Header(None)) -> dict:
    """FastAPI dependency to verify Firebase ID token AND enforce admin role.
    
    Returns the decoded token dict on success.
    Raises 401 for invalid token, 403 for non-admin users.
    Use this for admin-only endpoints.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    
    try:
        token = authorization.replace("Bearer ", "")
        decoded = firebase_auth.verify_id_token(token)
        uid = decoded.get("uid")
        
        # Check admin role in Firestore
        user_ref = db.collection("users").document(uid)
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            raise HTTPException(status_code=403, detail="User not found")
        
        user_data = user_doc.to_dict() or {}
        if user_data.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")
        
        return decoded
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

def get_current_user(decoded: dict = Depends(verify_token)) -> dict:
    """Dependency to get current user data from Firestore based on token."""
    try:
        uid = decoded.get("uid")
        user_ref = db.collection("users").document(uid)
        doc = user_ref.get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_data = doc.to_dict() or {}
        user_data["uid"] = uid
        return user_data
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to get user data")

def admin_required(decoded: dict = Depends(verify_token)) -> dict:
    """Dependency to enforce admin role. Returns user data."""
    try:
        uid = decoded.get("uid")
        user_ref = db.collection("users").document(uid)
        doc = user_ref.get()
        
        if not doc.exists:
            raise HTTPException(status_code=403, detail="User not found")
        
        user_data = doc.to_dict() or {}
        if user_data.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")
        
        user_data["uid"] = uid
        return user_data
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=403, detail="Admin verification failed")

@router.get("/me")
async def get_me_route(decoded: dict = Depends(verify_token), request: Request = None):
    try:
        uid = decoded.get("uid")
        email = decoded.get("email")

        # 1️⃣ Derive country from headers if available
        country_code = None
        country_name = None
        try:
            if request:
                # Prefer Cloudflare header if present
                cc = request.headers.get("CF-IPCountry") or request.headers.get("X-AppEngine-Country")
                if cc and isinstance(cc, str) and len(cc) in (2, 3):
                    country_code = cc.upper()
        except Exception:
            pass

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
            if country_code:
                profile_data["countryCode"] = country_code
                profile_data["lastSeenCountryAt"] = gcfirestore.SERVER_TIMESTAMP
            user_ref.set(profile_data)
        else:
            # 4️⃣ Update existing doc with latest email + last login
            profile_data = doc.to_dict() or {}
            update_fields = {
                "email": email,
                "lastLoginAt": gcfirestore.SERVER_TIMESTAMP,
            }
            if country_code:
                update_fields["countryCode"] = country_code
                update_fields["lastSeenCountryAt"] = gcfirestore.SERVER_TIMESTAMP
            user_ref.update(update_fields)
            # keep local copy roughly in sync
            profile_data["email"] = email
            if country_code:
                profile_data["countryCode"] = country_code

        # 5️⃣ Return profile to frontend
        return profile_data

    except HTTPException:
        # Bubble up auth errors
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to retrieve user profile")
