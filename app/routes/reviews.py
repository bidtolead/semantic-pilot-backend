from fastapi import APIRouter, Header, HTTPException
from firebase_admin import auth as firebase_auth
from app.services.firestore import db
from datetime import datetime

router = APIRouter(prefix="/reviews", tags=["Reviews"])


def _auth(authorization: str | None):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization.split(" ")[1]
    try:
        decoded = firebase_auth.verify_id_token(token)
        return decoded["uid"], decoded
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


@router.get("/check")
def check_review_status(authorization: str | None = Header(default=None)):
    """Check if the current user has already submitted a review."""
    uid, _ = _auth(authorization)
    existing_qry = db.collection("reviews").where("uid", "==", uid).limit(1)
    existing = list(existing_qry.stream())
    if len(existing) > 0:
        review_data = existing[0].to_dict() or {}
        return {
            "hasSubmitted": True,
            "approved": review_data.get("approved", False),
            "rejected": review_data.get("rejected", False)
        }
    return {"hasSubmitted": False, "approved": False, "rejected": False}


@router.post("")
def submit_review(body: dict, authorization: str | None = Header(default=None)):
    """Users submit a review. Stored as pending approval by default.
    body: { rating: 1-5, text: string }
    """
    uid, decoded = _auth(authorization)

    rating = int(body.get("rating", 0))
    text = (body.get("text") or "").strip()
    if rating < 1 or rating > 5:
        raise HTTPException(status_code=400, detail="Rating must be 1-5")
    if not text or len(text) < 10:
        raise HTTPException(status_code=400, detail="Review text is too short")

    user_ref = db.collection("users").document(uid)
    snap = user_ref.get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="User not found")
    user = snap.to_dict() or {}

    # Require at least 10 credits used (approx via researchCount or tokenUsage)
    research_count = int(user.get("researchCount") or 0)
    token_usage = int(user.get("tokenUsage") or 0)
    if research_count < 10 and token_usage < 10:
        raise HTTPException(status_code=403, detail="Review available after using at least 10 credits")

    # Enforce single review per user (pending or approved)
    existing_qry = db.collection("reviews").where("uid", "==", uid).limit(1)
    existing = list(existing_qry.stream())
    if existing:
        raise HTTPException(status_code=409, detail="You have already submitted a review")

    review = {
        "uid": uid,
        "email": user.get("email"),
        "firstName": user.get("firstName"),
        "rating": rating,
        "text": text,
        "approved": False,
        "createdAt": datetime.utcnow().isoformat(),
    }
    ref = db.collection("reviews").document()
    ref.set(review)
    return {"status": "submitted"}


@router.get("/pending")
def list_pending_reviews(authorization: str | None = Header(default=None)):
    """Admin-only: list pending reviews."""
    uid, _ = _auth(authorization)
    user = db.collection("users").document(uid).get().to_dict() or {}
    if user.get("role") not in ["admin", "tester"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    # Avoid composite index requirement by sorting in Python
    qry = db.collection("reviews").where("approved", "==", False).limit(50)
    docs = qry.stream()
    items = []
    for d in docs:
        r = d.to_dict() or {}
        r["id"] = d.id
        items.append(r)
    items.sort(key=lambda x: x.get("createdAt", ""), reverse=True)
    return {"items": items}


@router.post("/{review_id}/approve")
def approve_review(review_id: str, authorization: str | None = Header(default=None)):
    """Admin-only: approve a review to make public."""
    uid, _ = _auth(authorization)
    user = db.collection("users").document(uid).get().to_dict() or {}
    if user.get("role") not in ["admin", "tester"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    ref = db.collection("reviews").document(review_id)
    if not ref.get().exists:
        raise HTTPException(status_code=404, detail="Review not found")
    ref.update({"approved": True})
    return {"status": "approved"}


@router.delete("/{review_id}")
def delete_review(review_id: str, authorization: str | None = Header(default=None)):
    """Admin-only: delete a review (pending or approved)."""
    uid, _ = _auth(authorization)
    user = db.collection("users").document(uid).get().to_dict() or {}
    if user.get("role") not in ["admin", "tester"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    ref = db.collection("reviews").document(review_id)
    if not ref.get().exists:
        raise HTTPException(status_code=404, detail="Review not found")
    ref.delete()
    return {"status": "deleted"}


@router.get("/approved")
def list_approved_reviews():
    """Public list of approved reviews for homepage."""
    # Avoid composite index requirement by sorting in Python
    qry = db.collection("reviews").where("approved", "==", True).limit(50)
    docs = qry.stream()
    rows = []
    for d in docs:
        r = d.to_dict() or {}
        rows.append(r)
    rows.sort(key=lambda x: x.get("createdAt", ""), reverse=True)
    items = []
    for r in rows[:12]:
        items.append({
            "firstName": r.get("firstName") or "User",
            "rating": r.get("rating") or 5,
            "text": r.get("text") or "",
        })
    return {"items": items}


@router.get("/approved/all")
def list_all_approved_reviews(authorization: str | None = Header(default=None)):
    """Admin-only: list all approved reviews with full details including IDs for management."""
    uid, _ = _auth(authorization)
    user = db.collection("users").document(uid).get().to_dict() or {}
    if user.get("role") not in ["admin", "tester"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    qry = db.collection("reviews").where("approved", "==", True).limit(50)
    docs = qry.stream()
    items = []
    for d in docs:
        r = d.to_dict() or {}
        r["id"] = d.id
        items.append(r)
    items.sort(key=lambda x: x.get("createdAt", ""), reverse=True)
    return {"items": items}
