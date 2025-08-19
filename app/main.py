import os
import json
from fastapi import FastAPI, Request, Depends, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from dotenv import load_dotenv
import stripe
from werkzeug.security import generate_password_hash
from .models import Base, User, WebhookEvent, Tier
from .db import engine, SessionLocal
from .billing import PRICE_TO_TIER, DEFAULT_TIER, tier_rank
from .utils import sign_onboarding_token, verify_onboarding_token, send_email, normalize_email
from app.routes.users import router as users_router
from app.routes.usage import router as usage_router
from app.services.memberships import upsert_membership_from_checkout, upsert_membership_from_subscription
from app.auth import router as auth_router
from app.routes.limits import router as limits_router
from app.routes.admin import router as admin_router
from fastapi.templating import Jinja2Templates
from app.routes.dashboard import router as dashboard_router
from starlette.middleware.sessions import SessionMiddleware

load_dotenv()
STRIPE_API_KEY = os.getenv("STRIPE_API_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8000")
SESSION_SECRET = os.getenv("SESSION_SECRET", "dev-session-secret")

stripe.api_key = STRIPE_API_KEY

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, session_cookie="session", https_only=APP_BASE_URL.startswith("https://"), same_site="lax")

@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/webhook/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid Stripe signature"})

    event_id = event["id"]
    if db.query(WebhookEvent).filter_by(stripe_event_id=event_id).first():
        return JSONResponse({"status": "duplicate_ignored"})

    db.add(WebhookEvent(
        stripe_event_id=event_id,
        type=event["type"],
        payload=json.dumps(event),
    ))
    db.commit()

    try:
        if event["type"] == "checkout.session.completed":
            session = event["data"]["object"]
            email = (
                session.get("customer_details", {}).get("email")
                or session.get("customer_email")
            )
            if not email and session.get("id"):
                # Fallback: retrieve session with expand
                session_obj = stripe.checkout.Session.retrieve(
                    session["id"], expand=["customer"]
                )
                email = (
                    session_obj.get("customer_details", {}).get("email")
                    or session_obj.get("customer_email")
                    or (session_obj.get("customer") and session_obj["customer"].get("email"))
                )
            if not email:
                return JSONResponse({"status": "no_email_found"})
            stripe_customer_id = session.get("customer")
            price_ids = []
            if "line_items" in session:
                for item in session["line_items"]["data"]:
                    price_ids.append(item["price"]["id"])
            else:
                # Fetch line items if not present
                try:
                    line_items = stripe.checkout.Session.list_line_items(session["id"])
                    for item in line_items["data"]:
                        price_ids.append(item["price"]["id"])
                except Exception:
                    pass
            user = upsert_membership_from_checkout(
                db,
                email=email,
                stripe_customer_id=stripe_customer_id,
                line_item_price_ids=price_ids,
                stripe_event_id=event_id,
                reason="checkout.session.completed",
            )
            # Send onboarding email
            try:
                from app.auth import send_onboarding_email
                send_onboarding_email(user.email, user.tier)
            except Exception:
                pass  # Don't fail webhook if email fails
        elif event["type"] == "invoice.payment_succeeded":
            obj = event["data"]["object"]
            stripe_customer_id = obj.get("customer")
            user = db.query(User).filter_by(stripe_customer_id=stripe_customer_id).first()
            if not user:
                return JSONResponse({"status": "user_not_found"})
            # Optionally recompute tier from subscription
        elif event["type"] in ["customer.subscription.updated", "customer.subscription.deleted"]:
            obj = event["data"]["object"]
            stripe_customer_id = obj.get("customer")
            # Try to find user by customer_id
            user = db.query(User).filter_by(stripe_customer_id=stripe_customer_id).first()
            email = user.email if user else None
            if not email and obj.get("customer"):
                # Fallback: fetch Stripe customer
                try:
                    customer = stripe.Customer.retrieve(obj["customer"])
                    email = customer.get("email")
                except Exception:
                    pass
            items = obj.get("items", {}).get("data", [])
            price_ids = [item.get("price", {}).get("id") for item in items if item.get("price", {}).get("id")]
            user = upsert_membership_from_subscription(
                db,
                email=email,
                stripe_customer_id=stripe_customer_id,
                active_subscription_price_ids=price_ids,
                stripe_event_id=event_id,
                reason=event["type"],
            ) if email else None
    except Exception as e:
        # Log error, but don't crash webhook
        print(f"Webhook processing error: {e}")
    return JSONResponse({"status": "ok"})

@app.get("/auth/activate", response_class=HTMLResponse)
def activate_form(token: str):
    from app.auth import activate_form as real_activate_form
    return real_activate_form(token=token)

@app.post("/auth/activate")
def activate_post(token: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    from app.auth import activate_post as real_activate_post
    return real_activate_post(token=token, password=password, db=db)

templates = Jinja2Templates(directory="app/templates")

app.include_router(users_router, prefix="")
app.include_router(usage_router, prefix="")
app.include_router(auth_router, prefix="")
app.include_router(limits_router)
app.include_router(admin_router)
app.include_router(dashboard_router)
