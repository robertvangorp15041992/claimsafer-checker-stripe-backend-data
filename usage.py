"""
Usage tracking and limits management
"""
from datetime import datetime, date, timedelta
from sqlalchemy import select, update
from database import database
from models import User
from schemas import UsageResponse
from typing import Tuple
import logging

logger = logging.getLogger(__name__)

async def check_and_update_usage(user_id: str) -> Tuple[bool, UsageResponse]:
    """
    Check if user can perform a search and update usage count
    Returns: (allowed: bool, usage_info: UsageResponse)
    """
    # Get user from database
    query = select(User).where(User.id == user_id)
    user = await database.fetch_one(query)
    
    if not user:
        return False, UsageResponse(
            allowed=False,
            message="User not found"
        )
    
    # Check if user is active
    if not user.is_active:
        return False, UsageResponse(
            allowed=False,
            message="Account is inactive"
        )
    
    # Check subscription tier
    if user.subscription_tier in ['starter', 'pro']:
        # No limits for paid tiers
        await increment_search_count(user_id)
        return True, UsageResponse(
            allowed=True,
            message="Unlimited searches available"
        )
    
    # Free tier: check 7-day limit
    if user.subscription_tier == 'free':
        return await check_free_tier_usage(user_id, user)
    
    # Unknown tier
    return False, UsageResponse(
        allowed=False,
        message="Invalid subscription tier"
    )

async def check_free_tier_usage(user_id: str, user: User) -> Tuple[bool, UsageResponse]:
    """Check usage limits for free tier users"""
    today = date.today()
    last_search = user.last_search_date
    
    # If no previous searches, allow
    if not last_search:
        await increment_search_count(user_id)
        return True, UsageResponse(
            allowed=True,
            remaining_searches=2,  # 3 total - 1 used
            message="First search of the week"
        )
    
    # Check if 7 days have passed since last search
    days_since_last_search = (today - last_search).days
    
    if days_since_last_search >= 7:
        # Reset search count
        await reset_search_count(user_id)
        await increment_search_count(user_id)
        return True, UsageResponse(
            allowed=True,
            remaining_searches=2,  # 3 total - 1 used
            reset_date=today,
            message="Weekly limit reset, first search of new week"
        )
    
    # Check if under limit
    if user.search_count < 3:
        await increment_search_count(user_id)
        remaining = 3 - user.search_count - 1  # -1 for current search
        return True, UsageResponse(
            allowed=True,
            remaining_searches=remaining,
            message=f"Search allowed, {remaining} searches remaining this week"
        )
    
    # Over limit
    days_until_reset = 7 - days_since_last_search
    reset_date = today + timedelta(days=days_until_reset)
    
    return False, UsageResponse(
        allowed=False,
        remaining_searches=0,
        reset_date=reset_date,
        message=f"Free tier limit reached. Resets in {days_until_reset} days on {reset_date}"
    )

async def increment_search_count(user_id: str):
    """Increment user's search count and update last search date"""
    today = date.today()
    query = update(User).where(User.id == user_id).values(
        search_count=User.search_count + 1,
        last_search_date=today
    )
    await database.execute(query)
    logger.info(f"Incremented search count for user {user_id}")

async def reset_search_count(user_id: str):
    """Reset user's search count to 0"""
    query = update(User).where(User.id == user_id).values(
        search_count=0,
        last_search_date=None
    )
    await database.execute(query)
    logger.info(f"Reset search count for user {user_id}")

async def get_usage_stats(user_id: str) -> dict:
    """Get user's current usage statistics"""
    query = select(User).where(User.id == user_id)
    user = await database.fetch_one(query)
    
    if not user:
        return {"error": "User not found"}
    
    stats = {
        "subscription_tier": user.subscription_tier,
        "search_count": user.search_count or 0,
        "last_search_date": user.last_search_date.isoformat() if user.last_search_date else None,
        "is_active": user.is_active
    }
    
    if user.subscription_tier == 'free':
        if user.last_search_date:
            days_since_last_search = (date.today() - user.last_search_date).days
            if days_since_last_search >= 7:
                stats["remaining_searches"] = 3
                stats["reset_date"] = date.today().isoformat()
            else:
                stats["remaining_searches"] = max(0, 3 - user.search_count)
                stats["reset_date"] = (user.last_search_date + timedelta(days=7)).isoformat()
        else:
            stats["remaining_searches"] = 3
            stats["reset_date"] = date.today().isoformat()
    else:
        stats["remaining_searches"] = "unlimited"
        stats["reset_date"] = None
    
    return stats
