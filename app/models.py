from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum as SqlEnum, Text, func, Date, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import declarative_base, relationship
from enum import Enum as PyEnum

Base = declarative_base()

class Tier(PyEnum):
    free = "free"
    starter = "starter"
    pro = "pro"
    enterprise = "enterprise"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String(320), unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=True)
    is_active = Column(Boolean, default=False)
    tier = Column(SqlEnum(Tier), default=Tier.free, nullable=False)
    role = Column(String(50), default="user", nullable=False)  # user, admin
    stripe_customer_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    usage_counters = relationship("UsageCounter", back_populates="user")

class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    id = Column(Integer, primary_key=True)
    stripe_event_id = Column(String, unique=True, nullable=False)
    type = Column(String, nullable=False)
    payload = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class UsageCounter(Base):
    __tablename__ = "usage_counters"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    daily_checks_used = Column(Integer, default=0, nullable=False)
    user = relationship("User", back_populates="usage_counters")
    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_user_date"),
    )

class MembershipAudit(Base):
    __tablename__ = "membership_audit"
    id = Column(Integer, primary_key=True)
    email = Column(String(320), index=True, nullable=False)
    stripe_event_id = Column(String, nullable=True)
    old_tier = Column(SqlEnum(Tier), nullable=True)
    new_tier = Column(SqlEnum(Tier), nullable=False)
    stripe_customer_id = Column(String, nullable=True)
    reason = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
