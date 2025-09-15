"""
Pydantic schemas for request/response validation
"""
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime, date
from uuid import UUID

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: UUID
    email: str
    subscription_tier: str
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    created_at: datetime
    last_login: Optional[datetime] = None
    is_active: bool
    last_payment_date: Optional[date] = None
    search_count: Optional[int] = 0
    last_search_date: Optional[date] = None

class LoginResponse(BaseModel):
    success: bool
    message: str
    user: Optional[UserResponse] = None

class UsageResponse(BaseModel):
    allowed: bool
    remaining_searches: Optional[int] = None
    reset_date: Optional[date] = None
    message: str
