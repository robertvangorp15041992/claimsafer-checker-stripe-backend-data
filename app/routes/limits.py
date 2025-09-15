from fastapi import APIRouter, Depends, Request, Body, HTTPException
from sqlalchemy.orm import Session
from app.dependencies import get_current_user
from app.gating import load_entitlements, enforce_countries_limit, meter_daily_check, require_capability
from app.services.usage import remaining_daily_checks, get_or_create_today_counter
from app.db import get_db

router = APIRouter()

@router.post("/api/claims/check")
def claims_check(
    request: Request,
    data: dict = Body(...),
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    ents = load_entitlements(user)
    countries = data.get("countries", [])
    enforce_countries_limit(countries, ents, user)
    meter_daily_check(db, user, ents, amount=1)
    counter = get_or_create_today_counter(db, user.id)
    remaining = remaining_daily_checks(db, user, ents)
    return {
        "ok": True,
        "tier": user.tier.value,
        "used": counter.daily_checks_used,
        "remaining": remaining
    }

@router.get("/api/tools/pro-feature")
def pro_feature(user = Depends(require_capability("pro_tools"))):
    try:
        return {"ok": True, "msg": "You have access to pro tools!", "tier": user.tier.value}
    except Exception as e:
        print(f"Error in pro-feature endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
