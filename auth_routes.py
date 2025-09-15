"""
Authentication routes for login and user management
"""
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import update
from datetime import datetime
from database import database
from auth import authenticate_user, get_current_user_required, get_current_user
from schemas import LoginRequest, LoginResponse, UserResponse
from usage import get_usage_stats
from models import User
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])

@router.post("/login", response_model=LoginResponse)
async def login(request: Request, login_data: LoginRequest):
    """User login endpoint"""
    try:
        # Authenticate user
        user = await authenticate_user(login_data.email, login_data.password)
        
        if not user:
            return LoginResponse(
                success=False,
                message="Invalid email or password"
            )
        
        # Check if user is active
        if not user.is_active:
            return LoginResponse(
                success=False,
                message="Account is inactive. Please contact support."
            )
        
        # Update last login timestamp
        query = update(User).where(User.id == user.id).values(
            last_login=datetime.utcnow()
        )
        await database.execute(query)
        
        # Set session
        request.session["user_id"] = str(user.id)
        request.session["email"] = user.email
        request.session["subscription_tier"] = user.subscription_tier
        
        # Create user response
        user_response = UserResponse(
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
        
        logger.info(f"User {user.email} logged in successfully")
        
        return LoginResponse(
            success=True,
            message="Login successful",
            user=user_response
        )
        
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return LoginResponse(
            success=False,
            message="An error occurred during login"
        )

@router.post("/logout")
async def logout(request: Request):
    """User logout endpoint"""
    try:
        # Clear session
        request.session.clear()
        
        return JSONResponse(
            content={"success": True, "message": "Logged out successfully"}
        )
        
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        return JSONResponse(
            content={"success": False, "message": "An error occurred during logout"},
            status_code=500
        )

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(user: UserResponse = Depends(get_current_user_required)):
    """Get current user information"""
    return user

@router.get("/usage")
async def get_user_usage(user: UserResponse = Depends(get_current_user_required)):
    """Get user's usage statistics"""
    try:
        stats = await get_usage_stats(str(user.id))
        return JSONResponse(content=stats)
    except Exception as e:
        logger.error(f"Usage stats error: {str(e)}")
        return JSONResponse(
            content={"error": "Failed to get usage statistics"},
            status_code=500
        )

@router.get("/check")
async def check_auth(request: Request):
    """Check if user is authenticated"""
    user = await get_current_user(request)
    if user:
        return JSONResponse(content={
            "authenticated": True,
            "user": {
                "id": str(user.id),
                "email": user.email,
                "subscription_tier": user.subscription_tier
            }
        })
    else:
        return JSONResponse(content={
            "authenticated": False,
            "redirect": True,
            "url": "/login"
        })
