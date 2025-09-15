"""
Database models for user management
"""
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Date, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from database import Base
import uuid
import os

class User(Base):
    __tablename__ = "users"
    
    # Use String for SQLite compatibility, UUID for PostgreSQL
    if os.getenv("DATABASE_URL", "").startswith("sqlite"):
        id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    else:
        id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(Text, nullable=False)
    subscription_tier = Column(String(50), default="free")  # 'free', 'early_essentials', 'pro', 'enterprise'
    stripe_customer_id = Column(String(255), nullable=True)
    stripe_subscription_id = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)
    last_payment_date = Column(Date, nullable=True)
    search_count = Column(Integer, default=0)
    last_search_date = Column(Date, nullable=True)
