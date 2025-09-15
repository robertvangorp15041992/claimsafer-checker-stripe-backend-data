#!/usr/bin/env python3
"""
Database setup script for ClaimSafer authentication testing
"""
import asyncio
import os
from database import connect_db, disconnect_db, database
from models import User, Base
from auth import hash_password
from sqlalchemy import create_engine, select, insert

async def setup_database():
    """Setup database tables and create test user"""
    print("🔧 Setting up database...")
    
    # Connect to database
    await connect_db()
    
    try:
        # Create tables
        print("📋 Creating database tables...")
        engine = create_engine(os.getenv("DATABASE_URL", "sqlite:///test.db"))
        Base.metadata.create_all(bind=engine)
        print("✅ Database tables created successfully!")
        
        # Create test user
        print("👤 Creating test user...")
        import uuid
        test_user = {
            "id": str(uuid.uuid4()),
            "email": "test@claimsafer.com",
            "password_hash": hash_password("testpassword123"),
            "subscription_tier": "free",
            "is_active": True
        }
        
        # Check if user already exists
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
            from sqlalchemy import insert
            query = insert(User).values(**test_user)
            await database.execute(query)
            print("✅ Test user created successfully!")
            print(f"   Email: {test_user['email']}")
            print(f"   Password: testpassword123")
            print(f"   Subscription: {test_user['subscription_tier']}")
        
        # Create an early essentials user for testing
        early_essentials_user = {
            "id": str(uuid.uuid4()),
            "email": "early@claimsafer.com",
            "password_hash": hash_password("earlypassword123"),
            "subscription_tier": "early_essentials",
            "is_active": True
        }
        
        existing_early = await database.fetch_one(
            select(User).where(User.email == early_essentials_user["email"])
        )
        
        if not existing_early:
            query = User.__table__.insert().values(**early_essentials_user)
            await database.execute(query)
            print("✅ Early Essentials test user created successfully!")
            print(f"   Email: {early_essentials_user['email']}")
            print(f"   Password: earlypassword123")
            print(f"   Subscription: {early_essentials_user['subscription_tier']}")
        else:
            print("✅ Early Essentials test user already exists!")
        
        # Create a pro user for testing
        pro_user = {
            "id": str(uuid.uuid4()),
            "email": "pro@claimsafer.com",
            "password_hash": hash_password("propassword123"),
            "subscription_tier": "pro",
            "is_active": True
        }
        
        existing_pro = await database.fetch_one(
            select(User).where(User.email == pro_user["email"])
        )
        
        if not existing_pro:
            query = User.__table__.insert().values(**pro_user)
            await database.execute(query)
            print("✅ Pro test user created successfully!")
            print(f"   Email: {pro_user['email']}")
            print(f"   Password: propassword123")
            print(f"   Subscription: {pro_user['subscription_tier']}")
        else:
            print("✅ Pro test user already exists!")
        
        # Create an enterprise user for testing
        enterprise_user = {
            "id": str(uuid.uuid4()),
            "email": "enterprise@claimsafer.com",
            "password_hash": hash_password("enterprisepassword123"),
            "subscription_tier": "enterprise",
            "is_active": True
        }
        
        existing_enterprise = await database.fetch_one(
            select(User).where(User.email == enterprise_user["email"])
        )
        
        if not existing_enterprise:
            query = User.__table__.insert().values(**enterprise_user)
            await database.execute(query)
            print("✅ Enterprise test user created successfully!")
            print(f"   Email: {enterprise_user['email']}")
            print(f"   Password: enterprisepassword123")
            print(f"   Subscription: {enterprise_user['subscription_tier']}")
        else:
            print("✅ Enterprise test user already exists!")
    
    except Exception as e:
        print(f"❌ Error setting up database: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await disconnect_db()

if __name__ == "__main__":
    asyncio.run(setup_database())
