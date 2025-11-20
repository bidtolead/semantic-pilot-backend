from fastapi import APIRouter, Header, HTTPException
from firebase_admin import auth as firebase_auth
from app.services.firestore import db

router = APIRouter(prefix="/activity")

def get_uid_from_header(authorization: str | None):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token")

    token = authorization.split(" ")[1]
    decoded = firebase_auth.verify_id_token(token)
    return decoded["uid"]


@router.post("/heartbeat")
def heartbeat(authorization: str | None = Header(default=None)):
    uid = get_uid_from_header(authorization)

    db.collection("users").document(uid).update({
        "lastActivity": db.SERVER_TIMESTAMP,
        "online": True,
    })

    return {"status": "ok"}