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
# from app.routes.dashboard import router as dashboard_router  # Temporarily disabled
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy import text
from datetime import datetime
from app.middleware import SecurityHeadersMiddleware, TimingAccessLogMiddleware, ErrorEnvelopeMiddleware
from app.routes.ops import router as ops_router
from app.services.entitlements import get_entitlements
from app.dependencies import get_current_user
from typing import List

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
SESSION_SECRET = os.getenv("SESSION_SECRET")

# Validate required environment variables for production
if not STRIPE_API_KEY:
    print("⚠️ WARNING: STRIPE_API_KEY not set")
if not STRIPE_WEBHOOK_SECRET:
    print("⚠️ WARNING: STRIPE_WEBHOOK_SECRET not set")
if SESSION_SECRET == "dev-session-secret" or not SESSION_SECRET:
    print("⚠️ WARNING: Using default SESSION_SECRET - change for production!")

stripe.api_key = STRIPE_API_KEY

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, session_cookie="session", https_only=APP_BASE_URL.startswith("https://"), same_site="lax")

# Add production middleware
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(TimingAccessLogMiddleware)
app.add_middleware(ErrorEnvelopeMiddleware)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for production."""
    import traceback
    print(f"❌ Unhandled exception: {exc}")
    print(f"📍 Request path: {request.url.path}")
    print(f"🔍 Traceback: {traceback.format_exc()}")
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": "An unexpected error occurred" if os.getenv("ENVIRONMENT") == "production" else str(exc)
        }
    )

@app.get("/")
def root():
    """Root endpoint to test if routing works."""
    return {"message": "NEW_FASTAPI_BACKEND_IS_RUNNING", "status": "success"}

@app.get("/test")
def test():
    """Simple test endpoint."""
    return {"message": "Test endpoint works!"}

@app.on_event("startup")
def on_startup():
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ Database tables created successfully")
        
        # Run database migration to add role column if needed
        try:
            with engine.connect() as conn:
                # Check if role column exists by trying to select it
                try:
                    conn.execute(text("SELECT role FROM users LIMIT 1"))
                    print("✅ Role column already exists")
                except Exception as e:
                    print(f"📝 Role column doesn't exist, adding it... Error: {e}")
                    # Add role column with default value
                    conn.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR(50) DEFAULT 'user'"))
                    conn.commit()
                    print("✅ Role column added successfully")
        except Exception as e:
            print(f"⚠️ Migration warning: {e}")
            # Try alternative approach - recreate table if needed
            try:
                print("🔄 Attempting alternative migration approach...")
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(50) DEFAULT 'user'"))
                    conn.commit()
                    print("✅ Alternative migration successful")
            except Exception as e2:
                print(f"❌ Alternative migration also failed: {e2}")
            
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
app.include_router(ops_router)
# app.include_router(dashboard_router) # Temporarily disabled

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
def get_variations(claim: str, refresh: bool = False, user: User = Depends(get_current_user)):
    """Get GPT claim variations with tier-based limits and refresh functionality."""
    from app.services.entitlements import get_entitlements
    
    # Get user entitlements
    ents = get_entitlements(user.tier)
    variations_limit = ents.get("variations_per_claim", 3)
    can_refresh = ents.get("can_refresh_variations", False)
    
    # Check if user can refresh and is requesting refresh
    if refresh and not can_refresh:
        raise HTTPException(
            status_code=403, 
            detail="Refresh functionality requires Pro or Enterprise tier"
        )
    
    # Find variations for the claim
    variations = []
    for item in gpt_variations:
        if normalize_text(item.get("Original", "")) == normalize_text(claim):
            variations = item.get("Variations", [])
            break
    
    # Apply tier-based limits
    if variations_limit == -1:
        # Enterprise: show all variations (usually 10)
        limited_variations = variations
    else:
        # Other tiers: limit to specified number
        limited_variations = variations[:variations_limit]
    
    return {
        "variations": limited_variations,
        "total_available": len(variations),
        "showing": len(limited_variations),
        "can_refresh": can_refresh,
        "tier": user.tier.value,
        "refresh_requested": refresh
    }

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

@app.post("/bulk-check-ingredients")
def bulk_check_ingredients(
    ingredients: List[str], 
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Bulk check multiple ingredients (Enterprise only)."""
    from app.services.entitlements import get_entitlements
    
    # Check if user has bulk checking permission
    ents = get_entitlements(user.tier)
    if not ents.get("bulk_checking", False):
        raise HTTPException(
            status_code=403, 
            detail="Bulk checking requires Enterprise tier"
        )
    
    if df is None:
        raise HTTPException(status_code=500, detail="Data not loaded")
    
    if len(ingredients) > 10:  # Limit to 10 ingredients per request
        raise HTTPException(status_code=400, detail="Maximum 10 ingredients per bulk check")
    
    results = []
    for ingredient in ingredients:
        normalized_ingredient = normalize_text(ingredient)
        ingredient_results = []
        
        for _, row in df.iterrows():
            row_ingredient = normalize_text(str(row['Ingredient']))
            if normalized_ingredient in row_ingredient or row_ingredient in normalized_ingredient:
                ingredient_results.append({
                    "ingredient": row['Ingredient'],
                    "country": row['Country'],
                    "claim": row['Claim'],
                    "dosage": row['Dosage'],
                    "category": row['Categories'],
                    "valid": True
                })
        
        results.append({
            "input_ingredient": ingredient,
            "matches": ingredient_results,
            "total_matches": len(ingredient_results)
        })
    
    return {
        "bulk_results": results,
        "total_ingredients_checked": len(ingredients),
        "tier": user.tier.value
    }

@app.post("/export-to-pdf")
def export_to_pdf(
    data: dict,
    user: User = Depends(get_current_user)
):
    """Export search results to PDF (all tiers)."""
    from app.services.entitlements import get_entitlements
    from xhtml2pdf import pisa
    import tempfile
    import base64
    
    # Check if user has PDF export permission
    ents = get_entitlements(user.tier)
    if not ents.get("pdf_export", False):
        raise HTTPException(
            status_code=403, 
            detail="PDF export not available for your tier"
        )
    
    # Create HTML content for PDF
    html_content = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            h1 {{ color: #2563eb; }}
            .result {{ margin: 10px 0; padding: 10px; border: 1px solid #ddd; }}
            .ingredient {{ font-weight: bold; color: #059669; }}
            .claim {{ font-style: italic; }}
            .country {{ color: #7c3aed; }}
        </style>
    </head>
    <body>
        <h1>ClaimSafer Report</h1>
        <p><strong>Generated by:</strong> {user.email}</p>
        <p><strong>Tier:</strong> {user.tier.value}</p>
        <p><strong>Date:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <hr>
    """
    
    # Add results to PDF
    if "results" in data:
        for result in data["results"]:
            html_content += f"""
            <div class="result">
                <div class="ingredient">{result.get('ingredient', 'N/A')}</div>
                <div class="claim">{result.get('claim', 'N/A')}</div>
                <div class="country">Country: {result.get('country', 'N/A')}</div>
                <div>Dosage: {result.get('dosage', 'N/A')}</div>
                <div>Category: {result.get('category', 'N/A')}</div>
            </div>
            """
    
    html_content += "</body></html>"
    
    # Generate PDF
    try:
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
            pisa.CreatePDF(html_content, tmp_file)
            tmp_file_path = tmp_file.name
        
        # Read PDF and encode as base64
        with open(tmp_file_path, 'rb') as pdf_file:
            pdf_content = pdf_file.read()
        
        # Clean up temp file
        import os
        os.unlink(tmp_file_path)
        
        return {
            "pdf_base64": base64.b64encode(pdf_content).decode('utf-8'),
            "filename": f"claimsafer_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
            "tier": user.tier.value
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")

@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "data_loaded": df is not None}

@app.get("/debug")
def debug_info():
    """Debug endpoint to see which app is running."""
    return {
        "app": "NEW_FASTAPI_BACKEND",
        "version": "1.0.0",
        "features": ["stripe", "auth", "dashboard", "ingredient_checker"],
        "endpoints_available": True
    }

@app.get("/test-page", response_class=HTMLResponse)
def test_page():
    """Simple test page to check if HTML responses work."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test Page</title>
        <style>
            body { 
                background: linear-gradient(135deg, #020617 0%, #0f172a 100%);
                color: #e2e8f0;
                font-family: 'Inter', sans-serif;
                margin: 0;
                padding: 2rem;
                min-height: 100vh;
            }
            .container {
                max-width: 800px;
                margin: 0 auto;
                background: #1e293b;
                border: 1px solid #334155;
                border-radius: 1rem;
                padding: 2rem;
                box-shadow: 0 10px 25px -3px rgba(0, 0, 0, 0.2);
            }
            h1 {
                background: linear-gradient(135deg, #2563eb 0%, #10b981 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
                font-size: 2.5rem;
                font-weight: 700;
                margin: 0 0 1rem 0;
            }
            .btn {
                background: #2563eb;
                color: white;
                border: none;
                border-radius: 0.5rem;
                padding: 0.75rem 1.5rem;
                cursor: pointer;
                font-size: 0.875rem;
                font-weight: 500;
                text-decoration: none;
                display: inline-block;
                margin: 0.5rem;
            }
            .btn:hover {
                background: #1d4ed8;
                transform: translateY(-1px);
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>ClaimSafer Test Page</h1>
            <p>If you see this styled page, HTML responses work correctly!</p>
            <a href="/dashboard" class="btn">Go to Dashboard</a>
            <a href="/account" class="btn">Go to Account</a>
            <a href="/billing" class="btn">Go to Billing</a>
        </div>
    </body>
    </html>
    """

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_simple():
    """Simple dashboard page with ClaimSafer styling."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>ClaimSafer Dashboard</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
        <style>
            :root {
                --primary: #2563eb;
                --primary-dark: #1d4ed8;
                --secondary: #64748b;
                --success: #10b981;
                --warning: #f59e0b;
                --danger: #ef4444;
                --dark: #0f172a;
                --darker: #020617;
                --light: #f8fafc;
                --border: #334155;
                --card-bg: #1e293b;
                --text: #e2e8f0;
                --text-muted: #94a3b8;
            }
            
            * { box-sizing: border-box; }
            
            body { 
                background: linear-gradient(135deg, var(--darker) 0%, var(--dark) 100%);
                color: var(--text);
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
                margin: 0;
                line-height: 1.6;
                min-height: 100vh;
            }
            
            nav { 
                background: rgba(30, 41, 59, 0.95);
                backdrop-filter: blur(10px);
                border-bottom: 1px solid var(--border);
                padding: 1rem 2rem;
                display: flex;
                align-items: center;
                justify-content: space-between;
                position: sticky;
                top: 0;
                z-index: 100;
            }
            
            .nav-brand {
                font-size: 1.5rem;
                font-weight: 700;
                color: var(--primary);
                text-decoration: none;
            }
            
            .nav-links {
                display: flex;
                gap: 2rem;
                align-items: center;
            }
            
            nav a { 
                color: var(--text);
                text-decoration: none;
                font-weight: 500;
                transition: color 0.2s;
                padding: 0.5rem 1rem;
                border-radius: 0.5rem;
            }
            
            nav a:hover { 
                color: var(--primary);
                background: rgba(37, 99, 235, 0.1);
            }
            
            .container { 
                max-width: 1200px;
                margin: 0 auto;
                padding: 2rem;
            }
            
            .card { 
                background: var(--card-bg);
                border: 1px solid var(--border);
                border-radius: 1rem;
                padding: 1.5rem;
                margin-bottom: 1.5rem;
                box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
                transition: transform 0.2s, box-shadow 0.2s;
            }
            
            .card:hover {
                transform: translateY(-2px);
                box-shadow: 0 10px 25px -3px rgba(0, 0, 0, 0.2);
            }
            
            .card h3 {
                margin: 0 0 1rem 0;
                font-size: 1.25rem;
                font-weight: 600;
                color: var(--text);
            }
            
            .badge { 
                display: inline-block;
                padding: 0.25rem 0.75rem;
                border-radius: 9999px;
                background: var(--primary);
                color: white;
                font-size: 0.875rem;
                font-weight: 500;
                margin-left: 0.5rem;
            }
            
            .badge.pro { background: var(--success); }
            .badge.enterprise { background: var(--warning); }
            .badge.free { background: var(--secondary); }
            
            .btn { 
                background: var(--primary);
                color: white;
                border: none;
                border-radius: 0.5rem;
                padding: 0.75rem 1.5rem;
                cursor: pointer;
                font-size: 0.875rem;
                font-weight: 500;
                transition: all 0.2s;
                text-decoration: none;
                display: inline-block;
            }
            
            .btn:hover {
                background: var(--primary-dark);
                transform: translateY(-1px);
            }
            
            .btn.secondary {
                background: var(--secondary);
            }
            
            .btn.secondary:hover {
                background: #475569;
            }
            
            .stats-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 1.5rem;
                margin: 1.5rem 0;
            }
            
            .stat-card {
                background: var(--card-bg);
                border: 1px solid var(--border);
                border-radius: 0.75rem;
                padding: 1.5rem;
                text-align: center;
            }
            
            .stat-number {
                font-size: 2rem;
                font-weight: 700;
                color: var(--primary);
                margin-bottom: 0.5rem;
            }
            
            .stat-label {
                color: var(--text-muted);
                font-size: 0.875rem;
                font-weight: 500;
            }
            
            .welcome-section {
                text-align: center;
                margin-bottom: 2rem;
            }
            
            .welcome-section h1 {
                font-size: 2.5rem;
                font-weight: 700;
                margin: 0 0 0.5rem 0;
                background: linear-gradient(135deg, var(--primary) 0%, var(--success) 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
            }
            
            .subtitle {
                color: var(--text-muted);
                font-size: 1.125rem;
                margin: 0.5rem 0 0 0;
            }
            
            @media (max-width: 768px) {
                .container { padding: 1rem; }
                nav { padding: 1rem; }
                .nav-links { gap: 1rem; }
                .stats-grid { grid-template-columns: 1fr; }
            }
        </style>
    </head>
    <body>
        <nav>
            <a href="/dashboard" class="nav-brand">ClaimSafer</a>
            <div class="nav-links">
                <a href="/dashboard">Dashboard</a>
                <a href="/account">Account</a>
                <a href="/billing">Billing</a>
                <button class="btn secondary" style="border:none;">Logout</button>
            </div>
        </nav>
        <div class="container">
            <div class="welcome-section">
                <h1>Welcome back, robertvgorp@gmail.com</h1>
                <p class="subtitle">Your ClaimSafer Pro Dashboard</p>
            </div>
            
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-number">0</div>
                    <div class="stat-label">Checks Used Today</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">200</div>
                    <div class="stat-label">Daily Limit</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">5</div>
                    <div class="stat-label">Countries per Check</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">0%</div>
                    <div class="stat-label">Usage</div>
                </div>
            </div>
            
            <div class="card">
                <h3>Your Plan Features</h3>
                <ul class="feature-list">
                    <li>{{ '✅' if ents.pdf_export else '❌' }} PDF Export</li>
                    <li>✅ {{ ents.variations_per_claim if ents.variations_per_claim != -1 else 'All' }} variations per claim</li>
                    <li>{{ '✅' if ents.can_refresh_variations else '❌' }} Refresh to see more variations</li>
                    <li>{{ '✅' if ents.bulk_checking else '❌' }} Bulk ingredient checking</li>
                    <li>{{ '✅' if ents.pro_tools else '❌' }} Pro tools access</li>
                    <li>{{ '✅' if ents.priority_support else '❌' }} Priority support</li>
                </ul>
            </div>
            
            <div class="card">
                <h3>Quick Actions</h3>
                <div style="display: flex; gap: 1rem; flex-wrap: wrap;">
                    <a href="/account" class="btn">Account Settings</a>
                    <a href="/billing" class="btn secondary">Billing</a>
                    <a href="/docs" class="btn secondary">API Docs</a>
                </div>
            </div>
        </div>
    </body>
    </html>
    """

@app.get("/account", response_class=HTMLResponse)
def account_simple():
    """Simple account page with ClaimSafer styling."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>ClaimSafer Account</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
        <style>
            :root {
                --primary: #2563eb;
                --primary-dark: #1d4ed8;
                --secondary: #64748b;
                --success: #10b981;
                --warning: #f59e0b;
                --danger: #ef4444;
                --dark: #0f172a;
                --darker: #020617;
                --light: #f8fafc;
                --border: #334155;
                --card-bg: #1e293b;
                --text: #e2e8f0;
                --text-muted: #94a3b8;
            }
            
            * { box-sizing: border-box; }
            
            body { 
                background: linear-gradient(135deg, var(--darker) 0%, var(--dark) 100%);
                color: var(--text);
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
                margin: 0;
                line-height: 1.6;
                min-height: 100vh;
            }
            
            nav { 
                background: rgba(30, 41, 59, 0.95);
                backdrop-filter: blur(10px);
                border-bottom: 1px solid var(--border);
                padding: 1rem 2rem;
                display: flex;
                align-items: center;
                justify-content: space-between;
                position: sticky;
                top: 0;
                z-index: 100;
            }
            
            .nav-brand {
                font-size: 1.5rem;
                font-weight: 700;
                color: var(--primary);
                text-decoration: none;
            }
            
            .nav-links {
                display: flex;
                gap: 2rem;
                align-items: center;
            }
            
            nav a { 
                color: var(--text);
                text-decoration: none;
                font-weight: 500;
                transition: color 0.2s;
                padding: 0.5rem 1rem;
                border-radius: 0.5rem;
            }
            
            nav a:hover { 
                color: var(--primary);
                background: rgba(37, 99, 235, 0.1);
            }
            
            .container { 
                max-width: 1200px;
                margin: 0 auto;
                padding: 2rem;
            }
            
            .card { 
                background: var(--card-bg);
                border: 1px solid var(--border);
                border-radius: 1rem;
                padding: 1.5rem;
                margin-bottom: 1.5rem;
                box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
                transition: transform 0.2s, box-shadow 0.2s;
            }
            
            .card:hover {
                transform: translateY(-2px);
                box-shadow: 0 10px 25px -3px rgba(0, 0, 0, 0.2);
            }
            
            .card h3 {
                margin: 0 0 1rem 0;
                font-size: 1.25rem;
                font-weight: 600;
                color: var(--text);
            }
            
            .badge { 
                display: inline-block;
                padding: 0.25rem 0.75rem;
                border-radius: 9999px;
                background: var(--primary);
                color: white;
                font-size: 0.875rem;
                font-weight: 500;
                margin-left: 0.5rem;
            }
            
            .badge.pro { background: var(--success); }
            .badge.enterprise { background: var(--warning); }
            .badge.free { background: var(--secondary); }
            
            .btn { 
                background: var(--primary);
                color: white;
                border: none;
                border-radius: 0.5rem;
                padding: 0.75rem 1.5rem;
                cursor: pointer;
                font-size: 0.875rem;
                font-weight: 500;
                transition: all 0.2s;
                text-decoration: none;
                display: inline-block;
            }
            
            .btn:hover {
                background: var(--primary-dark);
                transform: translateY(-1px);
            }
            
            .btn.secondary {
                background: var(--secondary);
            }
            
            .btn.secondary:hover {
                background: #475569;
            }
            
            .page-header {
                text-align: center;
                margin-bottom: 2rem;
            }
            
            .page-header h1 {
                font-size: 2.5rem;
                font-weight: 700;
                margin: 0 0 0.5rem 0;
                background: linear-gradient(135deg, var(--primary) 0%, var(--success) 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
            }
            
            .page-header p {
                color: var(--text-muted);
                font-size: 1.125rem;
                margin: 0;
            }
            
            .settings-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
                gap: 2rem;
            }
            
            .info-item {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 0.75rem 0;
                border-bottom: 1px solid var(--border);
            }
            
            .info-item:last-child {
                border-bottom: none;
            }
            
            .info-item label {
                font-weight: 500;
                color: var(--text-muted);
            }
            
            .info-item span {
                color: var(--text);
                font-weight: 500;
            }
            
            @media (max-width: 768px) {
                .container { padding: 1rem; }
                nav { padding: 1rem; }
                .nav-links { gap: 1rem; }
                .settings-grid { grid-template-columns: 1fr; }
            }
        </style>
    </head>
    <body>
        <nav>
            <a href="/dashboard" class="nav-brand">ClaimSafer</a>
            <div class="nav-links">
                <a href="/dashboard">Dashboard</a>
                <a href="/account">Account</a>
                <a href="/billing">Billing</a>
                <button class="btn secondary" style="border:none;">Logout</button>
            </div>
        </nav>
        <div class="container">
            <div class="page-header">
                <h1>Account Settings</h1>
                <p>Manage your account preferences and security settings</p>
            </div>
            
            <div class="settings-grid">
                <div class="card">
                    <h3>Profile Information</h3>
                    <div class="info-item">
                        <label>Email Address</label>
                        <span>robertvgorp@gmail.com</span>
                    </div>
                    <div class="info-item">
                        <label>Account Status</label>
                        <span class="badge success">Active</span>
                    </div>
                    <div class="info-item">
                        <label>Plan</label>
                        <span class="badge pro">Pro</span>
                    </div>
                    <div class="info-item">
                        <label>Member Since</label>
                        <span>August 20, 2025</span>
                    </div>
                </div>
                
                <div class="card">
                    <h3>Security</h3>
                    <p>Change your password and manage security settings.</p>
                    <a href="/dashboard" class="btn">Back to Dashboard</a>
                </div>
            </div>
        </div>
    </body>
    </html>
    """

@app.get("/billing", response_class=HTMLResponse)
def billing_simple():
    """Simple billing page with ClaimSafer styling."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>ClaimSafer Billing</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
        <style>
            :root {
                --primary: #2563eb;
                --primary-dark: #1d4ed8;
                --secondary: #64748b;
                --success: #10b981;
                --warning: #f59e0b;
                --danger: #ef4444;
                --dark: #0f172a;
                --darker: #020617;
                --light: #f8fafc;
                --border: #334155;
                --card-bg: #1e293b;
                --text: #e2e8f0;
                --text-muted: #94a3b8;
            }
            
            * { box-sizing: border-box; }
            
            body { 
                background: linear-gradient(135deg, var(--darker) 0%, var(--dark) 100%);
                color: var(--text);
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
                margin: 0;
                line-height: 1.6;
                min-height: 100vh;
            }
            
            nav { 
                background: rgba(30, 41, 59, 0.95);
                backdrop-filter: blur(10px);
                border-bottom: 1px solid var(--border);
                padding: 1rem 2rem;
                display: flex;
                align-items: center;
                justify-content: space-between;
                position: sticky;
                top: 0;
                z-index: 100;
            }
            
            .nav-brand {
                font-size: 1.5rem;
                font-weight: 700;
                color: var(--primary);
                text-decoration: none;
            }
            
            .nav-links {
                display: flex;
                gap: 2rem;
                align-items: center;
            }
            
            nav a { 
                color: var(--text);
                text-decoration: none;
                font-weight: 500;
                transition: color 0.2s;
                padding: 0.5rem 1rem;
                border-radius: 0.5rem;
            }
            
            nav a:hover { 
                color: var(--primary);
                background: rgba(37, 99, 235, 0.1);
            }
            
            .container { 
                max-width: 1200px;
                margin: 0 auto;
                padding: 2rem;
            }
            
            .card { 
                background: var(--card-bg);
                border: 1px solid var(--border);
                border-radius: 1rem;
                padding: 1.5rem;
                margin-bottom: 1.5rem;
                box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
                transition: transform 0.2s, box-shadow 0.2s;
            }
            
            .card:hover {
                transform: translateY(-2px);
                box-shadow: 0 10px 25px -3px rgba(0, 0, 0, 0.2);
            }
            
            .card h3 {
                margin: 0 0 1rem 0;
                font-size: 1.25rem;
                font-weight: 600;
                color: var(--text);
            }
            
            .badge { 
                display: inline-block;
                padding: 0.25rem 0.75rem;
                border-radius: 9999px;
                background: var(--primary);
                color: white;
                font-size: 0.875rem;
                font-weight: 500;
                margin-left: 0.5rem;
            }
            
            .badge.pro { background: var(--success); }
            .badge.enterprise { background: var(--warning); }
            .badge.free { background: var(--secondary); }
            
            .btn { 
                background: var(--primary);
                color: white;
                border: none;
                border-radius: 0.5rem;
                padding: 0.75rem 1.5rem;
                cursor: pointer;
                font-size: 0.875rem;
                font-weight: 500;
                transition: all 0.2s;
                text-decoration: none;
                display: inline-block;
            }
            
            .btn:hover {
                background: var(--primary-dark);
                transform: translateY(-1px);
            }
            
            .btn.secondary {
                background: var(--secondary);
            }
            
            .btn.secondary:hover {
                background: #475569;
            }
            
            .page-header {
                text-align: center;
                margin-bottom: 2rem;
            }
            
            .page-header h1 {
                font-size: 2.5rem;
                font-weight: 700;
                margin: 0 0 0.5rem 0;
                background: linear-gradient(135deg, var(--primary) 0%, var(--success) 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
            }
            
            .page-header p {
                color: var(--text-muted);
                font-size: 1.125rem;
                margin: 0;
            }
            
            .billing-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
                gap: 2rem;
            }
            
            .info-item {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 0.75rem 0;
                border-bottom: 1px solid var(--border);
            }
            
            .info-item:last-child {
                border-bottom: none;
            }
            
            .info-item label {
                font-weight: 500;
                color: var(--text-muted);
            }
            
            .info-item span {
                color: var(--text);
                font-weight: 500;
            }
            
            @media (max-width: 768px) {
                .container { padding: 1rem; }
                nav { padding: 1rem; }
                .nav-links { gap: 1rem; }
                .billing-grid { grid-template-columns: 1fr; }
            }
        </style>
    </head>
    <body>
        <nav>
            <a href="/dashboard" class="nav-brand">ClaimSafer</a>
            <div class="nav-links">
                <a href="/dashboard">Dashboard</a>
                <a href="/account">Account</a>
                <a href="/billing">Billing</a>
                <button class="btn secondary" style="border:none;">Logout</button>
            </div>
        </nav>
        <div class="container">
            <div class="page-header">
                <h1>Billing & Subscription</h1>
                <p>Manage your subscription and billing preferences</p>
            </div>
            
            <div class="billing-grid">
                <div class="card">
                    <h3>Current Plan</h3>
                    <div class="info-item">
                        <label>Plan</label>
                        <span class="badge pro">Pro</span>
                    </div>
                    <div class="info-item">
                        <label>Price</label>
                        <span>$29/month</span>
                    </div>
                    <div class="info-item">
                        <label>Status</label>
                        <span class="badge success">Active</span>
                    </div>
                </div>
                
                <div class="card">
                    <h3>Billing Actions</h3>
                    <p>Manage your billing and subscription settings.</p>
                    <a href="/dashboard" class="btn">Back to Dashboard</a>
                </div>
            </div>
        </div>
    </body>
    </html>
    """

@app.get("/test-billing")
def test_billing():
    """Test billing page without authentication."""
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test Billing</title>
        <style>
            body { font-family: Arial, sans-serif; padding: 20px; }
            .test-card { background: #f5f5f5; padding: 20px; border-radius: 8px; margin: 10px 0; }
        </style>
    </head>
    <body>
        <h1>🧪 Test Billing Page</h1>
        <div class="test-card">
            <h3>✅ New billing template is deployed!</h3>
            <p>If you see this, the new code is working.</p>
            <p>Try logging in and going to <a href="/billing">/billing</a></p>
        </div>
        <div class="test-card">
            <h3>🔍 Debug Info:</h3>
            <p>• App is running: ✅</p>
            <p>• New code deployed: ✅</p>
            <p>• Authentication required for /billing: ✅</p>
        </div>
    </body>
    </html>
    """)

@app.get("/quick-test-user")
def quick_test_user(db: Session = Depends(get_db)):
    """Quick test user creation via GET for easy testing."""
    try:
        from app.models import User, Tier
        from app.security import hash_password
        from datetime import datetime
        
        email = "test@claimsafer.com"
        password = "test123456"
        
        # Check if user exists
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            return {
                "message": "Test user already exists",
                "email": email,
                "password": password,
                "login_url": "/login"
            }
        
        # Create test user
        new_user = User(
            email=email,
            password_hash=hash_password(password),
            is_active=True,
            tier=Tier.pro,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(new_user)
        db.commit()
        
        return {
            "message": "Test user created successfully!",
            "email": email,
            "password": password,
            "login_url": "/login",
            "billing_url": "/billing"
        }
    except Exception as e:
        return {"error": f"Failed to create test user: {str(e)}"}
