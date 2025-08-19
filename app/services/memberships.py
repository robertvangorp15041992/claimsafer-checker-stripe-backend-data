from typing import Iterable, Optional
from sqlalchemy.orm import Session
from app.models import Tier, User
from app.repository import (
    get_user_by_email, create_user, update_user_tier_and_customer, record_membership_audit
)
from app.billing import PRICE_TO_TIER, DEFAULT_TIER, tier_rank
from app.utils import normalize_email

def decide_tier_from_prices(price_ids: Iterable[str]) -> Tier:
    """Return highest Tier found in price_ids; if none match, return DEFAULT_TIER."""
    found = [PRICE_TO_TIER[pid] for pid in price_ids if pid in PRICE_TO_TIER]
    if not found:
        return DEFAULT_TIER
    return max(found, key=tier_rank)

def upsert_membership_from_checkout(
    db: Session,
    *,
    email: str,
    stripe_customer_id: Optional[str],
    line_item_price_ids: Iterable[str],
    stripe_event_id: Optional[str],
    reason: str = "checkout.session.completed",
) -> User:
    email = normalize_email(email)
    user = get_user_by_email(db, email)
    new_tier = decide_tier_from_prices(line_item_price_ids)
    old_tier = user.tier if user else None
    if not user:
        user = create_user(db, email, new_tier, stripe_customer_id=stripe_customer_id, is_active=False)
    else:
        if tier_rank(new_tier) != tier_rank(user.tier):
            update_user_tier_and_customer(db, user, new_tier, stripe_customer_id)
        elif stripe_customer_id and not user.stripe_customer_id:
            update_user_tier_and_customer(db, user, user.tier, stripe_customer_id)
    record_membership_audit(
        db,
        email=email,
        stripe_event_id=stripe_event_id,
        old_tier=old_tier,
        new_tier=new_tier,
        stripe_customer_id=stripe_customer_id,
        reason=reason,
    )
    return user

def upsert_membership_from_subscription(
    db: Session,
    *,
    email: str,
    stripe_customer_id: Optional[str],
    active_subscription_price_ids: Iterable[str],
    stripe_event_id: Optional[str],
    reason: str = "subscription.updated",
) -> User:
    email = normalize_email(email)
    user = get_user_by_email(db, email)
    new_tier = decide_tier_from_prices(active_subscription_price_ids) if active_subscription_price_ids else Tier.free
    old_tier = user.tier if user else None
    if not user:
        user = create_user(db, email, new_tier, stripe_customer_id=stripe_customer_id, is_active=False)
    else:
        if tier_rank(new_tier) != tier_rank(user.tier):
            update_user_tier_and_customer(db, user, new_tier, stripe_customer_id)
        elif stripe_customer_id and not user.stripe_customer_id:
            update_user_tier_and_customer(db, user, user.tier, stripe_customer_id)
    record_membership_audit(
        db,
        email=email,
        stripe_event_id=stripe_event_id,
        old_tier=old_tier,
        new_tier=new_tier,
        stripe_customer_id=stripe_customer_id,
        reason=reason,
    )
    return user
