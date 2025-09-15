import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models import Base, User, Tier
from app.db import SessionLocal, engine
from app.services.usage import increment_daily_checks
from datetime import datetime, timedelta

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def client():
    return TestClient(app)

def test_admin_usage_html(client, monkeypatch):
    db = SessionLocal()
    for i in range(3):
        user = User(email=f"user{i}@ex.com", tier=Tier.starter, is_active=True, password_hash="x", role="user")
        db.add(user)
        db.commit()
        for _ in range(i+1):
            increment_daily_checks(db, user.id)
    admin = User(email="admin@ex.com", tier=Tier.enterprise, is_active=True, password_hash="x", role="admin")
    db.add(admin)
    db.commit()
    db.close()
    def fake_require_role(role):
        def dep(*a, **k):
            return admin
        return dep
    monkeypatch.setattr("app.dependencies.require_role", fake_require_role)
    resp = client.get("/admin/usage")
    assert resp.status_code == 200
    assert "user2@ex.com" in resp.text

def test_user_usage_history(client, monkeypatch):
    db = SessionLocal()
    user = User(email="userx@ex.com", tier=Tier.starter, is_active=True, password_hash="x", role="user")
    db.add(user)
    db.commit()
    today = datetime.utcnow().date()
    for i in range(7):
        from app.models import UsageCounter
        uc = UsageCounter(user_id=user.id, date=today - timedelta(days=i), daily_checks_used=i)
        db.add(uc)
    admin = User(email="admin@ex.com", tier=Tier.enterprise, is_active=True, password_hash="x", role="admin")
    db.add(admin)
    db.commit()
    db.close()
    def fake_require_role(role):
        def dep(*a, **k):
            return admin
        return dep
    monkeypatch.setattr("app.dependencies.require_role", fake_require_role)
    resp = client.get(f"/admin/users/userx@ex.com/usage?days=7")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 7
    assert data[0]["daily_checks_used"] == 0 or data[-1]["daily_checks_used"] == 6
