from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.services.users import get_or_error
from app.services.entitlements import get_entitlements
import os

router = APIRouter()

ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "replace-me")

@router.get("/me/plan")
def get_my_plan(x_debug_email: str = Header(None), db: Session = Depends(get_db)):
    if not x_debug_email:
        raise HTTPException(status_code=401, detail="Missing X-Debug-Email header")
    user = get_or_error(db, x_debug_email)
    entitlements = get_entitlements(user.tier)
    return {"email": user.email, "tier": user.tier.value, "entitlements": entitlements}

@router.get("/admin/users")
def admin_list_users(admin_api_key: str = Header(None), db: Session = Depends(get_db)):
    if admin_api_key != ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")
    users = db.query(get_or_error.__globals__["User"]).all()
    return [{"email": u.email, "tier": u.tier.value, "is_active": u.is_active, "created_at": u.created_at} for u in users]

@router.get("/admin/users/{email}")
def admin_user_detail(email: str, admin_api_key: str = Header(None), db: Session = Depends(get_db)):
    if admin_api_key != ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")
    user = get_or_error(db, email)
    today = __import__('datetime').datetime.utcnow().date()
    usage = db.query(get_or_error.__globals__["UsageCounter"]).filter_by(user_id=user.id, date=today).first()
    return {
        "email": user.email,
        "tier": user.tier.value,
        "is_active": user.is_active,
        "created_at": user.created_at,
        "usage_today": usage.daily_checks_used if usage else 0
    }
