from fastapi import APIRouter, Header, HTTPException, Request
from app.services.firestore import db
from firebase_admin import auth as firebase_auth
from app.core.config import STRIPE_SECRET_KEY, STRIPE_PRICE_PRO, STRIPE_WEBHOOK_SECRET, STRIPE_DUMMY_MODE
import stripe
from datetime import datetime

router = APIRouter(prefix="/payments", tags=["Payments"])

if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY


def _require_auth(authorization: str | None):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization.split(" ")[1]
    try:
        decoded = firebase_auth.verify_id_token(token)
        return decoded["uid"], decoded
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


@router.post("/create-checkout-session")
def create_checkout_session(authorization: str | None = Header(default=None)):
    """Create a Stripe Checkout Session for upgrading to Pro plan.
    Returns the session URL to redirect user.
    """
    if STRIPE_DUMMY_MODE:
        # Return a dummy URL for testing UI flow without Stripe keys
        return {"status": "ok", "url": "https://checkout.stripe.com/test-session", "id": "dummy_session"}
    if not STRIPE_SECRET_KEY or not STRIPE_PRICE_PRO:
        raise HTTPException(status_code=500, detail="Stripe not configured")

    uid, decoded = _require_auth(authorization)

    # Retrieve user (ensure exists)
    user_ref = db.collection("users").document(uid)
    snap = user_ref.get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="User not found")
    user = snap.to_dict() or {}

    # If already pro, short-circuit
    if user.get("plan") == "pro":
        return {"status": "already-pro"}

    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            payment_method_types=["card"],
            line_items=[{"price": STRIPE_PRICE_PRO, "quantity": 1}],
            customer_email=user.get("email"),
            success_url=user.get("frontendUrlOverride") or "https://semanticpilot.com/dashboard?upgrade=success",
            cancel_url=user.get("frontendUrlOverride") or "https://semanticpilot.com/dashboard?upgrade=cancel",
            metadata={"uid": uid, "plan_target": "pro"},
        )
        return {"status": "ok", "url": session.url, "id": session.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events to apply plan upgrades.
    Expected event: checkout.session.completed
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if STRIPE_DUMMY_MODE:
        # In dummy mode, acknowledge webhook without processing
        return {"received": True, "dummy": True}
    if not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=500, detail="Webhook secret not configured")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        uid = session.get("metadata", {}).get("uid")
        target_plan = session.get("metadata", {}).get("plan_target") or "pro"

        if uid and target_plan == "pro":
            user_ref = db.collection("users").document(uid)
            snap = user_ref.get()
            if snap.exists:
                user = snap.to_dict() or {}
                # Idempotent upgrade: only if not already pro
                if user.get("plan") != "pro":
                    bonus_credits = 1000
                    new_credits = (user.get("credits", 0) or 0) + bonus_credits
                    user_ref.update({
                        "plan": "pro",
                        "credits": new_credits,
                        "lastLoginAt": datetime.utcnow().isoformat(),
                        "stripeCheckoutId": session.get("id"),
                        "stripeCustomerId": session.get("customer"),
                        "stripeSubscriptionId": session.get("subscription"),
                    })
                    return {"received": True, "upgraded": True}
            return {"received": True, "upgraded": False}

    # Unhandled event types are acknowledged
    return {"received": True}
