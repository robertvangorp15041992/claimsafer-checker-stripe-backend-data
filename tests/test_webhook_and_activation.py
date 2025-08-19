import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models import User, WebhookEvent, Tier, Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch

# Use in-memory SQLite for tests
TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
Base.metadata.create_all(bind=test_engine)

client = TestClient(app)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides = getattr(app, 'dependency_overrides', {})
app.dependency_overrides[app.get_dependency('get_db') if hasattr(app, 'get_dependency') else 'get_db'] = override_get_db


def fake_stripe_event():
    return {
        "id": "evt_test_123",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_123",
                "customer_email": "testuser@example.com",
                "customer": "cus_test_123",
                "lines": {"data": [{"price": {"id": "price_456PRO"}}]},
            }
        },
    }

def test_webhook_and_activation(monkeypatch):
    # Patch stripe.Webhook.construct_event to bypass signature
    monkeypatch.setattr("stripe.Webhook.construct_event", lambda payload, sig, secret: fake_stripe_event())
    # Patch send_email to capture email
    sent = {}
    def fake_send_email(to_email, subject, html, text=None):
        sent["to"] = to_email
        sent["subject"] = subject
        sent["html"] = html
    with patch("app.utils.send_email", fake_send_email):
        resp = client.post("/webhook/stripe", data=b"{}", headers={"stripe-signature": "test"})
        assert resp.status_code == 200
        db = TestingSessionLocal()
        user = db.query(User).filter_by(email="testuser@example.com").first()
        assert user is not None
        assert user.tier == Tier.pro
        event = db.query(WebhookEvent).filter_by(stripe_event_id="evt_test_123").first()
        assert event is not None
        assert sent["to"] == "testuser@example.com"
        assert "Activate" in sent["subject"]
        # Extract token from email
        import re
        m = re.search(r'token=([\w\.-]+)', sent["html"])
        assert m
        token = m.group(1)
        # GET /auth/activate
        resp = client.get(f"/auth/activate?token={token}")
        assert resp.status_code == 200
        assert "form" in resp.text
        # POST /auth/activate
        resp = client.post("/auth/activate", data={"token": token, "password": "newpass123"})
        assert resp.status_code in (200, 302)
        db.refresh(user)
        assert user.is_active
        assert user.password_hash is not None
        db.close()
