#!/usr/bin/env python3
"""
Check SQLite database schema and data
"""
import asyncio
import os
from database import connect_db, disconnect_db, database
from sqlalchemy import text

async def check_sqlite_schema():
    """Check what tables and data exist in SQLite database"""
    print("🔍 SQLite Database Schema Check")
    print("=" * 40)
    
    database_url = os.getenv("DATABASE_URL", "")
    print(f"📊 Database URL: {database_url}")
    
    try:
        await connect_db()
        print("✅ Connected to database!")
        
        # Check what tables exist (SQLite syntax)
        print("\n📋 Checking existing tables...")
        tables_query = text("SELECT name FROM sqlite_master WHERE type='table'")
        tables = await database.fetch_all(tables_query)
        
        print(f"   Found {len(tables)} tables:")
        for table in tables:
            print(f"   - {table['name']}")
        
        # Check users table specifically
        if any(table['name'] == 'users' for table in tables):
            print("\n👥 Checking users table...")
            users_query = text("SELECT COUNT(*) as count FROM users")
            user_count = await database.fetch_one(users_query)
            print(f"   Users count: {user_count['count']}")
            
            # Show sample users
            if user_count['count'] > 0:
                sample_query = text("SELECT email, subscription_tier, is_active FROM users LIMIT 5")
                sample_users = await database.fetch_all(sample_query)
                print("   Sample users:")
                for user in sample_users:
                    print(f"     - {user['email']} ({user['subscription_tier']}) - Active: {user['is_active']}")
        else:
            print("\n❌ No 'users' table found!")
        
        # Check table structure
        if any(table['name'] == 'users' for table in tables):
            print("\n🏗️ Checking users table structure...")
            columns_query = text("PRAGMA table_info(users)")
            columns = await database.fetch_all(columns_query)
            
            print("   Users table columns:")
            for col in columns:
                nullable = "NULL" if col['notnull'] == 0 else "NOT NULL"
                default = f" DEFAULT {col['dflt_value']}" if col['dflt_value'] else ""
                print(f"     - {col['name']}: {col['type']} {nullable}{default}")
        
    except Exception as e:
        print(f"❌ Error checking database: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        try:
            await disconnect_db()
        except:
            pass

if __name__ == "__main__":
    asyncio.run(check_sqlite_schema())
