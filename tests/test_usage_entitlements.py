import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Base, Tier
from app.services.entitlements import get_entitlements, max_daily_checks
from app.repository import create_user
from app.services.usage import get_or_create_today_counter, increment_daily_checks, remaining_daily_checks

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

def test_entitlements_loading():
    for tier in [Tier.free, Tier.starter, Tier.pro, Tier.enterprise]:
        ent = get_entitlements(tier)
        assert "daily_checks" in ent
        val = max_daily_checks(tier)
        if ent["daily_checks"] == -1:
            import math
            assert val == math.inf
        else:
            assert val == ent["daily_checks"]

def test_usage_increment_and_limit(db):
    user = create_user(db, email="x@y.com", tier=Tier.starter)
    ent = get_entitlements(Tier.starter)
    max_checks = ent["daily_checks"]
    for i in range(max_checks):
        counter = increment_daily_checks(db, user.id)
        assert counter.daily_checks_used == i + 1
        remaining = remaining_daily_checks(db, user, ent)
        assert remaining == max_checks - (i + 1)
    # Next increment should still increment, but remaining will be negative
    counter = increment_daily_checks(db, user.id)
    assert counter.daily_checks_used == max_checks + 1
    remaining = remaining_daily_checks(db, user, ent)
    assert remaining == -1
