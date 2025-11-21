from fastapi import APIRouter, Header, HTTPException
from firebase_admin import auth as firebase_auth
from app.services.firestore import db
from datetime import datetime, timezone

router = APIRouter(prefix="/activity", tags=["Activity"])


# -----------------------------------------------------
# 🔒 Helper: Extract UID from Authorization header
# -----------------------------------------------------
def get_uid_from_header(authorization: str | None):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid or missing token")

    token = authorization.split(" ")[1]

    try:
        decoded = firebase_auth.verify_id_token(token)
        return decoded["uid"]

    except Exception:
        raise HTTPException(status_code=401, detail="Invalid Firebase token")


# -----------------------------------------------------
# ❤️ Heartbeat — called every 60 seconds from frontend
# -----------------------------------------------------
@router.post("/heartbeat")
def heartbeat(authorization: str | None = Header(default=None)):
    uid = get_uid_from_header(authorization)

    # Save UTC timestamp of last activity
    db.collection("users").document(uid).set(
        {
            "lastHeartbeatAt": datetime.now(timezone.utc).isoformat()
        },
        merge=True
    )

    return {"status": "ok"}