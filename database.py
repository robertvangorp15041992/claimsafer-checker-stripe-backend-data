"""
Database configuration and connection management
"""
import os
from databases import Database
from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Database URL from environment
# In production (Railway), this will be set to the PostgreSQL connection string
# In local development, this will use SQLite for testing
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")

# SQLAlchemy setup
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
metadata = MetaData()

# Async database connection
database = Database(DATABASE_URL)

async def get_database():
    """Get database connection"""
    return database

async def connect_db():
    """Connect to database"""
    await database.connect()

async def disconnect_db():
    """Disconnect from database"""
    await database.disconnect()
