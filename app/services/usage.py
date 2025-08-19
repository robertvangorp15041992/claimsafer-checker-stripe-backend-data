from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from app.models import UsageCounter, User
from sqlalchemy.exc import IntegrityError

def get_or_create_today_counter(db: Session, user_id: int) -> UsageCounter:
    today = datetime.utcnow().date()
    counter = db.query(UsageCounter).filter_by(user_id=user_id, date=today).first()
    if not counter:
        counter = UsageCounter(user_id=user_id, date=today, daily_checks_used=0)
        db.add(counter)
        db.commit()
        db.refresh(counter)
    return counter

def increment_daily_checks(db: Session, user_id: int, amount: int = 1) -> UsageCounter:
    counter = get_or_create_today_counter(db, user_id)
    counter.daily_checks_used += amount
    db.commit()
    db.refresh(counter)
    return counter

def remaining_daily_checks(db: Session, user, entitlements: dict) -> int:
    from math import inf
    max_checks = entitlements.get("daily_checks", 0)
    if max_checks == -1:
        return inf
    counter = get_or_create_today_counter(db, user.id)
    return max_checks - counter.daily_checks_used

def get_usage_for_date(db: Session, date: str, limit=50):
    q = (
        db.query(User.email, User.tier, UsageCounter.daily_checks_used, UsageCounter.date, User.updated_at)
        .join(UsageCounter, User.id == UsageCounter.user_id)
        .filter(UsageCounter.date == date)
        .order_by(UsageCounter.daily_checks_used.desc())
        .limit(limit)
    )
    return [
        {
            "email": row[0],
            "tier": row[1].value if hasattr(row[1], "value") else row[1],
            "daily_checks_used": row[2],
            "date": row[3].isoformat(),
            "updated_at": row[4].isoformat() if row[4] else None,
        }
        for row in q.all()
    ]

def get_user_usage_days(db: Session, user_id: int, days: int):
    today = datetime.utcnow().date()
    usage_map = {
        uc.date: uc.daily_checks_used
        for uc in db.query(UsageCounter).filter(
            UsageCounter.user_id == user_id,
            UsageCounter.date >= today - timedelta(days=days-1)
        )
    }
    return [
        {
            "date": (today - timedelta(days=i)).isoformat(),
            "daily_checks_used": usage_map.get(today - timedelta(days=i), 0)
        }
        for i in range(days)
    ]

def reset_counters_for_date(db: Session, reset_date: date):
    db.query(UsageCounter).filter(UsageCounter.date == reset_date).update({UsageCounter.daily_checks_used: 0})
    db.commit()
