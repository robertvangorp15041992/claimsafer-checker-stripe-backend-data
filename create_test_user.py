#!/usr/bin/env python3
"""
Script to create a test user for testing authentication
"""
import asyncio
import os
from database import connect_db, disconnect_db, database
from auth import hash_password
from sqlalchemy import insert
from models import User

async def create_test_user():
    """Create a test user for testing"""
    await connect_db()
    
    # Test user data
    test_user = {
        "email": "test@claimsafer.com",
        "password_hash": hash_password("testpassword123"),
        "subscription_tier": "free",
        "is_active": True
    }
    
    try:
        # Check if user already exists
        from sqlalchemy import select
        existing_user = await database.fetch_one(
            select(User).where(User.email == test_user["email"])
        )
        
        if existing_user:
            print("✅ Test user already exists!")
            print(f"   Email: {existing_user.email}")
            print(f"   Subscription: {existing_user.subscription_tier}")
            print(f"   Search Count: {existing_user.search_count}")
        else:
            # Create new user
            query = insert(User).values(**test_user)
            await database.execute(query)
            print("✅ Test user created successfully!")
            print(f"   Email: {test_user['email']}")
            print(f"   Password: testpassword123")
            print(f"   Subscription: {test_user['subscription_tier']}")
    
    except Exception as e:
        print(f"❌ Error creating test user: {e}")
    
    finally:
        await disconnect_db()

if __name__ == "__main__":
    asyncio.run(create_test_user())
