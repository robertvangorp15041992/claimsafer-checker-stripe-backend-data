from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.services.users import get_or_error
from app.services.usage import get_or_create_today_counter, increment_daily_checks, remaining_daily_checks
from app.services.entitlements import get_entitlements
from datetime import datetime

router = APIRouter()

@router.get("/me/usage")
def get_my_usage(x_debug_email: str = Header(None), db: Session = Depends(get_db)):
    if not x_debug_email:
        raise HTTPException(status_code=401, detail="Missing X-Debug-Email header")
    user = get_or_error(db, x_debug_email)
    entitlements = get_entitlements(user.tier)
    counter = get_or_create_today_counter(db, user.id)
    remaining = remaining_daily_checks(db, user, entitlements)
    return {
        "date": datetime.utcnow().date().isoformat(),
        "used": counter.daily_checks_used,
        "remaining": remaining
    }

@router.post("/me/usage/increment")
def increment_my_usage(x_debug_email: str = Header(None), db: Session = Depends(get_db)):
    if not x_debug_email:
        raise HTTPException(status_code=401, detail="Missing X-Debug-Email header")
    user = get_or_error(db, x_debug_email)
    entitlements = get_entitlements(user.tier)
    remaining = remaining_daily_checks(db, user, entitlements)
    if remaining <= 0:
        raise HTTPException(status_code=402, detail="Upgrade required")
    counter = increment_daily_checks(db, user.id, 1)
    remaining = remaining_daily_checks(db, user, entitlements)
    return {
        "date": datetime.utcnow().date().isoformat(),
        "used": counter.daily_checks_used,
        "remaining": remaining
    }
