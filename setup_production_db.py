#!/usr/bin/env python3
"""
Production database setup for Railway deployment
This script sets up the database schema and creates initial data
"""
import asyncio
import os
import sys
from database import connect_db, disconnect_db, database, Base, engine
from models import User
from auth import hash_password
from sqlalchemy import select, text
import uuid
from datetime import datetime

async def setup_production_database():
    """Setup production database with schema and initial data"""
    print("🚀 Setting up Production Database")
    print("=" * 50)
    
    # Check if we're in production (Railway)
    database_url = os.getenv("DATABASE_URL", "")
    is_production = database_url.startswith("postgresql://")
    
    print(f"📊 Database: {'PostgreSQL (Production)' if is_production else 'SQLite (Local)'}")
    print(f"🔗 URL: {database_url[:50]}...")
    
    try:
        # Connect to database
        print("\n🔌 Connecting to database...")
        await connect_db()
        print("✅ Connected successfully!")
        
        # Create tables
        print("\n📋 Creating database tables...")
        Base.metadata.create_all(bind=engine)
        print("✅ Tables created/verified!")
        
        # Check if users table has data
        print("\n👥 Checking existing users...")
        query = select(User)
        users = await database.fetch_all(query)
        print(f"   Found {len(users)} existing users")
        
        if users:
            print("\n📝 Current users in database:")
            for user in users:
                print(f"   - {user.email} ({user.subscription_tier}) - Active: {user.is_active}")
        
        # If no users exist, create a default admin user
        if len(users) == 0:
            print("\n👤 Creating default admin user...")
            admin_user = {
                "id": str(uuid.uuid4()),
                "email": "admin@claimsafer.com",
                "password_hash": hash_password("admin123"),
                "subscription_tier": "enterprise",
                "is_active": True,
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
                "search_count": 0,
                "last_search_date": None
            }
            
            insert_query = User.__table__.insert().values(**admin_user)
            await database.execute(insert_query)
            print("✅ Default admin user created!")
            print(f"   Email: admin@claimsafer.com")
            print(f"   Password: admin123")
            print(f"   Tier: enterprise")
        
        print("\n✅ Production database setup complete!")
        
        # Show database info
        print(f"\n📊 Database Summary:")
        print(f"   Type: {'PostgreSQL' if is_production else 'SQLite'}")
        print(f"   Users: {len(users) + (1 if len(users) == 0 else 0)}")
        print(f"   Tables: users, sessions (if applicable)")
        
    except Exception as e:
        print(f"❌ Error setting up database: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    finally:
        try:
            await disconnect_db()
        except:
            pass

if __name__ == "__main__":
    asyncio.run(setup_production_database())
