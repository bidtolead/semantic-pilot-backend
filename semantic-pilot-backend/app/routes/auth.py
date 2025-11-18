from fastapi import APIRouter, HTTPException, Header
from app.services.firestore import db
import firebase_admin
from firebase_admin import auth as firebase_auth

router = APIRouter()

# -------------------------------
# GET CURRENT USER (AUTH /me)
# -------------------------------
@router.get("/me")
def get_current_user(authorization: str | None = Header(default=None)):
    """
    Reads the Bearer token from Authorization header,
    verifies Firebase ID token, returns user object.
    """

    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header")

    token = authorization.split(" ")[1]

    try:
        decoded = firebase_auth.verify_id_token(token)
        uid = decoded["uid"]

        user_ref = db.collection("users").document(uid).get()
        if user_ref.exists:
            return {"userId": uid, **user_ref.to_dict()}
        else:
            return {"userId": uid, "email": decoded.get("email")}
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))


# -------------------------------
# Existing login/register routes
# -------------------------------
@router.post("/login")
def login():
    return {"message": "login ok"}

@router.post("/register")
def register():
    return {"message": "register ok"}
