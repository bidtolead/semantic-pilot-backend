# Stripe Integration (Initial Setup)

## 1. Environment Variables (.env)
Add these keys:
```
STRIPE_SECRET_KEY=sk_live_or_test_xxx
STRIPE_PRICE_PRO=price_xxx   # Price ID for Pro subscription (recurring)
STRIPE_WEBHOOK_SECRET=whsec_xxx
```
For local testing use Stripe test keys.

## 2. Create Price
In Stripe Dashboard → Products:
- Create product: "Semantic Pilot Pro"
- Billing: Monthly (or Yearly) as desired
- Copy the Price ID → STRIPE_PRICE_PRO

## 3. Webhook Endpoint
Set webhook endpoint URL (test mode):
```
https://your-backend-host/payments/webhook
```
Events to send (minimum):
- `checkout.session.completed`

## 4. Checkout Flow
Frontend (dashboard) calls:
```
POST /payments/create-checkout-session (Authorization: Bearer <FirebaseIdToken>)
```
Response example:
```
{ "status": "ok", "url": "https://checkout.stripe.com/c/session_xyz", "id": "cs_test_xyz" }
```
Redirect user to `url`.

## 5. Post-Purchase Upgrade
Webhook `checkout.session.completed` triggers plan upgrade:
- Sets `plan` -> `pro`
- Adds 1000 bonus credits
- Stores Stripe IDs: `stripeCheckoutId`, `stripeCustomerId`, `stripeSubscriptionId`
Idempotent: If already pro, no duplicate credit.

## 6. Testing with Stripe CLI
```
stripe login
stripe listen --forward-to localhost:8000/payments/webhook
stripe trigger checkout.session.completed
```
Replace localhost:8000 with actual dev server.

## 7. Extending
- Add `customer` persistence if you want portal links.
- Add cancellation endpoint: Use subscription ID to cancel at period end.
- Add billing portal session: `stripe.billing_portal.Session.create`.

## 8. Security Notes
- Webhook signature verified using `STRIPE_WEBHOOK_SECRET`.
- Only authenticated users can create sessions.
- Ensure HTTPS in production.

## 9. Frontend Success Handling
After redirect back, detect `?upgrade=success` query to show success banner and refresh `/me` profile.

## 10. Future Enhancements
- Usage metering for overage billing.
- Tiered plans (pass price ID dynamically).
- In-app invoices retrieval.

