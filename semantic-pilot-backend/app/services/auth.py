from fastapi import Header, HTTPException
from firebase_admin import auth as firebase_auth

async def verify_firebase_token(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    try:
        token = authorization.replace("Bearer ", "")
        decoded = firebase_auth.verify_id_token(token)
        return decoded  # contains uid, email etc.
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
