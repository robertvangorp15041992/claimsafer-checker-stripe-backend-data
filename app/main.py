import os
import json
import pandas as pd
import numpy as np
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

# Import ingredient checker functionality
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from rapidfuzz import fuzz, process
from nltk.stem.snowball import SnowballStemmer
import re
from pathlib import Path
from unicodedata import normalize as u_normalize

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
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ Database tables created successfully")
    except Exception as e:
        print(f"❌ Database startup error: {e}")
    
    try:
        load_data()  # Load ingredient checker data
    except Exception as e:
        print(f"❌ Data loading error: {e}")
        # Don't crash the app if data loading fails

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

# ----------------------------------------------------
# Ingredient Checker Functionality
# ----------------------------------------------------

# Load CSV data on startup
CSV_PATH = 'masterfile_claims.csv'
df = None
gpt_variations = {}

def load_data():
    global df, gpt_variations
    try:
        print("🔍 Looking for CSV file at:", CSV_PATH)
        print("📁 Current working directory:", os.getcwd())
        print("📋 Files in current directory:", os.listdir('.'))
        
        if os.path.exists(CSV_PATH):
            print("✅ Successfully loaded CSV with", len(pd.read_csv(CSV_PATH)), "rows")
            df = pd.read_csv(CSV_PATH)
            print("📊 DataFrame columns:", list(df.columns))
            print("🎯 Sample data - first 3 rows:")
            print(df.head(3))
        else:
            print("❌ CSV file not found!")
            
        # Load GPT variations
        gpt_file = 'gpt_claim_variations.json'
        if os.path.exists(gpt_file):
            with open(gpt_file, 'r') as f:
                gpt_variations = json.load(f)
            print("✅ Loaded", len(gpt_variations), "GPT claim variations")
        else:
            print("❌ GPT variations file not found!")
            
    except Exception as e:
        print("❌ Error loading data:", e)

# Load data on startup
# @app.on_event("startup")
# def startup_event():
#     load_data()

def normalize_text(s: str) -> str:
    """Lowercase, remove accents, punctuation, collapse whitespace."""
    if not isinstance(s, str):
        return ""
    s = u_normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = s.lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

@app.get("/categories")
def get_categories():
    """Get all available categories."""
    if df is None:
        raise HTTPException(status_code=500, detail="Data not loaded")
    
    categories = df['Categories'].dropna().unique().tolist()
    return {"categories": categories}

@app.get("/_columns")
def get_columns():
    """Get DataFrame columns for debugging."""
    if df is None:
        raise HTTPException(status_code=500, detail="Data not loaded")
    
    return {"columns": list(df.columns)}

@app.post("/search-by-ingredient")
def search_by_ingredient(ingredient: str):
    """Search claims by ingredient name."""
    if df is None:
        raise HTTPException(status_code=500, detail="Data not loaded")
    
    normalized_ingredient = normalize_text(ingredient)
    results = []
    
    for _, row in df.iterrows():
        row_ingredient = normalize_text(str(row['Ingredient']))
        if normalized_ingredient in row_ingredient or row_ingredient in normalized_ingredient:
            results.append({
                "ingredient": row['Ingredient'],
                "country": row['Country'],
                "claim": row['Claim'],
                "dosage": row['Dosage'],
                "category": row['Categories']
            })
    
    return {"results": results[:50]}  # Limit to 50 results

@app.post("/search-by-claim")
def search_by_claim(claim: str):
    """Search ingredients by claim text."""
    if df is None:
        raise HTTPException(status_code=500, detail="Data not loaded")
    
    normalized_claim = normalize_text(claim)
    results = []
    
    for _, row in df.iterrows():
        row_claim = normalize_text(str(row['Claim']))
        if normalized_claim in row_claim or row_claim in normalized_claim:
            results.append({
                "ingredient": row['Ingredient'],
                "country": row['Country'],
                "claim": row['Claim'],
                "dosage": row['Dosage'],
                "category": row['Categories']
            })
    
    return {"results": results[:50]}  # Limit to 50 results

@app.get("/get-variations")
def get_variations():
    """Get GPT claim variations."""
    return {"variations": gpt_variations}

@app.post("/check-claims")
def check_claims(ingredient: str, claim: str = None, category: str = None):
    """Check if a claim is valid for an ingredient."""
    if df is None:
        raise HTTPException(status_code=500, detail="Data not loaded")
    
    normalized_ingredient = normalize_text(ingredient)
    results = []
    
    for _, row in df.iterrows():
        row_ingredient = normalize_text(str(row['Ingredient']))
        if normalized_ingredient in row_ingredient or row_ingredient in normalized_ingredient:
            if claim:
                row_claim = normalize_text(str(row['Claim']))
                normalized_claim = normalize_text(claim)
                if normalized_claim not in row_claim:
                    continue
            
            if category:
                row_category = normalize_text(str(row['Categories']))
                normalized_category = normalize_text(category)
                if normalized_category not in row_category:
                    continue
            
            results.append({
                "ingredient": row['Ingredient'],
                "country": row['Country'],
                "claim": row['Claim'],
                "dosage": row['Dosage'],
                "category": row['Categories'],
                "valid": True
            })
    
    return {"results": results, "valid": len(results) > 0}

@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "data_loaded": df is not None}
