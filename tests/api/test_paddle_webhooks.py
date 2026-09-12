"""
Integration and security tests for Paddle Billing webhook endpoint.
Covers:
- Self-hosted vs SaaS mode isolation.
- HMAC-SHA256 signature verification & forgery rejection.
- Timestamp drift & replay attack prevention.
- Event deduplication / idempotency ledger.
- Subscription lifecycle transitions (created, updated with scheduled change, canceled).
- Transaction completion and customer association.
"""

import json
import time
import hmac
import hashlib
from datetime import datetime, timezone, timedelta
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from src.main import app
from src.core.config import settings
from src.db.models import Family, ProcessedWebhook
from src.db.session import engine


def _generate_paddle_signature(raw_body: str, secret: str, timestamp: int) -> str:
    """Helper to generate a valid Paddle-Signature header."""
    signed_payload = f"{timestamp}:{raw_body}"
    computed_hash = hmac.new(
        secret.encode("utf-8"),
        signed_payload.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    return f"ts={timestamp};h1={computed_hash}"


@pytest.fixture
def paddle_test_setup():
    """Configures Paddle test secrets and settings."""
    test_secret = "pdl_ntfset_test_secret_123456789"
    original_secret = settings.PADDLE_WEBHOOK_SECRET_KEY
    original_subs = settings.ENABLE_SUBSCRIPTIONS

    settings.PADDLE_WEBHOOK_SECRET_KEY = test_secret
    settings.ENABLE_SUBSCRIPTIONS = True

    yield test_secret

    settings.PADDLE_WEBHOOK_SECRET_KEY = original_secret
    settings.ENABLE_SUBSCRIPTIONS = original_subs


def test_paddle_webhook_disabled_in_self_hosted():
    """Verify webhook endpoint returns 404 when ENABLE_SUBSCRIPTIONS is False."""
    settings.ENABLE_SUBSCRIPTIONS = False
    client = TestClient(app)

    response = client.post(
        "/api/v1/paddle/webhook",
        content="{}",
        headers={"Paddle-Signature": "ts=123;h1=abc"}
    )
    assert response.status_code == 404
    assert "Subscriptions are disabled" in response.json().get("detail", "")


def test_paddle_webhook_missing_signature(paddle_test_setup):
    """Verify webhook rejects requests without signature or body."""
    client = TestClient(app)

    # Missing header
    res1 = client.post("/api/v1/paddle/webhook", content='{"event_id": "evt_1"}')
    assert res1.status_code == 400

    # Missing body
    res2 = client.post("/api/v1/paddle/webhook", content="", headers={"Paddle-Signature": "ts=123;h1=abc"})
    assert res2.status_code == 400


def test_paddle_webhook_invalid_signature(paddle_test_setup):
    """Verify webhook rejects tampered payloads or forged signatures with 401."""
    client = TestClient(app)
    raw_body = json.dumps({"event_id": "evt_tampered", "event_type": "subscription.created"})

    # Forged header
    res = client.post(
        "/api/v1/paddle/webhook",
        content=raw_body,
        headers={"Paddle-Signature": f"ts={int(time.time())};h1=bad_hash_value"}
    )
    assert res.status_code == 401
    assert "Invalid signature" in res.json().get("detail", "")


def test_paddle_webhook_replay_attack_tolerance(paddle_test_setup):
    """Verify webhook rejects timestamps older than 5 seconds."""
    secret = paddle_test_setup
    client = TestClient(app)
    raw_body = json.dumps({"event_id": "evt_old", "event_type": "subscription.created"})

    # Timestamp 10 seconds in the past
    expired_ts = int(time.time()) - 10
    sig = _generate_paddle_signature(raw_body, secret, expired_ts)

    res = client.post(
        "/api/v1/paddle/webhook",
        content=raw_body,
        headers={"Paddle-Signature": sig}
    )
    assert res.status_code == 401


def test_paddle_webhook_subscription_created(paddle_test_setup):
    """Verify subscription.created updates Family tier, member cap, and IDs."""
    secret = paddle_test_setup
    client = TestClient(app)

    # 1. Create a Family in database
    family_id = uuid4()
    with Session(engine) as session:
        family = Family(
            id=family_id,
            name="Test Family",
            plan_type="free",
            subscription_status="active",
            max_members=5
        )
        session.add(family)
        session.commit()

    # 2. Craft subscription.created payload
    now_ts = int(time.time())
    period_end_dt = datetime.now(timezone.utc) + timedelta(days=30)
    payload = {
        "event_id": "evt_sub_created_001",
        "event_type": "subscription.created",
        "data": {
            "id": "sub_paddle_001",
            "customer_id": "ctm_paddle_001",
            "status": "active",
            "custom_data": {
                "family_id": str(family_id),
                "plan_code": "solo_pro"
            },
            "items": [
                {
                    "price": {"id": "pri_solo_001"}
                }
            ],
            "current_billing_period": {
                "ends_at": period_end_dt.isoformat()
            }
        }
    }
    raw_body = json.dumps(payload)
    sig = _generate_paddle_signature(raw_body, secret, now_ts)

    # 3. Post webhook
    res = client.post(
        "/api/v1/paddle/webhook",
        content=raw_body,
        headers={"Paddle-Signature": sig}
    )
    assert res.status_code == 200
    assert res.json() == {"received": True}

    # 4. Verify DB updates
    with Session(engine) as session:
        updated_family = session.get(Family, family_id)
        assert updated_family.paddle_subscription_id == "sub_paddle_001"
        assert updated_family.paddle_customer_id == "ctm_paddle_001"
        assert updated_family.paddle_price_id == "pri_solo_001"
        assert updated_family.plan_type == "solo_pro"
        assert updated_family.max_members == 1
        assert updated_family.subscription_status == "active"
        assert updated_family.current_period_end is not None

        # Verify idempotency ledger entry
        webhook_entry = session.get(ProcessedWebhook, "evt_sub_created_001")
        assert webhook_entry is not None
        assert webhook_entry.event_type == "subscription.created"


def test_paddle_webhook_idempotency(paddle_test_setup):
    """Verify duplicate deliveries return 200 and avoid double-processing."""
    secret = paddle_test_setup
    client = TestClient(app)

    family_id = uuid4()
    with Session(engine) as session:
        family = Family(id=family_id, name="Idempotent Family", plan_type="free")
        session.add(family)
        session.commit()

    now_ts = int(time.time())
    payload = {
        "event_id": "evt_duplicate_002",
        "event_type": "subscription.created",
        "data": {
            "id": "sub_dup_001",
            "customer_id": "ctm_dup_001",
            "status": "active",
            "custom_data": {"family_id": str(family_id), "plan_code": "duo_pro"}
        }
    }
    raw_body = json.dumps(payload)
    sig = _generate_paddle_signature(raw_body, secret, now_ts)

    # First delivery
    res1 = client.post("/api/v1/paddle/webhook", content=raw_body, headers={"Paddle-Signature": sig})
    assert res1.status_code == 200
    assert res1.json() == {"received": True}

    # Second delivery (retry with same event_id)
    res2 = client.post("/api/v1/paddle/webhook", content=raw_body, headers={"Paddle-Signature": sig})
    assert res2.status_code == 200
    assert res2.json() == {"received": True, "duplicate": True}


def test_paddle_webhook_subscription_updated_scheduled_cancel(paddle_test_setup):
    """Verify scheduled cancellation keeps status active and records effective date."""
    secret = paddle_test_setup
    client = TestClient(app)

    family_id = uuid4()
    with Session(engine) as session:
        family = Family(
            id=family_id,
            paddle_subscription_id="sub_cancel_001",
            plan_type="family_pro",
            subscription_status="active",
            max_members=5
        )
        session.add(family)
        session.commit()

    now_ts = int(time.time())
    cancel_effective_at = (datetime.now(timezone.utc) + timedelta(days=15)).isoformat()
    payload = {
        "event_id": "evt_sub_updated_cancel_003",
        "event_type": "subscription.updated",
        "data": {
            "id": "sub_cancel_001",
            "status": "active",
            "scheduled_change": {
                "action": "cancel",
                "effective_at": cancel_effective_at
            }
        }
    }
    raw_body = json.dumps(payload)
    sig = _generate_paddle_signature(raw_body, secret, now_ts)

    res = client.post("/api/v1/paddle/webhook", content=raw_body, headers={"Paddle-Signature": sig})
    assert res.status_code == 200

    with Session(engine) as session:
        updated_family = session.get(Family, family_id)
        # Status remains active until effective_at
        assert updated_family.subscription_status == "active"
        assert updated_family.scheduled_change_action == "cancel"
        assert updated_family.scheduled_change_effective_at is not None


def test_paddle_webhook_subscription_canceled(paddle_test_setup):
    """Verify subscription.canceled updates status to canceled."""
    secret = paddle_test_setup
    client = TestClient(app)

    family_id = uuid4()
    with Session(engine) as session:
        family = Family(
            id=family_id,
            paddle_subscription_id="sub_terminal_001",
            plan_type="solo_pro",
            subscription_status="active"
        )
        session.add(family)
        session.commit()

    now_ts = int(time.time())
    payload = {
        "event_id": "evt_sub_canceled_004",
        "event_type": "subscription.canceled",
        "data": {
            "id": "sub_terminal_001",
            "status": "canceled"
        }
    }
    raw_body = json.dumps(payload)
    sig = _generate_paddle_signature(raw_body, secret, now_ts)

    res = client.post("/api/v1/paddle/webhook", content=raw_body, headers={"Paddle-Signature": sig})
    assert res.status_code == 200

    with Session(engine) as session:
        updated_family = session.get(Family, family_id)
        assert updated_family.subscription_status == "canceled"
        assert updated_family.scheduled_change_action is None


def test_paddle_webhook_transaction_completed(paddle_test_setup):
    """Verify transaction.completed links customer and transaction ID."""
    secret = paddle_test_setup
    client = TestClient(app)

    family_id = uuid4()
    with Session(engine) as session:
        family = Family(id=family_id, name="Tx Family")
        session.add(family)
        session.commit()

    now_ts = int(time.time())
    payload = {
        "event_id": "evt_tx_completed_005",
        "event_type": "transaction.completed",
        "data": {
            "id": "txn_paddle_001",
            "customer_id": "ctm_paddle_002",
            "status": "completed",
            "custom_data": {"family_id": str(family_id)}
        }
    }
    raw_body = json.dumps(payload)
    sig = _generate_paddle_signature(raw_body, secret, now_ts)

    res = client.post("/api/v1/paddle/webhook", content=raw_body, headers={"Paddle-Signature": sig})
    assert res.status_code == 200

    with Session(engine) as session:
        updated_family = session.get(Family, family_id)
        assert updated_family.paddle_customer_id == "ctm_paddle_002"
        assert updated_family.telegram_payment_charge_id == "txn_paddle_001"


def test_paddle_webhook_activation_notification_to_admin(paddle_test_setup):
    """Verify subscription activation notification is sent ONLY to the paying admin."""
    from unittest.mock import patch, AsyncMock
    from src.db.models import User

    secret = paddle_test_setup
    client = TestClient(app)

    family_id = uuid4()
    admin_user_id = uuid4()
    member_user_id = uuid4()

    with Session(engine) as session:
        family = Family(id=family_id, name="Pro Family", plan_type="free")
        session.add(family)
        admin_user = User(
            id=admin_user_id,
            telegram_id=987654321,
            family_id=family_id,
            is_admin=True,
            username="admin_tony"
        )
        member_user = User(
            id=member_user_id,
            telegram_id=123456789,
            family_id=family_id,
            is_admin=False,
            username="member_jane"
        )
        session.add(admin_user)
        session.add(member_user)
        session.commit()

    now_ts = int(time.time())
    payload = {
        "event_id": "evt_sub_created_notify_001",
        "event_type": "subscription.created",
        "data": {
            "id": "sub_act_001",
            "customer_id": "ctm_act_001",
            "status": "active",
            "current_billing_period": {
                "starts_at": "2026-09-01T00:00:00Z",
                "ends_at": "2026-10-01T00:00:00Z"
            },
            "custom_data": {
                "family_id": str(family_id),
                "user_id": str(admin_user_id),
                "plan_code": "solo_pro"
            }
        }
    }
    raw_body = json.dumps(payload)
    sig = _generate_paddle_signature(raw_body, secret, now_ts)

    with patch("src.services.telegram_service.TelegramService.send_message", new_callable=AsyncMock) as mock_send:
        res = client.post("/api/v1/paddle/webhook", content=raw_body, headers={"Paddle-Signature": sig})
        assert res.status_code == 200

        # Must be called ONLY for the admin who paid
        assert mock_send.call_count == 1
        called_chat_id = mock_send.call_args.kwargs.get("chat_id")
        called_text = mock_send.call_args.kwargs.get("text")
        assert called_chat_id == 987654321
        assert "Solo Pro" in called_text
        assert "/billing" in called_text


def test_paddle_webhook_scheduled_cancellation_broadcasts_to_all_members(paddle_test_setup):
    """Verify scheduled cancellation is broadcast to ALL family members with expiration date and free tier details."""
    from unittest.mock import patch, AsyncMock
    from src.db.models import User

    secret = paddle_test_setup
    client = TestClient(app)

    family_id = uuid4()
    admin_user_id = uuid4()
    member_user_id = uuid4()

    with Session(engine) as session:
        family = Family(
            id=family_id,
            name="Canceling Family",
            plan_type="family_pro",
            subscription_status="active",
            paddle_subscription_id="sub_canceling_002"
        )
        session.add(family)
        admin_user = User(
            id=admin_user_id,
            telegram_id=987654321,
            family_id=family_id,
            is_admin=True,
            username="admin_tony"
        )
        member_user = User(
            id=member_user_id,
            telegram_id=123456789,
            family_id=family_id,
            is_admin=False,
            username="member_jane"
        )
        session.add(admin_user)
        session.add(member_user)
        session.commit()

    now_ts = int(time.time())
    payload = {
        "event_id": "evt_sub_sched_cancel_002",
        "event_type": "subscription.updated",
        "data": {
            "id": "sub_canceling_002",
            "status": "active",
            "current_billing_period": {
                "ends_at": "2026-10-15T00:00:00Z"
            },
            "scheduled_change": {
                "action": "cancel",
                "effective_at": "2026-10-15T00:00:00Z"
            },
            "custom_data": {
                "family_id": str(family_id)
            }
        }
    }
    raw_body = json.dumps(payload)
    sig = _generate_paddle_signature(raw_body, secret, now_ts)

    with patch("src.services.telegram_service.TelegramService.send_message", new_callable=AsyncMock) as mock_send:
        res = client.post("/api/v1/paddle/webhook", content=raw_body, headers={"Paddle-Signature": sig})
        assert res.status_code == 200

        # Broadcasted to BOTH users
        assert mock_send.call_count == 2
        notified_chats = {call.kwargs.get("chat_id") for call in mock_send.call_args_list}
        assert notified_chats == {987654321, 123456789}

        # Check message content
        sample_text = mock_send.call_args_list[0].kwargs.get("text")
        assert "Family Pro" in sample_text
        assert "Free" in sample_text
        from src.core.subscription_config import FREE_TIER_MONTHLY_LIMIT
        assert str(FREE_TIER_MONTHLY_LIMIT) in sample_text
        assert "/upgrade" in sample_text


def test_paddle_webhook_routine_renewal_does_not_resend_welcome_message(paddle_test_setup):
    """Verify routine renewal (same plan, active status) does NOT resend welcome notification."""
    from unittest.mock import patch, AsyncMock
    from src.db.models import User

    secret = paddle_test_setup
    client = TestClient(app)

    family_id = uuid4()
    admin_user_id = uuid4()

    with Session(engine) as session:
        family = Family(
            id=family_id,
            name="Ongoing Family",
            plan_type="solo_pro",
            subscription_status="active",
            paddle_subscription_id="sub_renewal_003"
        )
        session.add(family)
        admin_user = User(
            id=admin_user_id,
            telegram_id=987654321,
            family_id=family_id,
            is_admin=True,
            username="admin_tony"
        )
        session.add(admin_user)
        session.commit()

    now_ts = int(time.time())
    payload = {
        "event_id": "evt_sub_renewal_003",
        "event_type": "subscription.updated",
        "data": {
            "id": "sub_renewal_003",
            "status": "active",
            "current_billing_period": {
                "starts_at": "2026-10-01T00:00:00Z",
                "ends_at": "2026-11-01T00:00:00Z"
            },
            "custom_data": {
                "family_id": str(family_id),
                "plan_code": "solo_pro"
            }
        }
    }
    raw_body = json.dumps(payload)
    sig = _generate_paddle_signature(raw_body, secret, now_ts)

    with patch("src.services.telegram_service.TelegramService.send_message", new_callable=AsyncMock) as mock_send:
        res = client.post("/api/v1/paddle/webhook", content=raw_body, headers={"Paddle-Signature": sig})
        assert res.status_code == 200
        # Routine renewal should NOT send any activation notification
        assert mock_send.call_count == 0


def test_paddle_webhook_full_upgrade_downgrade_cancel_lifecycle(paddle_test_setup):
    """
    Comprehensive verification of the entire customer payment and tier lifecycle:
    1. Initial State: Free tier family with Admin Alice and Member Bob.
    2. Upgrade: Admin Alice upgrades to Solo Pro -> family becomes solo_pro (max 1 user).
    3. Change: Upgrades to Family Pro -> family becomes family_pro (max 5 users), Bob is present.
    4. Downgrade: Downgrades to Solo Pro with multiple members:
       - Existing family stays Free (max 5 members).
       - Oldest non-admin (Bob) is promoted to Admin of the Free family.
       - Admin Alice is separated into a dedicated Solo Pro workspace (max 1 member) with Paddle sub attached.
       - Alice's personal transactions are migrated to her new Solo workspace (zero crosstalk).
    5. Upgrade Back: Alice upgrades her Solo workspace back to Family Pro -> becomes family_pro (max 5).
    6. Scheduled Cancellation: Cancellation scheduled mid-period -> status active, action=cancel.
    7. Terminal Cancellation: Subscription expires/canceled -> status canceled, plan reverts to free.
    """
    from unittest.mock import patch, AsyncMock
    from src.db.models import User, Transaction

    secret = paddle_test_setup
    client = TestClient(app)

    f1_id = uuid4()
    alice_id = uuid4()
    bob_id = uuid4()
    t_alice_id = uuid4()
    t_bob_id = uuid4()

    # 1. Initial State: Free family with Alice (Admin) and Bob (Member)
    with Session(engine) as session:
        f1 = Family(
            id=f1_id,
            name="The Smiths",
            plan_type="free",
            subscription_status="active",
            max_members=5
        )
        session.add(f1)
        alice = User(
            id=alice_id,
            telegram_id=1111101,
            family_id=f1_id,
            is_admin=True,
            full_name="Alice Smith",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc)
        )
        session.add(alice)
        bob = User(
            id=bob_id,
            telegram_id=2222202,
            family_id=f1_id,
            is_admin=False,
            full_name="Bob Smith",
            created_at=datetime(2026, 1, 2, tzinfo=timezone.utc)
        )
        session.add(bob)

        # Add initial transactions
        from src.core.encryption import EncryptionService
        enc = EncryptionService()
        t_alice = Transaction(
            id=t_alice_id,
            family_id=f1_id,
            user_id=alice_id,
            amount=enc.encrypt("50.00"),
            concept=enc.encrypt("Groceries"),
            category="Food/Drink"
        )
        t_bob = Transaction(
            id=t_bob_id,
            family_id=f1_id,
            user_id=bob_id,
            amount=enc.encrypt("25.00"),
            concept=enc.encrypt("Cinema"),
            category="Entertainment"
        )
        session.add(t_alice)
        session.add(t_bob)
        session.commit()

    sub_id = "sub_lifecycle_999"
    cust_id = "ctm_lifecycle_999"
    now_ts = int(time.time())

    with patch("src.services.telegram_service.TelegramService.send_message", new_callable=AsyncMock) as mock_tg:
        # ---------------------------------------------------------------------
        # Phase 1: Upgrade to Family Pro
        # ---------------------------------------------------------------------
        payload_upgrade_fam = {
            "event_id": "evt_lc_001",
            "event_type": "subscription.created",
            "data": {
                "id": sub_id,
                "customer_id": cust_id,
                "status": "active",
                "custom_data": {"family_id": str(f1_id), "user_id": str(alice_id), "plan_code": "family_pro"},
                "items": [{"price": {"id": "pri_family_pro_001"}}],
                "current_billing_period": {"ends_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()}
            }
        }
        raw = json.dumps(payload_upgrade_fam)
        res = client.post("/api/v1/paddle/webhook", content=raw, headers={"Paddle-Signature": _generate_paddle_signature(raw, secret, now_ts)})
        assert res.status_code == 200

        with Session(engine) as session:
            f = session.get(Family, f1_id)
            assert f.plan_type == "family_pro"
            assert f.max_members == 5
            assert f.paddle_subscription_id == sub_id
            assert f.subscription_status == "active"

        # ---------------------------------------------------------------------
        # Phase 2: Downgrade from Family Pro to Solo Pro with Multiple Members
        # ---------------------------------------------------------------------
        payload_downgrade_solo = {
            "event_id": "evt_lc_002",
            "event_type": "subscription.updated",
            "data": {
                "id": sub_id,
                "customer_id": cust_id,
                "status": "active",
                "custom_data": {"family_id": str(f1_id), "user_id": str(alice_id), "plan_code": "solo_pro"},
                "items": [{"price": {"id": "pri_solo_pro_001"}}],
                "current_billing_period": {"ends_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()}
            }
        }
        raw = json.dumps(payload_downgrade_solo)
        res = client.post("/api/v1/paddle/webhook", content=raw, headers={"Paddle-Signature": _generate_paddle_signature(raw, secret, now_ts)})
        assert res.status_code == 200

        solo_fam_id = None
        with Session(engine) as session:
            # 1. Verify Existing Family (F1)
            f1_db = session.get(Family, f1_id)
            assert f1_db.plan_type == "free"
            assert f1_db.max_members == 5
            assert f1_db.paddle_subscription_id is None
            assert f1_db.subscription_status == "active"

            # Bob should now be the new Admin of F1
            bob_db = session.get(User, bob_id)
            assert bob_db.family_id == f1_id
            assert bob_db.is_admin is True

            # Bob's transaction remained in F1
            t_bob_db = session.get(Transaction, t_bob_id)
            assert t_bob_db.family_id == f1_id

            # 2. Verify New Solo Family (Alice)
            alice_db = session.get(User, alice_id)
            assert alice_db.family_id != f1_id
            assert alice_db.is_admin is True
            solo_fam_id = alice_db.family_id

            solo_fam = session.get(Family, solo_fam_id)
            assert solo_fam.plan_type == "solo_pro"
            assert solo_fam.max_members == 1
            assert solo_fam.paddle_subscription_id == sub_id
            assert solo_fam.paddle_customer_id == cust_id
            assert solo_fam.subscription_status == "active"

            # Alice's transaction was migrated to her new Solo workspace
            t_alice_db = session.get(Transaction, t_alice_id)
            assert t_alice_db.family_id == solo_fam_id

        # ---------------------------------------------------------------------
        # Phase 3: Upgrade Solo Workspace back to Family Pro
        # ---------------------------------------------------------------------
        payload_upgrade_back = {
            "event_id": "evt_lc_003",
            "event_type": "subscription.updated",
            "data": {
                "id": sub_id,
                "customer_id": cust_id,
                "status": "active",
                "custom_data": {"family_id": str(solo_fam_id), "user_id": str(alice_id), "plan_code": "family_pro"},
                "items": [{"price": {"id": "pri_family_pro_001"}}],
                "current_billing_period": {"ends_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()}
            }
        }
        raw = json.dumps(payload_upgrade_back)
        res = client.post("/api/v1/paddle/webhook", content=raw, headers={"Paddle-Signature": _generate_paddle_signature(raw, secret, now_ts)})
        assert res.status_code == 200

        with Session(engine) as session:
            solo_fam_db = session.get(Family, solo_fam_id)
            assert solo_fam_db.plan_type == "family_pro"
            assert solo_fam_db.max_members == 5
            assert solo_fam_db.subscription_status == "active"

        # ---------------------------------------------------------------------
        # Phase 4: Scheduled Cancellation mid-period
        # ---------------------------------------------------------------------
        cancel_effective = (datetime.now(timezone.utc) + timedelta(days=14)).isoformat()
        payload_sched_cancel = {
            "event_id": "evt_lc_004",
            "event_type": "subscription.updated",
            "data": {
                "id": sub_id,
                "customer_id": cust_id,
                "status": "active",
                "scheduled_change": {
                    "action": "cancel",
                    "effective_at": cancel_effective
                }
            }
        }
        raw = json.dumps(payload_sched_cancel)
        res = client.post("/api/v1/paddle/webhook", content=raw, headers={"Paddle-Signature": _generate_paddle_signature(raw, secret, now_ts)})
        assert res.status_code == 200

        with Session(engine) as session:
            solo_fam_db = session.get(Family, solo_fam_id)
            assert solo_fam_db.subscription_status == "active"
            assert solo_fam_db.scheduled_change_action == "cancel"
            assert solo_fam_db.scheduled_change_effective_at is not None

        # ---------------------------------------------------------------------
        # Phase 5: Terminal Cancellation (Period Ends)
        # ---------------------------------------------------------------------
        payload_canceled = {
            "event_id": "evt_lc_005",
            "event_type": "subscription.canceled",
            "data": {
                "id": sub_id,
                "status": "canceled"
            }
        }
        raw = json.dumps(payload_canceled)
        res = client.post("/api/v1/paddle/webhook", content=raw, headers={"Paddle-Signature": _generate_paddle_signature(raw, secret, now_ts)})
        assert res.status_code == 200

        with Session(engine) as session:
            solo_fam_db = session.get(Family, solo_fam_id)
            assert solo_fam_db.subscription_status == "canceled"
            assert solo_fam_db.plan_type == "free"
            assert solo_fam_db.max_members == 5
            assert solo_fam_db.scheduled_change_action is None


def test_paddle_webhook_portal_price_change_precedence(paddle_test_setup, monkeypatch):
    """
    Verify that when a user updates their plan in the Paddle Customer Portal,
    items[0].price.id takes precedence over stale custom_data.plan_code.
    """
    secret = paddle_test_setup
    client = TestClient(app)

    configured_fam_price = "pri_live_family_pro_abc"
    monkeypatch.setattr(settings, "PADDLE_PRICE_ID_FAMILY_PRO", configured_fam_price)

    family_id = uuid4()
    with Session(engine) as session:
        family = Family(
            id=family_id,
            name="Portal Family",
            plan_type="solo_pro",
            max_members=1,
            paddle_subscription_id="sub_portal_001"
        )
        session.add(family)
        session.commit()

    now_ts = int(time.time())
    # Payload has stale plan_code "solo_pro" in custom_data, but new price_id for family_pro
    payload = {
        "event_id": "evt_portal_precedence_001",
        "event_type": "subscription.updated",
        "data": {
            "id": "sub_portal_001",
            "status": "active",
            "custom_data": {"family_id": str(family_id), "plan_code": "solo_pro"},
            "items": [{"price": {"id": configured_fam_price}}]
        }
    }
    raw = json.dumps(payload)
    sig = _generate_paddle_signature(raw, secret, now_ts)

    res = client.post("/api/v1/paddle/webhook", content=raw, headers={"Paddle-Signature": sig})
    assert res.status_code == 200

    with Session(engine) as session:
        updated = session.get(Family, family_id)
        # Authoritative price_id updated workspace to family_pro despite stale custom_data
        assert updated.plan_type == "family_pro"
        assert updated.max_members == 5
        assert updated.paddle_price_id == configured_fam_price

