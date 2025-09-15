#!/usr/bin/env python3
"""
Database comparison tool for ClaimSafer
Compares user data between local SQLite and Railway PostgreSQL databases
"""
import asyncio
import os
import sys
from datetime import datetime
from database import connect_db, disconnect_db, database
from models import User
from sqlalchemy import select, text

async def get_local_users():
    """Get users from local SQLite database"""
    print("🔍 Fetching users from local SQLite database...")
    
    # Connect to local SQLite
    local_db = Database("sqlite:///./test.db")
    await local_db.connect()
    
    try:
        query = select(User)
        users = await local_db.fetch_all(query)
        print(f"✅ Found {len(users)} users in local database")
        return users
    finally:
        await local_db.disconnect()

async def get_railway_users():
    """Get users from Railway PostgreSQL database"""
    print("🔍 Fetching users from Railway PostgreSQL database...")
    
    # Check if DATABASE_URL is set
    railway_url = os.getenv("DATABASE_URL")
    if not railway_url:
        print("❌ DATABASE_URL environment variable not set")
        print("   Please set it to your Railway PostgreSQL connection string")
        print("   Example: export DATABASE_URL='postgresql://user:pass@host:port/dbname'")
        return []
    
    if not railway_url.startswith("postgresql://"):
        print("❌ DATABASE_URL doesn't appear to be a PostgreSQL connection string")
        print(f"   Current value: {railway_url}")
        return []
    
    # Connect to Railway database
    railway_db = Database(railway_url)
    await railway_db.connect()
    
    try:
        query = select(User)
        users = await railway_db.fetch_all(query)
        print(f"✅ Found {len(users)} users in Railway database")
        return users
    except Exception as e:
        print(f"❌ Error connecting to Railway database: {e}")
        return []
    finally:
        await railway_db.disconnect()

def format_user_info(user):
    """Format user information for display"""
    return {
        "id": str(user.id),
        "email": user.email,
        "subscription_tier": user.subscription_tier,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "last_login": user.last_login.isoformat() if user.last_login else None,
        "search_count": user.search_count or 0,
        "last_search_date": user.last_search_date.isoformat() if user.last_search_date else None
    }

async def compare_databases():
    """Compare local and Railway databases"""
    print("🔍 ClaimSafer Database Comparison Tool")
    print("=" * 50)
    
    # Get users from both databases
    local_users = await get_local_users()
    railway_users = await get_railway_users()
    
    if not railway_users:
        print("\n❌ Cannot compare - Railway database not accessible")
        return
    
    # Convert to dictionaries for easier comparison
    local_dict = {user.email: format_user_info(user) for user in local_users}
    railway_dict = {user.email: format_user_info(user) for user in railway_users}
    
    print(f"\n📊 Database Comparison Results:")
    print(f"   Local SQLite: {len(local_users)} users")
    print(f"   Railway PostgreSQL: {len(railway_users)} users")
    
    # Find differences
    local_emails = set(local_dict.keys())
    railway_emails = set(railway_dict.keys())
    
    only_local = local_emails - railway_emails
    only_railway = railway_emails - local_emails
    common_emails = local_emails & railway_emails
    
    print(f"\n🔍 User Analysis:")
    print(f"   Users only in local: {len(only_local)}")
    print(f"   Users only in Railway: {len(only_railway)}")
    print(f"   Users in both: {len(common_emails)}")
    
    # Show users only in local
    if only_local:
        print(f"\n📝 Users only in local SQLite:")
        for email in sorted(only_local):
            user = local_dict[email]
            print(f"   - {email} ({user['subscription_tier']}) - Created: {user['created_at']}")
    
    # Show users only in Railway
    if only_railway:
        print(f"\n📝 Users only in Railway PostgreSQL:")
        for email in sorted(only_railway):
            user = railway_dict[email]
            print(f"   - {email} ({user['subscription_tier']}) - Created: {user['created_at']}")
    
    # Compare common users
    if common_emails:
        print(f"\n🔍 Comparing common users:")
        differences = []
        
        for email in sorted(common_emails):
            local_user = local_dict[email]
            railway_user = railway_dict[email]
            
            # Check for differences
            user_diffs = []
            for key in ['subscription_tier', 'is_active', 'search_count', 'last_search_date']:
                if local_user[key] != railway_user[key]:
                    user_diffs.append(f"{key}: local={local_user[key]} vs railway={railway_user[key]}")
            
            if user_diffs:
                differences.append((email, user_diffs))
            else:
                print(f"   ✅ {email} - Identical")
        
        if differences:
            print(f"\n⚠️  Users with differences:")
            for email, diffs in differences:
                print(f"   📝 {email}:")
                for diff in diffs:
                    print(f"      - {diff}")
    
    # Summary
    print(f"\n📊 Summary:")
    if not only_local and not only_railway and not differences:
        print("   ✅ Databases are in sync!")
    else:
        print("   ⚠️  Databases have differences")
        print("   💡 Consider syncing the databases if needed")

async def sync_to_railway():
    """Sync local users to Railway database"""
    print("\n🔄 Syncing local users to Railway database...")
    
    local_users = await get_local_users()
    railway_url = os.getenv("DATABASE_URL")
    
    if not railway_url or not railway_url.startswith("postgresql://"):
        print("❌ Cannot sync - Railway DATABASE_URL not properly configured")
        return
    
    railway_db = Database(railway_url)
    await railway_db.connect()
    
    try:
        synced_count = 0
        for user in local_users:
            # Check if user exists in Railway
            existing = await railway_db.fetch_one(
                select(User).where(User.email == user.email)
            )
            
            if not existing:
                # Insert user into Railway
                insert_query = User.__table__.insert().values(
                    id=str(user.id),
                    email=user.email,
                    password_hash=user.password_hash,
                    subscription_tier=user.subscription_tier,
                    stripe_customer_id=user.stripe_customer_id,
                    stripe_subscription_id=user.stripe_subscription_id,
                    created_at=user.created_at,
                    updated_at=user.updated_at,
                    last_login=user.last_login,
                    is_active=user.is_active,
                    last_payment_date=user.last_payment_date,
                    search_count=user.search_count or 0,
                    last_search_date=user.last_search_date
                )
                await railway_db.execute(insert_query)
                synced_count += 1
                print(f"   ✅ Synced user: {user.email}")
            else:
                print(f"   ⏭️  User already exists: {user.email}")
        
        print(f"\n✅ Sync complete! Synced {synced_count} new users to Railway")
        
    except Exception as e:
        print(f"❌ Error during sync: {e}")
    finally:
        await railway_db.disconnect()

async def main():
    """Main function"""
    if len(sys.argv) > 1 and sys.argv[1] == "sync":
        await sync_to_railway()
    else:
        await compare_databases()

if __name__ == "__main__":
    asyncio.run(main())
