"""
Authentication logic and session management
"""
import bcrypt
from fastapi import HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy import select
from database import database
from models import User
from schemas import UserResponse
from typing import Optional
import os

# Session secret key
SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY", "your-secret-key-change-in-production")

# HTTP Bearer for optional token-based auth
security = HTTPBearer(auto_error=False)

async def get_user_by_email(email: str) -> Optional[User]:
    """Get user by email from database"""
    query = select(User).where(User.email == email)
    result = await database.fetch_one(query)
    return result

async def get_user_by_id(user_id: str) -> Optional[User]:
    """Get user by ID from database"""
    query = select(User).where(User.id == user_id)
    result = await database.fetch_one(query)
    return result

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password using bcrypt"""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

async def authenticate_user(email: str, password: str) -> Optional[User]:
    """Authenticate user with email and password"""
    user = await get_user_by_email(email)
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user

async def get_current_user(request: Request) -> Optional[UserResponse]:
    """Get current user from session"""
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    
    user = await get_user_by_id(user_id)
    if not user:
        return None
    
    return UserResponse(
        id=user.id,
        email=user.email,
        subscription_tier=user.subscription_tier,
        stripe_customer_id=user.stripe_customer_id,
        stripe_subscription_id=user.stripe_subscription_id,
        created_at=user.created_at,
        last_login=user.last_login,
        is_active=user.is_active,
        last_payment_date=user.last_payment_date,
        search_count=user.search_count,
        last_search_date=user.last_search_date
    )

async def get_current_user_required(request: Request) -> UserResponse:
    """Get current user from session, raise exception if not authenticated"""
    user = await get_current_user(request)
    if not user:
        raise HTTPException(
            status_code=401,
            detail={"redirect": True, "url": "/login", "message": "Authentication required"}
        )
    return user

async def get_current_user_optional(request: Request) -> Optional[UserResponse]:
    """Get current user from session, return None if not authenticated"""
    return await get_current_user(request)

# Dependency for route protection
async def require_auth(request: Request) -> UserResponse:
    """Dependency that requires authentication"""
    return await get_current_user_required(request)

# Optional: Token-based auth for future use
async def get_current_user_from_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Optional[UserResponse]:
    """Get current user from JWT token (for future implementation)"""
    if not credentials:
        return None
    
    # TODO: Implement JWT token validation
    # For now, return None to use session-based auth
    return None
