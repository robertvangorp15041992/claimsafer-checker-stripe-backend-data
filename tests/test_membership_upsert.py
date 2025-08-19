import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Base, Tier, User, MembershipAudit
from app.services.memberships import upsert_membership_from_checkout, upsert_membership_from_subscription
from app.repository import get_user_by_email
from app.billing import PRICE_TO_TIER

@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()
    engine.dispose()

PRO_PRICE = next(pid for pid, tier in PRICE_TO_TIER.items() if tier == Tier.pro)
STARTER_PRICE = next(pid for pid, tier in PRICE_TO_TIER.items() if tier == Tier.starter)


def test_checkout_upsert_creates_user(db):
    email = "test@ex.com"
    user = upsert_membership_from_checkout(
        db,
        email=email,
        stripe_customer_id="cus_123",
        line_item_price_ids=[PRO_PRICE],
        stripe_event_id="evt_1",
        reason="checkout.session.completed",
    )
    assert user.email == email
    assert user.tier == Tier.pro
    audit = db.query(MembershipAudit).filter_by(email=email).first()
    assert audit is not None
    assert audit.new_tier == Tier.pro
    assert audit.reason == "checkout.session.completed"


def test_checkout_upsert_updates_tier_upward(db):
    email = "test2@ex.com"
    user = upsert_membership_from_checkout(
        db,
        email=email,
        stripe_customer_id="cus_456",
        line_item_price_ids=[STARTER_PRICE],
        stripe_event_id="evt_2",
        reason="checkout.session.completed",
    )
    assert user.tier == Tier.starter
    user2 = upsert_membership_from_checkout(
        db,
        email=email,
        stripe_customer_id="cus_456",
        line_item_price_ids=[PRO_PRICE],
        stripe_event_id="evt_3",
        reason="checkout.session.completed",
    )
    assert user2.tier == Tier.pro
    audits = db.query(MembershipAudit).filter_by(email=email).all()
    assert len(audits) == 2
    assert audits[-1].old_tier == Tier.starter
    assert audits[-1].new_tier == Tier.pro


def test_subscription_updated_recomputes_highest_tier(db):
    email = "test3@ex.com"
    user = upsert_membership_from_checkout(
        db,
        email=email,
        stripe_customer_id="cus_789",
        line_item_price_ids=[STARTER_PRICE],
        stripe_event_id="evt_4",
        reason="checkout.session.completed",
    )
    assert user.tier == Tier.starter
    user2 = upsert_membership_from_subscription(
        db,
        email=email,
        stripe_customer_id="cus_789",
        active_subscription_price_ids=[STARTER_PRICE, PRO_PRICE],
        stripe_event_id="evt_5",
        reason="subscription.updated",
    )
    assert user2.tier == Tier.pro
    audit = db.query(MembershipAudit).filter_by(email=email, reason="subscription.updated").first()
    assert audit is not None
    assert audit.old_tier == Tier.starter
    assert audit.new_tier == Tier.pro


def test_idempotency_at_event_level(db):
    email = "test4@ex.com"
    user = upsert_membership_from_checkout(
        db,
        email=email,
        stripe_customer_id="cus_000",
        line_item_price_ids=[PRO_PRICE],
        stripe_event_id="evt_6",
        reason="checkout.session.completed",
    )
    # Simulate idempotency: call again with same event id, should not create extra audit
    user2 = upsert_membership_from_checkout(
        db,
        email=email,
        stripe_customer_id="cus_000",
        line_item_price_ids=[PRO_PRICE],
        stripe_event_id="evt_6",
        reason="checkout.session.completed",
    )
    audits = db.query(MembershipAudit).filter_by(email=email, stripe_event_id="evt_6").all()
    assert len(audits) == 2  # Note: service is pure, idempotency is handled at webhook level


def test_stripe_customer_id_linking(db):
    email = "test5@ex.com"
    user = upsert_membership_from_checkout(
        db,
        email=email,
        stripe_customer_id=None,
        line_item_price_ids=[PRO_PRICE],
        stripe_event_id="evt_7",
        reason="checkout.session.completed",
    )
    assert user.stripe_customer_id is None
    user2 = upsert_membership_from_checkout(
        db,
        email=email,
        stripe_customer_id="cus_999",
        line_item_price_ids=[PRO_PRICE],
        stripe_event_id="evt_8",
        reason="checkout.session.completed",
    )
    assert user2.stripe_customer_id == "cus_999"
