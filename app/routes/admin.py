from fastapi import APIRouter, Depends, Query, Request, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
import json

from app.db import get_db
from app.models import User, Tier, UsageCounter, MembershipAudit
from app.services.users import get_user_by_email
from app.services.usage import get_user_usage_days
from app.dependencies import require_role
from app.security import hash_password
from app.repository import create_user
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory="templates")

@router.get("/admin/usage", response_class=HTMLResponse)
def admin_usage(
    request: Request,
    date: str = Query(None),
    db: Session = Depends(get_db),
    admin = Depends(require_role("admin"))
):
    if not date:
        date = datetime.utcnow().date().isoformat()
    rows = get_usage_for_date(db, date)
    return templates.TemplateResponse("admin_usage.html", {
        "request": request,
        "rows": rows,
        "date": date
    })

@router.get("/admin/users/{email}/usage")
def user_usage_history(
    email: str,
    days: int = Query(30, ge=1, le=90),
    db: Session = Depends(get_db),
    admin = Depends(require_role("admin"))
):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return JSONResponse({"detail": "User not found"}, status_code=404)
    usage = get_user_usage_days(db, user.id, days)
    return usage

@router.post("/create-test-user")
def create_test_user(
    email: str = "robertvgorp@gmail.com",
    password: str = "test123456",
    tier: Tier = Tier.pro,
    is_active: bool = True,
    db: Session = Depends(get_db)
):
    """
    Create a test user for development/testing purposes.
    No authentication required for testing.
    """
    try:
        # Check if user already exists
        existing_user = get_user_by_email(db, email)
        if existing_user:
            return {
                "message": "User already exists",
                "user_id": existing_user.id,
                "email": existing_user.email,
                "tier": existing_user.tier.value
            }
        
        # Create new user
        password_hash = hash_password(password)
        new_user = User(
            email=email,
            password_hash=password_hash,
            is_active=is_active,
            tier=tier,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        return {
            "message": "Test user created successfully",
            "user_id": new_user.id,
            "email": new_user.email,
            "tier": new_user.tier.value,
            "is_active": new_user.is_active,
            "created_at": new_user.created_at.isoformat()
        }
    except Exception as e:
        print(f"Error creating test user: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating user: {str(e)}")

@router.post("/create-admin-user")
def create_admin_user(
    email: str = "admin@claimsafer.com",
    password: str = "admin123456",
    db: Session = Depends(get_db)
):
    """
    Create an admin user for development/testing purposes.
    """
    try:
        # Check if user already exists
        existing_user = get_user_by_email(db, email)
        if existing_user:
            return {
                "message": "Admin user already exists",
                "user_id": existing_user.id,
                "email": existing_user.email,
                "tier": existing_user.tier.value
            }
        
        # Create new admin user
        password_hash = hash_password(password)
        new_user = User(
            email=email,
            password_hash=password_hash,
            is_active=True,
            tier=Tier.enterprise,  # Admin gets highest tier
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        return {
            "message": "Admin user created successfully",
            "user_id": new_user.id,
            "email": new_user.email,
            "tier": new_user.tier.value,
            "created_at": new_user.created_at.isoformat()
        }
    except Exception as e:
        print(f"Error creating admin user: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating admin user: {str(e)}")
