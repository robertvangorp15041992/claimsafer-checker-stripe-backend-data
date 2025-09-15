#!/usr/bin/env python3
"""
Check Railway database connection and show current configuration
"""
import os
import asyncio
from database import connect_db, disconnect_db, database
from models import User
from sqlalchemy import select, text

async def check_railway_connection():
    """Check Railway database connection and show info"""
    print("🔍 Railway Database Connection Check")
    print("=" * 40)
    
    # Check environment variables
    database_url = os.getenv("DATABASE_URL")
    print(f"📋 DATABASE_URL: {database_url[:50]}..." if database_url else "❌ DATABASE_URL not set")
    
    if not database_url:
        print("\n❌ DATABASE_URL environment variable not found!")
        print("   Please set it with your Railway PostgreSQL connection string")
        print("   Example: export DATABASE_URL='postgresql://user:pass@host:port/dbname'")
        return
    
    if not database_url.startswith("postgresql://"):
        print(f"\n❌ DATABASE_URL doesn't appear to be PostgreSQL: {database_url}")
        return
    
    print(f"✅ DATABASE_URL looks like a PostgreSQL connection")
    
    # Try to connect
    try:
        print("\n🔌 Attempting to connect to Railway database...")
        await connect_db()
        print("✅ Successfully connected to Railway database!")
        
        # Check if users table exists
        print("\n📊 Checking database structure...")
        try:
            # Try to query users table
            query = select(User).limit(1)
            result = await database.fetch_one(query)
            print("✅ Users table exists and is accessible")
            
            # Get user count
            count_query = text("SELECT COUNT(*) as count FROM users")
            count_result = await database.fetch_one(count_query)
            user_count = count_result['count'] if count_result else 0
            print(f"📈 Total users in Railway database: {user_count}")
            
            # Show sample users
            if user_count > 0:
                print("\n👥 Sample users:")
                sample_query = select(User).limit(5)
                sample_users = await database.fetch_all(sample_query)
                
                for user in sample_users:
                    print(f"   - {user.email} ({user.subscription_tier}) - Active: {user.is_active}")
            
        except Exception as e:
            print(f"❌ Error querying users table: {e}")
            print("   The users table might not exist or have a different structure")
        
    except Exception as e:
        print(f"❌ Failed to connect to Railway database: {e}")
        print("\n💡 Troubleshooting tips:")
        print("   1. Check if your Railway service is running")
        print("   2. Verify the DATABASE_URL is correct")
        print("   3. Check if the database credentials are valid")
        print("   4. Ensure your IP is whitelisted (if required)")
    
    finally:
        try:
            await disconnect_db()
        except:
            pass

if __name__ == "__main__":
    asyncio.run(check_railway_connection())
