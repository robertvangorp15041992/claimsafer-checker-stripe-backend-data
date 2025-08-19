import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Base, Tier
from app.repository import create_user, get_user_by_email, upsert_user_by_email
from app.services.users import find_or_create_by_email, set_user_tier

def setup_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    return engine, TestingSessionLocal

@pytest.fixture
def db():
    engine, TestingSessionLocal = setup_db()
    db = TestingSessionLocal()
    yield db
    db.close()
    engine.dispose()

def test_email_normalization_and_uniqueness(db):
    user1 = create_user(db, email="Test@Example.com ", tier=Tier.starter)
    user2 = get_user_by_email(db, " test@example.com")
    assert user1.id == user2.id
    with pytest.raises(Exception):
        create_user(db, email="TEST@example.com", tier=Tier.starter)

def test_tier_set_and_update(db):
    user = find_or_create_by_email(db, "a@b.com", default_tier=Tier.free)
    assert user.tier == Tier.free
    set_user_tier(db, "a@b.com", Tier.pro)
    user2 = get_user_by_email(db, "A@B.COM")
    assert user2.tier == Tier.pro

def test_upsert_user_by_email(db):
    user = upsert_user_by_email(db, "c@d.com", Tier.starter)
    assert user.tier == Tier.starter
    user2 = upsert_user_by_email(db, "C@D.COM", Tier.pro)
    assert user2.id == user.id
    assert user2.tier == Tier.pro
