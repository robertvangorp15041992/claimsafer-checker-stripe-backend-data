import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models import User, WebhookEvent, Tier, Base
from app.db import engine, SessionLocal
from unittest.mock import patch

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

def fake_stripe_event():
    return {
        "id": "evt_test_123",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_123",
                "customer_details": {"email": "TestUser@Example.com "},
                "customer": "cus_test_123",
            }
        },
    }

def fake_line_items(session_id):
    return {"data": [{"price": {"id": "price_456PRO"}}]}

def test_webhook_checkout_and_idempotency(monkeypatch):
    monkeypatch.setattr("stripe.Webhook.construct_event", lambda payload, sig, secret: fake_stripe_event())
    monkeypatch.setattr("stripe.checkout.Session.list_line_items", lambda session_id: fake_line_items(session_id))
    sent = {}
    def fake_send_email(to_email, subject, html, text=None):
        sent["to"] = to_email
        sent["subject"] = subject
        sent["html"] = html
    with patch("app.utils.send_email", fake_send_email):
        resp = client.post("/webhook/stripe", data=b"{}", headers={"stripe-signature": "test"})
        assert resp.status_code == 200
        db = SessionLocal()
        user = db.query(User).filter_by(email="testuser@example.com").first()
        assert user is not None
        assert user.tier == Tier.pro
        event = db.query(WebhookEvent).filter_by(stripe_event_id="evt_test_123").first()
        assert event is not None
        assert sent["to"] == "testuser@example.com"
        assert "/auth/activate?token=" in sent["html"]
        # Idempotency: call again
        resp2 = client.post("/webhook/stripe", data=b"{}", headers={"stripe-signature": "test"})
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "duplicate_ignored"
        db.close()
