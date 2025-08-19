import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Base, User, Tier
from app.auth import sign_activation_token, sign_magic_token
from app.main import app
from app.db import get_db
from unittest.mock import patch

@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()
    engine.dispose()

@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)

def test_onboarding_and_activation(client, db):
    # Simulate webhook: create inactive user
    user = User(email="test@ex.com", tier=Tier.starter, is_active=False)
    db.add(user)
    db.commit()
    token = sign_activation_token("test@ex.com")
    # GET form
    resp = client.get(f"/auth/activate?token={token}")
    assert resp.status_code == 200
    # POST activation
    resp = client.post("/auth/activate", data={"token": token, "password": "secret123"}, allow_redirects=False)
    assert resp.status_code == 302
    db.refresh(user)
    assert user.is_active
    assert user.password_hash is not None

def test_login_and_dashboard(client, db):
    from werkzeug.security import generate_password_hash
    user = User(email="login@ex.com", tier=Tier.pro, is_active=True, password_hash=generate_password_hash("pw123456"))
    db.add(user)
    db.commit()
    # GET login form
    resp = client.get("/login")
    assert resp.status_code == 200
    # POST login
    resp = client.post("/login", data={"email": "login@ex.com", "password": "pw123456"}, allow_redirects=False)
    assert resp.status_code == 302
    assert "session=" in resp.headers.get("set-cookie", "")
    # Access dashboard
    cookies = resp.cookies
    resp2 = client.get("/dashboard", cookies=cookies)
    assert resp2.status_code == 200
    assert "login@ex.com" in resp2.text
    assert "pro" in resp2.text
    # Wrong password
    resp = client.post("/login", data={"email": "login@ex.com", "password": "wrongpass"})
    assert resp.status_code == 401

def test_magic_link_flow(client, db):
    from werkzeug.security import generate_password_hash
    user = User(email="magic@ex.com", tier=Tier.starter, is_active=True, password_hash=generate_password_hash("pw123456"))
    db.add(user)
    db.commit()
    # POST magic link
    with patch("app.utils.send_email") as mock_send:
        resp = client.post("/auth/magic-link", data={"email": "magic@ex.com"})
        assert resp.status_code == 200
        assert mock_send.called
        # Extract token from email body
        html = mock_send.call_args[0][2]
        import re
        m = re.search(r'token=([\w\.-]+)', html)
        assert m
        token = m.group(1)
    # GET magic login
    resp = client.get(f"/auth/magic-login?token={token}", allow_redirects=False)
    assert resp.status_code == 302
    assert "session=" in resp.headers.get("set-cookie", "")
    # Access dashboard
    cookies = resp.cookies
    resp2 = client.get("/dashboard", cookies=cookies)
    assert resp2.status_code == 200
    assert "magic@ex.com" in resp2.text
