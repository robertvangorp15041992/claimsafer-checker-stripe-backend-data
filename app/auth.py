import os
from fastapi import APIRouter, Request, Form, Depends, Response, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import PlainTextResponse
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from app.db import get_db
from app.models import User, Tier
from app.utils import normalize_email, send_email
from dotenv import load_dotenv

load_dotenv()

SESSION_SECRET = os.getenv("SESSION_SECRET", "dev-session-secret")
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8000")
ONBOARDING_SECRET = os.getenv("ONBOARDING_SECRET", "dev-onboard-secret")

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# --- Token helpers ---
serializer = URLSafeTimedSerializer(ONBOARDING_SECRET)
def sign_activation_token(email: str) -> str:
    return serializer.dumps(email, salt="onboarding")
def verify_activation_token(token: str, max_age=604800) -> str:
    return serializer.loads(token, salt="onboarding", max_age=max_age)
def sign_magic_token(email: str) -> str:
    return serializer.dumps(email, salt="magic-login")
def verify_magic_token(token: str, max_age=900) -> str:
    return serializer.loads(token, salt="magic-login", max_age=max_age)

# --- Onboarding email (called from webhook service) ---
def send_onboarding_email(email: str, tier: Tier):
    token = sign_activation_token(email)
    link = f"{APP_BASE_URL}/auth/activate?token={token}"
    html = f"""
    <p>Welcome to ClaimSafer!</p>
    <p>Your plan: <b>{tier.value}</b></p>
    <p>To finish signup, <a href='{link}'>activate your account</a> and set your password.</p>
    <p>If you did not sign up, you can ignore this email.</p>
    """
    send_email(email, "ClaimSafer — Activate your account", html)

# --- Activation routes ---
@router.get("/auth/activate", response_class=HTMLResponse)
def activate_form(request: Request, token: str):
    try:
        email = verify_activation_token(token)
    except Exception:
        return HTMLResponse("<h3>Invalid or expired token.</h3>", status_code=400)
    return f"""
    <form method='post' action='/auth/activate'>
        <input type='hidden' name='token' value='{token}' />
        <label>Email: {email}</label><br>
        <input type='password' name='password' placeholder='Set your password' minlength='8' required /><br>
        <button type='submit'>Activate</button>
    </form>
    """

@router.post("/auth/activate")
def activate_post(token: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    try:
        email = verify_activation_token(token)
    except Exception:
        return HTMLResponse("<h3>Invalid or expired token.</h3>", status_code=400)
    user = db.query(User).filter_by(email=normalize_email(email)).first()
    if not user:
        return HTMLResponse("<h3>User not found.</h3>", status_code=404)
    if len(password) < 8:
        return HTMLResponse("<h3>Password must be at least 8 characters.</h3>", status_code=400)
    user.password_hash = generate_password_hash(password)
    user.is_active = True
    db.commit()
    return RedirectResponse("/login", status_code=302)

# --- Login routes ---
@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return """
    <form method='post' action='/login'>
        <input type='email' name='email' placeholder='Email' required /><br>
        <input type='password' name='password' placeholder='Password' minlength='8' required /><br>
        <button type='submit'>Login</button>
    </form>
    """

@router.post("/login")
def login_post(response: Response, email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    email = normalize_email(email)
    user = db.query(User).filter_by(email=email).first()
    if not user or not user.password_hash or not user.is_active:
        return HTMLResponse("<h3>Invalid credentials or inactive account.</h3>", status_code=401)
    if not check_password_hash(user.password_hash, password):
        return HTMLResponse("<h3>Invalid credentials.</h3>", status_code=401)
    # Set session cookie
    response = RedirectResponse("/dashboard", status_code=302)
    response.set_cookie(
        key="session",
        value=serializer.dumps(email, salt="session"),
        httponly=True,
        samesite="lax",
        secure=APP_BASE_URL.startswith("https://"),
    )
    return response

# --- Magic link ---
@router.post("/auth/magic-link")
def magic_link(email: str = Form(...), db: Session = Depends(get_db)):
    email = normalize_email(email)
    user = db.query(User).filter_by(email=email).first()
    if not user or not user.is_active:
        return HTMLResponse("<h3>User not found or not active.</h3>", status_code=404)
    token = sign_magic_token(email)
    link = f"{APP_BASE_URL}/auth/magic-login?token={token}"
    html = f"<p>Click to log in: <a href='{link}'>Magic Login</a></p>"
    send_email(email, "ClaimSafer — Magic Login", html)
    return HTMLResponse("<h3>Magic link sent! Check your email.</h3>")

@router.get("/auth/magic-login")
def magic_login(token: str, response: Response, db: Session = Depends(get_db)):
    try:
        email = verify_magic_token(token)
    except Exception:
        return HTMLResponse("<h3>Invalid or expired magic link.</h3>", status_code=400)
    user = db.query(User).filter_by(email=normalize_email(email)).first()
    if not user or not user.is_active:
        return HTMLResponse("<h3>User not found or not active.</h3>", status_code=404)
    # Set session cookie
    response = RedirectResponse("/dashboard", status_code=302)
    response.set_cookie(
        key="session",
        value=serializer.dumps(email, salt="session"),
        httponly=True,
        samesite="lax",
        secure=APP_BASE_URL.startswith("https://"),
    )
    return response

# --- Session-protected dashboard ---
def get_current_user_from_session(request: Request, db: Session):
    session_cookie = request.cookies.get("session")
    if not session_cookie:
        raise HTTPException(status_code=401, detail="Not logged in")
    try:
        email = serializer.loads(session_cookie, salt="session")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid session")
    user = db.query(User).filter_by(email=normalize_email(email)).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or not active")
    return user

@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_from_session(request, db)
    return f"<h2>Welcome {user.email}, your tier is {user.tier.value}.</h2>"
