#!/usr/bin/env python3
"""
Setup Railway database connection and sync data
"""
import os
import asyncio
from database import connect_db, disconnect_db, database
from models import User, Base
from sqlalchemy import select, text

async def setup_railway_database():
    """Setup Railway database with proper schema"""
    print("🚀 Setting up Railway Database")
    print("=" * 40)
    
    # Check DATABASE_URL
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL not set!")
        print("\n💡 To set up Railway database:")
        print("   1. Go to your Railway dashboard")
        print("   2. Select your database service")
        print("   3. Copy the PostgreSQL connection string")
        print("   4. Set it as environment variable:")
        print("      export DATABASE_URL='postgresql://user:pass@host:port/dbname'")
        return
    
    if not database_url.startswith("postgresql://"):
        print(f"❌ DATABASE_URL is not PostgreSQL: {database_url}")
        print("   Please set a proper PostgreSQL connection string")
        return
    
    print(f"✅ Using Railway database: {database_url[:50]}...")
    
    try:
        # Connect to Railway database
        print("\n🔌 Connecting to Railway database...")
        await connect_db()
        print("✅ Connected successfully!")
        
        # Create tables
        print("\n📋 Creating database tables...")
        Base.metadata.create_all(bind=database._backend._engine)
        print("✅ Tables created/verified!")
        
        # Check current users
        print("\n👥 Checking existing users...")
        query = select(User)
        users = await database.fetch_all(query)
        print(f"   Found {len(users)} existing users")
        
        if users:
            print("\n📝 Current users in Railway database:")
            for user in users:
                print(f"   - {user.email} ({user.subscription_tier}) - Active: {user.is_active}")
        
        print("\n✅ Railway database setup complete!")
        print("\n💡 Next steps:")
        print("   1. Run: python3 compare_databases.py")
        print("   2. Run: python3 compare_databases.py sync (to sync local data)")
        
    except Exception as e:
        print(f"❌ Error setting up Railway database: {e}")
        print("\n💡 Troubleshooting:")
        print("   1. Check if Railway service is running")
        print("   2. Verify DATABASE_URL is correct")
        print("   3. Check database permissions")
    
    finally:
        try:
            await disconnect_db()
        except:
            pass

if __name__ == "__main__":
    asyncio.run(setup_railway_database())
