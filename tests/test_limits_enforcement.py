import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models import Base, User, Tier
from app.db import SessionLocal, engine
from sqlalchemy.orm import sessionmaker
from app.services.usage import increment_daily_checks

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def client():
    return TestClient(app)

def get_token_for_user(email, tier):
    db = SessionLocal()
    user = db.query(User).filter_by(email=email).first()
    if not user:
        user = User(email=email, tier=tier, is_active=True, password_hash="x", role="user")
        db.add(user)
        db.commit()
    db.close()
    return "test-token"  # Patch get_current_user to accept this

def test_starter_limit(client, monkeypatch):
    token = get_token_for_user("starter@ex.com", Tier.starter)
    def fake_get_current_user(*a, **k):
        db = SessionLocal()
        return db.query(User).filter_by(email="starter@ex.com").first()
    monkeypatch.setattr("app.dependencies.get_current_user", fake_get_current_user)
    for _ in range(20):
        resp = client.post("/api/claims/check", json={"text": "foo", "countries": ["NL"]})
        assert resp.status_code == 200
    resp = client.post("/api/claims/check", json={"text": "foo", "countries": ["NL"]})
    assert resp.status_code == 402
    assert resp.json()["code"] == "DAILY_LIMIT_EXCEEDED"

def test_pro_no_limit(client, monkeypatch):
    token = get_token_for_user("pro@ex.com", Tier.pro)
    def fake_get_current_user(*a, **k):
        db = SessionLocal()
        return db.query(User).filter_by(email="pro@ex.com").first()
    monkeypatch.setattr("app.dependencies.get_current_user", fake_get_current_user)
    for _ in range(201):
        resp = client.post("/api/claims/check", json={"text": "foo", "countries": ["NL"]})
        assert resp.status_code == 200

def test_countries_limit(client, monkeypatch):
    token = get_token_for_user("starter2@ex.com", Tier.starter)
    def fake_get_current_user(*a, **k):
        db = SessionLocal()
        return db.query(User).filter_by(email="starter2@ex.com").first()
    monkeypatch.setattr("app.dependencies.get_current_user", fake_get_current_user)
    resp = client.post("/api/claims/check", json={"text": "foo", "countries": ["NL", "DE", "FR"]})
    assert resp.status_code == 402
    assert resp.json()["code"] == "COUNTRIES_LIMIT_EXCEEDED"
