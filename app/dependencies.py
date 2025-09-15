from fastapi import Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import User
from app.utils import normalize_email
from typing import Optional


def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Get current user from session or return None if not authenticated."""
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    
    user = db.query(User).filter(User.id == user_id).first()
    return user


def require_active_user(
    current_user: Optional[User] = Depends(get_current_user)
) -> User:
    """Require an active, authenticated user."""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated"
        )
    
    return current_user


def require_role(required_role: str):
    """Require a specific role."""
    def _require_role(
        current_user: User = Depends(require_active_user)
    ) -> User:
        if current_user.role != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{required_role}' required"
            )
        return current_user
    return _require_role


def require_tier(min_tier: str):
    """Require a minimum tier level."""
    def _require_tier(
        current_user: User = Depends(require_active_user)
    ) -> User:
        from app.billing import tier_rank
        
        user_rank = tier_rank(current_user.tier)
        required_rank = tier_rank(min_tier)
        
        if user_rank < required_rank:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Tier '{min_tier}' or higher required"
            )
        return current_user
    return _require_tier
