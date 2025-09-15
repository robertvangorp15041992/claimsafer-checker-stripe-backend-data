#!/usr/bin/env python3
"""
Sync database schema between local SQLite and PostgreSQL
"""
import asyncio
import os
from database import connect_db, disconnect_db, database, Base, engine
from models import User
from auth import hash_password
from sqlalchemy import text
import uuid
from datetime import datetime

async def sync_to_postgresql():
    """Sync local SQLite data to PostgreSQL database"""
    print("🔄 Database Schema Sync")
    print("=" * 40)
    
    # First, get data from local SQLite
    print("📥 Reading data from local SQLite...")
    local_db = Database("sqlite:///./test.db")
    await local_db.connect()
    
    try:
        # Get all users from local database
        users_query = text("SELECT * FROM users")
        local_users = await local_db.fetch_all(users_query)
        print(f"   Found {len(local_users)} users in local database")
        
        # Now connect to PostgreSQL (you'll need to set the external URL)
        postgres_url = os.getenv("POSTGRES_URL")
        if not postgres_url:
            print("❌ POSTGRES_URL not set!")
            print("   Please set it to your external PostgreSQL connection string")
            print("   Example: export POSTGRES_URL='postgresql://postgres:pass@containers-xxx.railway.app:5432/railway'")
            return
        
        print(f"📤 Connecting to PostgreSQL: {postgres_url[:50]}...")
        postgres_db = Database(postgres_url)
        await postgres_db.connect()
        
        try:
            # Create tables in PostgreSQL
            print("🏗️ Creating tables in PostgreSQL...")
            Base.metadata.create_all(bind=postgres_db._backend._engine)
            print("✅ Tables created!")
            
            # Insert users into PostgreSQL
            print("👥 Syncing users to PostgreSQL...")
            synced_count = 0
            
            for user in local_users:
                # Check if user already exists
                existing = await postgres_db.fetch_one(
                    text("SELECT id FROM users WHERE email = :email"),
                    {"email": user["email"]}
                )
                
                if not existing:
                    # Insert user
                    insert_query = text("""
                        INSERT INTO users (id, email, password_hash, subscription_tier, 
                                         stripe_customer_id, stripe_subscription_id, 
                                         created_at, updated_at, last_login, is_active, 
                                         last_payment_date, search_count, last_search_date)
                        VALUES (:id, :email, :password_hash, :subscription_tier,
                                :stripe_customer_id, :stripe_subscription_id,
                                :created_at, :updated_at, :last_login, :is_active,
                                :last_payment_date, :search_count, :last_search_date)
                    """)
                    
                    await postgres_db.execute(insert_query, {
                        "id": user["id"],
                        "email": user["email"],
                        "password_hash": user["password_hash"],
                        "subscription_tier": user["subscription_tier"],
                        "stripe_customer_id": user["stripe_customer_id"],
                        "stripe_subscription_id": user["stripe_subscription_id"],
                        "created_at": user["created_at"],
                        "updated_at": user["updated_at"],
                        "last_login": user["last_login"],
                        "is_active": user["is_active"],
                        "last_payment_date": user["last_payment_date"],
                        "search_count": user["search_count"],
                        "last_search_date": user["last_search_date"]
                    })
                    synced_count += 1
                    print(f"   ✅ Synced: {user['email']}")
                else:
                    print(f"   ⏭️ Already exists: {user['email']}")
            
            print(f"\n✅ Sync complete! Synced {synced_count} users to PostgreSQL")
            
            # Verify sync
            print("\n🔍 Verifying sync...")
            verify_query = text("SELECT COUNT(*) as count FROM users")
            postgres_count = await postgres_db.fetch_one(verify_query)
            print(f"   PostgreSQL now has {postgres_count['count']} users")
            
        finally:
            await postgres_db.disconnect()
            
    except Exception as e:
        print(f"❌ Error during sync: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await local_db.disconnect()

async def create_postgresql_schema_only():
    """Create only the schema in PostgreSQL (without data)"""
    print("🏗️ Creating PostgreSQL Schema Only")
    print("=" * 40)
    
    postgres_url = os.getenv("POSTGRES_URL")
    if not postgres_url:
        print("❌ POSTGRES_URL not set!")
        print("   Please set it to your external PostgreSQL connection string")
        return
    
    try:
        postgres_db = Database(postgres_url)
        await postgres_db.connect()
        
        print("📤 Connected to PostgreSQL!")
        
        # Create tables
        print("🏗️ Creating tables...")
        Base.metadata.create_all(bind=postgres_db._backend._engine)
        print("✅ Tables created successfully!")
        
        # Check what was created
        tables_query = text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        tables = await postgres_db.fetch_all(tables_query)
        
        print(f"\n📋 Created tables:")
        for table in tables:
            print(f"   - {table['table_name']}")
        
        print("\n✅ PostgreSQL schema is ready!")
        print("   You can now deploy your app and it will use the same database as your frontpage")
        
    except Exception as e:
        print(f"❌ Error creating schema: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        try:
            await postgres_db.disconnect()
        except:
            pass

async def main():
    """Main function"""
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "schema":
        await create_postgresql_schema_only()
    else:
        await sync_to_postgresql()

if __name__ == "__main__":
    asyncio.run(main())
