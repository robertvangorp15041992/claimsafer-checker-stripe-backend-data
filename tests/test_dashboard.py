import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models import Base, User, Tier
from app.db import SessionLocal, engine
from sqlalchemy.orm import sessionmaker
from werkzeug.security import generate_password_hash
import os

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def client():
    return TestClient(app)

def login_session(client, email, tier=Tier.starter, stripe_customer_id=None):
    db = SessionLocal()
    user = db.query(User).filter_by(email=email).first()
    if not user:
        user = User(email=email, tier=tier, is_active=True, password_hash=generate_password_hash("pw123456"), role="user", stripe_customer_id=stripe_customer_id)
        db.add(user)
        db.commit()
    db.close()
    # Simulate login by setting session cookie
    from itsdangerous import URLSafeTimedSerializer
    secret = os.getenv("SESSION_SECRET", "dev-session-secret")
    serializer = URLSafeTimedSerializer(secret)
    session_cookie = serializer.dumps(email, salt="session")
    client.cookies.set("session", session_cookie)
    return user

def test_dashboard_requires_login(client):
    resp = client.get("/dashboard")
    assert resp.status_code == 401

def test_dashboard_shows_user_info(client):
    login_session(client, "dash@ex.com", Tier.pro)
    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert "dash@ex.com" in resp.text
    assert "Pro" in resp.text or "pro" in resp.text

def test_billing_portal_redirect(client, monkeypatch):
    user = login_session(client, "bill@ex.com", Tier.starter, stripe_customer_id="cus_123")
    class FakeSession:
        url = "https://stripe-portal.test/session"
    monkeypatch.setattr("stripe.billing_portal.Session.create", lambda **kwargs: FakeSession())
    # Get CSRF token
    resp = client.get("/billing")
    assert resp.status_code == 200
    import re
    m = re.search(r'name="csrf_token" value="([^"]+)"', resp.text)
    assert m
    csrf_token = m.group(1)
    # Post to portal
    resp2 = client.post("/billing/portal", data={"csrf_token": csrf_token}, allow_redirects=False)
    assert resp2.status_code == 303
    assert resp2.headers["location"].startswith("https://stripe-portal.test/")

def test_change_password_csrf(client):
    login_session(client, "pw@ex.com", Tier.starter)
    # No CSRF
    resp = client.post("/account/change-password", data={"current_password": "pw123456", "new_password": "newpass123"})
    assert resp.status_code == 403
    # With CSRF
    resp = client.get("/account")
    import re
    m = re.search(r'name="csrf_token" value="([^"]+)"', resp.text)
    csrf_token = m.group(1)
    resp2 = client.post("/account/change-password", data={"csrf_token": csrf_token, "current_password": "pw123456", "new_password": "newpass123"}, allow_redirects=False)
    assert resp2.status_code == 303
    # Password actually changed
    db = SessionLocal()
    user = db.query(User).filter_by(email="pw@ex.com").first()
    assert user is not None
    from werkzeug.security import check_password_hash
    assert check_password_hash(user.password_hash, "newpass123")
    db.close()
