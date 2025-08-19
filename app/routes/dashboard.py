from fastapi import APIRouter, Request, Depends, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.dependencies import get_current_user, require_active_user
from app.services.entitlements import get_entitlements
from app.services.usage import remaining_daily_checks, get_or_create_today_counter
from app.utils import normalize_email, send_email
from app.security import generate_csrf_token, validate_csrf, password_strong_enough
from app.db import get_db
from starlette.responses import Response
import os
import stripe
from werkzeug.security import check_password_hash, generate_password_hash
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8000")
UPGRADE_URL = os.getenv("UPGRADE_URL", "https://claimsafer.com/pricing")
STRIPE_PORTAL_RETURN_PATH = os.getenv("STRIPE_PORTAL_RETURN_PATH", "/billing")
STRIPE_API_KEY = os.getenv("STRIPE_API_KEY")
stripe.api_key = STRIPE_API_KEY

# --- Dashboard ---
@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db), user=Depends(require_active_user)):
    ents = get_entitlements(user.tier)
    counter = get_or_create_today_counter(db, user.id)
    remaining = remaining_daily_checks(db, user, ents)
    csrf_token = generate_csrf_token()
    response = templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "ents": ents,
        "used": counter.daily_checks_used,
        "remaining": remaining,
        "csrf_token": csrf_token,
        "upgrade_url": UPGRADE_URL,
    })
    response.set_cookie("csrf_token", csrf_token, httponly=False, samesite="lax")
    return response

# --- Account ---
@router.get("/account", response_class=HTMLResponse)
def account(request: Request, user=Depends(require_active_user)):
    csrf_token = generate_csrf_token()
    response = templates.TemplateResponse("account.html", {
        "request": request,
        "user": user,
        "csrf_token": csrf_token,
    })
    response.set_cookie("csrf_token", csrf_token, httponly=False, samesite="lax")
    return response

@router.post("/account/change-password")
def change_password(request: Request, db: Session = Depends(get_db), user=Depends(require_active_user), current_password: str = Form(...), new_password: str = Form(...)):
    validate_csrf(request)
    if not check_password_hash(user.password_hash, current_password):
        return RedirectResponse("/account?error=badpass", status_code=303)
    if not password_strong_enough(new_password):
        return RedirectResponse("/account?error=weakpass", status_code=303)
    user.password_hash = generate_password_hash(new_password)
    db.commit()
    return RedirectResponse("/account?success=1", status_code=303)

@router.post("/account/request-email-change")
def request_email_change(request: Request, db: Session = Depends(get_db), user=Depends(require_active_user), new_email: str = Form(...)):
    validate_csrf(request)
    # Use existing email change logic (Step 6)
    from app.auth import sign_activation_token
    email = normalize_email(new_email)
    # Send verification (simulate, or call real logic)
    token = sign_activation_token(email)
    link = f"{APP_BASE_URL}/auth/confirm-email-change?token={token}"
    html = f"<p>Click to confirm your new email: <a href='{link}'>Confirm Email</a></p>"
    send_email(email, "ClaimSafer — Confirm your new email", html)
    return RedirectResponse("/account?success=1", status_code=303)

@router.post("/account/magic-link")
def send_magic_link(request: Request, user=Depends(require_active_user)):
    validate_csrf(request)
    from app.auth import sign_magic_token
    token = sign_magic_token(user.email)
    link = f"{APP_BASE_URL}/auth/magic-login?token={token}"
    html = f"<p>Click to log in: <a href='{link}'>Magic Login</a></p>"
    send_email(user.email, "ClaimSafer — Magic Login", html)
    return RedirectResponse("/account?success=1", status_code=303)

# --- Billing ---
@router.get("/billing", response_class=HTMLResponse)
def billing(request: Request, user=Depends(require_active_user)):
    ents = get_entitlements(user.tier)
    csrf_token = generate_csrf_token()
    response = templates.TemplateResponse("billing.html", {
        "request": request,
        "user": user,
        "ents": ents,
        "csrf_token": csrf_token,
        "upgrade_url": UPGRADE_URL,
    })
    response.set_cookie("csrf_token", csrf_token, httponly=False, samesite="lax")
    return response

@router.post("/billing/portal")
def billing_portal(request: Request, user=Depends(require_active_user)):
    validate_csrf(request)
    if not user.stripe_customer_id:
        return RedirectResponse("/billing?error=nocustomer", status_code=303)
    return_url = f"{APP_BASE_URL}{STRIPE_PORTAL_RETURN_PATH}"
    session = stripe.billing_portal.Session.create(
        customer=user.stripe_customer_id,
        return_url=return_url
    )
    return RedirectResponse(session.url, status_code=303)
