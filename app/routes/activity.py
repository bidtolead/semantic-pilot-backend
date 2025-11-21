from fastapi import APIRouter, Header, HTTPException
from firebase_admin import auth as firebase_auth
from app.services.firestore import db
from google.cloud import firestore   # ✅ REQUIRED FIX

router = APIRouter(prefix="/activity", tags=["Activity"])


def get_uid_from_header(authorization: str | None):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token")

    token = authorization.split(" ")[1]
    decoded = firebase_auth.verify_id_token(token)
    return decoded["uid"]


@router.post("/heartbeat")
def heartbeat(authorization: str | None = Header(default=None)):
    uid = get_uid_from_header(authorization)

    # ✅ ABSOLUTE REQUIRED FIX
    db.collection("users").document(uid).update({
        "lastActivity": firestore.SERVER_TIMESTAMP,
        "online": True,
    })

    return {"status": "ok"}