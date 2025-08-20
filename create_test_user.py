#!/usr/bin/env python3
"""
Script to create a test user in the database
"""

import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from werkzeug.security import generate_password_hash

# Add the app directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.models import Base, User, Tier
from app.db import engine, SessionLocal

def create_test_user():
    """Create a test user in the database."""
    
    # Create database session
    db = SessionLocal()
    
    try:
        # Check if user already exists
        existing_user = db.query(User).filter_by(email="robertvgorp@gmail.com").first()
        
        if existing_user:
            print("✅ User already exists!")
            print(f"Email: {existing_user.email}")
            print(f"Tier: {existing_user.tier}")
            print(f"Active: {existing_user.is_active}")
            return
        
        # Create new user
        test_user = User(
            email="robertvgorp@gmail.com",
            password_hash=generate_password_hash("test123456"),
            tier=Tier.pro,  # Give pro tier for testing
            is_active=True,
            role="user"
        )
        
        # Add to database
        db.add(test_user)
        db.commit()
        db.refresh(test_user)
        
        print("✅ Test user created successfully!")
        print(f"Email: {test_user.email}")
        print(f"Password: test123456")
        print(f"Tier: {test_user.tier}")
        print(f"Active: {test_user.is_active}")
        
    except Exception as e:
        print(f"❌ Error creating user: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    create_test_user()
