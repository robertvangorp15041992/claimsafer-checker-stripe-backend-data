from sqlalchemy.orm import Session
from app.models import User, Tier, MembershipAudit
from app.utils import normalize_email
from sqlalchemy.exc import IntegrityError
from typing import Optional

def get_user_by_email(db: Session, email: str):
    email = normalize_email(email)
    return db.query(User).filter(User.email == email).first()

def create_user(db: Session, email: str, tier: Tier, stripe_customer_id=None, is_active=False):
    email = normalize_email(email)
    user = User(email=email, tier=tier, stripe_customer_id=stripe_customer_id, is_active=is_active)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise
    db.refresh(user)
    return user

def update_user_tier_and_customer(db: Session, user: User, new_tier: Tier, stripe_customer_id: Optional[str] = None):
    user.tier = new_tier
    if stripe_customer_id:
        if not user.stripe_customer_id or user.stripe_customer_id != stripe_customer_id:
            user.stripe_customer_id = stripe_customer_id
    user.updated_at = None  # triggers onupdate=func.now()
    db.commit()
    db.refresh(user)
    return user

def record_membership_audit(db: Session, *, email, stripe_event_id, old_tier, new_tier, stripe_customer_id, reason):
    audit = MembershipAudit(
        email=normalize_email(email),
        stripe_event_id=stripe_event_id,
        old_tier=old_tier,
        new_tier=new_tier,
        stripe_customer_id=stripe_customer_id,
        reason=reason
    )
    db.add(audit)
    db.commit()
    db.refresh(audit)
    return audit

def upsert_user_by_email(db: Session, email: str, tier: Tier, stripe_customer_id=None):
    email = normalize_email(email)
    user = db.query(User).filter(User.email == email).first()
    if user:
        user.tier = tier
        if stripe_customer_id and not user.stripe_customer_id:
            user.stripe_customer_id = stripe_customer_id
        db.commit()
        db.refresh(user)
        return user
    else:
        user = User(email=email, tier=tier, stripe_customer_id=stripe_customer_id)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
