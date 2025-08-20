from app.repository import get_user_by_email, create_user, update_user_tier_and_customer
from app.models import Tier
from app.utils import normalize_email
from fastapi import HTTPException

def find_or_create_by_email(db, email, default_tier=Tier.free, stripe_customer_id=None):
    email = normalize_email(email)
    user = get_user_by_email(db, email)
    if user:
        return user
    return create_user(db, email=email, tier=default_tier, stripe_customer_id=stripe_customer_id)

def set_user_tier(db, email, tier):
    user = get_user_by_email(db, email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return update_user_tier_and_customer(db, user, tier)

def get_or_error(db, email):
    user = get_user_by_email(db, email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
