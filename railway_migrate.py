#!/usr/bin/env python3
"""
Railway database migration script to add role column.
This script will be run on Railway to update the database schema.
"""

import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError

def migrate_database():
    """Add role column to users table if it doesn't exist."""
    
    # Get database URL from environment
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL environment variable not set")
        return False
    
    try:
        # Create engine
        engine = create_engine(database_url)
        
        with engine.connect() as conn:
            # Check if role column exists
            try:
                result = conn.execute(text("SELECT role FROM users LIMIT 1"))
                print("✅ Role column already exists")
                return True
            except ProgrammingError:
                print("📝 Role column doesn't exist, adding it...")
                
                # Add role column
                conn.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR(50)"))
                conn.commit()
                print("✅ Role column added successfully")
                return True
                
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False

if __name__ == "__main__":
    print("🔄 Starting Railway database migration...")
    success = migrate_database()
    if success:
        print("✅ Migration completed successfully")
    else:
        print("❌ Migration failed")
        sys.exit(1)
