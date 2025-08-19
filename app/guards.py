from fastapi import Depends, HTTPException, status, Request
from .models import Tier, User
from .db import SessionLocal
from .billing import tier_rank
from .utils import normalize_email
from sqlalchemy.orm import Session

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    email = request.headers.get("X-Debug-Email")
    if not email:
        raise HTTPException(status_code=401, detail="Missing X-Debug-Email header")
    email = normalize_email(email)
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

def require_tier(min_tier: Tier):
    def dependency(user: User = Depends(get_current_user)):
        if tier_rank(user.tier) < tier_rank(min_tier):
            raise HTTPException(status_code=403, detail=f"Requires {min_tier.value} tier or higher.")
        return user
    return dependency
