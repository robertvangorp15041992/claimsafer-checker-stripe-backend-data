import os
from fastapi import HTTPException, Depends
from app.services.entitlements import get_entitlements
from app.services.usage import get_or_create_today_counter, increment_daily_checks, remaining_daily_checks
from app.dependencies import get_current_user
from app.models import User
from sqlalchemy.orm import Session
from app.db import get_db

UPGRADE_URL = os.getenv("UPGRADE_URL", "https://claimsafer.com/pricing")

class LimitError(HTTPException):
    def __init__(self, detail, code, plan, limit, remaining, upgrade_url=UPGRADE_URL):
        super().__init__(
            status_code=402 if code in ("UPGRADE_REQUIRED", "DAILY_LIMIT_EXCEEDED", "COUNTRIES_LIMIT_EXCEEDED") else 403,
            detail={
                "detail": detail,
                "code": code,
                "plan": plan,
                "limit": limit,
                "remaining": remaining,
                "upgrade_url": upgrade_url,
            }
        )

def load_entitlements(user: User) -> dict:
    return get_entitlements(user.tier)

def require_capability(flag: str):
    def dep(user: User = Depends(get_current_user)):
        ents = load_entitlements(user)
        if not ents.get(flag, False):
            raise LimitError(
                detail=f"Feature '{flag}' requires upgrade.",
                code="UPGRADE_REQUIRED",
                plan=user.tier.value,
                limit=None,
                remaining=None,
            )
        return user
    return dep

def enforce_countries_limit(countries: list[str], entitlements: dict, user: User = None):
    max_countries = entitlements.get("countries_per_check", 1)
    if len(countries) > max_countries:
        raise LimitError(
            detail=f"Your plan allows up to {max_countries} countries per check.",
            code="COUNTRIES_LIMIT_EXCEEDED",
            plan=user.tier.value if user else None,
            limit=max_countries,
            remaining=0,
        )

def meter_daily_check(db: Session, user: User, entitlements: dict, amount: int = 1):
    max_checks = entitlements.get("daily_checks", 0)
    if max_checks == -1:
        return  # unlimited
    counter = get_or_create_today_counter(db, user.id)
    remaining = max_checks - counter.daily_checks_used
    if remaining < amount:
        raise LimitError(
            detail="Daily checks limit reached.",
            code="DAILY_LIMIT_EXCEEDED",
            plan=user.tier.value,
            limit=max_checks,
            remaining=max(0, remaining),
        )
    increment_daily_checks(db, user.id, amount)
