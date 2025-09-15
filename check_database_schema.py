#!/usr/bin/env python3
"""
Check database schema and data in PostgreSQL
"""
import asyncio
import os
from database import connect_db, disconnect_db, database
from sqlalchemy import text

async def check_database_schema():
    """Check what tables and data exist in the database"""
    print("🔍 Database Schema Check")
    print("=" * 40)
    
    database_url = os.getenv("DATABASE_URL", "")
    print(f"📊 Database URL: {database_url[:50]}...")
    
    try:
        await connect_db()
        print("✅ Connected to database!")
        
        # Check what tables exist
        print("\n📋 Checking existing tables...")
        tables_query = text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        tables = await database.fetch_all(tables_query)
        
        print(f"   Found {len(tables)} tables:")
        for table in tables:
            print(f"   - {table['table_name']}")
        
        # Check users table specifically
        if any(table['table_name'] == 'users' for table in tables):
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
        if any(table['table_name'] == 'users' for table in tables):
            print("\n🏗️ Checking users table structure...")
            columns_query = text("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns 
                WHERE table_name = 'users' 
                ORDER BY ordinal_position
            """)
            columns = await database.fetch_all(columns_query)
            
            print("   Users table columns:")
            for col in columns:
                nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
                default = f" DEFAULT {col['column_default']}" if col['column_default'] else ""
                print(f"     - {col['column_name']}: {col['data_type']} {nullable}{default}")
        
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
    asyncio.run(check_database_schema())
