from fastapi import APIRouter, Header, HTTPException
from firebase_admin import auth as firebase_auth
from app.services.firestore import db
from google.cloud import firestore   # required

router = APIRouter(prefix="/activity", tags=["Activity"])


# -----------------------------------------------------
# Helper: extract UID from Firebase token
# -----------------------------------------------------
def get_uid_from_header(authorization: str | None):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token")

    token = authorization.split(" ")[1]
    decoded = firebase_auth.verify_id_token(token)
    return decoded["uid"]


# -----------------------------------------------------
# Heartbeat — called every 60 sec by frontend
# -----------------------------------------------------
@router.post("/heartbeat")
def heartbeat(authorization: str | None = Header(default=None)):
    uid = get_uid_from_header(authorization)

    # 🔥 FIXED: backend now uses "lastHeartbeatAt" to match frontend
    db.collection("users").document(uid).update({
        "lastHeartbeatAt": firestore.SERVER_TIMESTAMP,   # <-- IMPORTANT FIX
        "online": True,
    })

    return {"status": "ok"}