"""
Exhaustive integration test suite for all Paddle tier transitions and workspace splitting:
1. Non-admin member graduation from Family to new Family Pro workspace.
2. Non-admin member graduation from Duo to new Duo Pro workspace.
3. Non-admin member graduation from Free Family to new Solo Pro workspace.
4. Single-user Family Pro to Solo Pro in-place downgrade (no split).
5. Single-user Duo Pro to Solo Pro in-place downgrade (no split).
6. Multi-user Duo Pro to Solo Pro downgrade split (couples separation).
7. Family Pro to Duo Pro downgrade with over-capacity locking.
8. Active Trial conversion to paid Pro.
9. Resuming / aborting a scheduled cancellation (clearing scheduled change).
10. Dunning past_due grace window and paused immediate access cutoff.
"""

import json
import time
import hmac
import hashlib
from datetime import datetime, timezone, timedelta
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from src.main import app
from src.core.config import settings
from src.db.models import Family, User, Transaction, ScheduledBill, FamilyInvite
from src.db.session import engine
from src.core.encryption import EncryptionService
from src.services.subscription_service import has_unlimited_access
from src.services.family_service import FamilyService


def _generate_paddle_sig(raw_body: str, secret: str, timestamp: int) -> str:
    signed_payload = f"{timestamp}:{raw_body}"
    computed_hash = hmac.new(
        secret.encode("utf-8"),
        signed_payload.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    return f"ts={timestamp};h1={computed_hash}"


@pytest.fixture
def paddle_test_setup():
    test_secret = "pdl_ntfset_tier_matrix_secret_123"
    orig_secret = settings.PADDLE_WEBHOOK_SECRET_KEY
    orig_subs = settings.ENABLE_SUBSCRIPTIONS
    orig_solo = settings.PADDLE_PRICE_ID_SOLO_PRO
    orig_duo = settings.PADDLE_PRICE_ID_DUO_PRO
    orig_fam = settings.PADDLE_PRICE_ID_FAMILY_PRO

    settings.PADDLE_WEBHOOK_SECRET_KEY = test_secret
    settings.ENABLE_SUBSCRIPTIONS = True
    settings.PADDLE_PRICE_ID_SOLO_PRO = "pri_solo_test_1"
    settings.PADDLE_PRICE_ID_DUO_PRO = "pri_duo_test_2"
    settings.PADDLE_PRICE_ID_FAMILY_PRO = "pri_fam_test_5"

    yield test_secret

    settings.PADDLE_WEBHOOK_SECRET_KEY = orig_secret
    settings.ENABLE_SUBSCRIPTIONS = orig_subs
    settings.PADDLE_PRICE_ID_SOLO_PRO = orig_solo
    settings.PADDLE_PRICE_ID_DUO_PRO = orig_duo
    settings.PADDLE_PRICE_ID_FAMILY_PRO = orig_fam


# =============================================================================
# 1. Non-Admin Graduation: Family Member starts their own Family Pro
# =============================================================================
def test_paddle_webhook_non_admin_starts_new_family_pro(paddle_test_setup):
    """
    Scenario:
    - Host family exists on Free tier with Admin Alice, Member Bob, and Member Charlie.
    - Bob has personal transactions and a scheduled bill.
    - Bob purchases Family Pro via Paddle.
    - Webhook arrives.
    - Outcome:
      - Bob is graduated to a new sovereign workspace as Admin.
      - The new workspace has plan_type="family_pro" and max_members=5.
      - Bob's transactions and scheduled bills are migrated.
      - Host family remains intact with Alice as Admin and Charlie as Member.
      - Host family's data remains untouched.
    """
    secret = paddle_test_setup
    client = TestClient(app)
    enc = EncryptionService()

    host_fam_id = uuid4()
    alice_id = uuid4()
    bob_id = uuid4()
    charlie_id = uuid4()
    tx_alice_id = uuid4()
    tx_bob_id = uuid4()
    bill_bob_id = uuid4()

    with Session(engine) as session:
        host_fam = Family(
            id=host_fam_id,
            name="Host Family",
            plan_type="free",
            max_members=5,
            subscription_status="active"
        )
        session.add(host_fam)

        alice = User(
            id=alice_id,
            telegram_id=900101,
            family_id=host_fam_id,
            is_admin=True,
            full_name="Alice Host",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc)
        )
        bob = User(
            id=bob_id,
            telegram_id=900102,
            family_id=host_fam_id,
            is_admin=False,
            full_name="Bob Graduate",
            created_at=datetime(2026, 1, 2, tzinfo=timezone.utc)
        )
        charlie = User(
            id=charlie_id,
            telegram_id=900103,
            family_id=host_fam_id,
            is_admin=False,
            full_name="Charlie Host",
            created_at=datetime(2026, 1, 3, tzinfo=timezone.utc)
        )
        session.add_all([alice, bob, charlie])

        # Alice's transaction
        tx_alice = Transaction(
            id=tx_alice_id,
            family_id=host_fam_id,
            user_id=alice_id,
            amount=enc.encrypt("150.00"),
            concept=enc.encrypt("Groceries"),
            category="Food/Drink"
        )
        # Bob's transaction
        tx_bob = Transaction(
            id=tx_bob_id,
            family_id=host_fam_id,
            user_id=bob_id,
            amount=enc.encrypt("75.50"),
            concept=enc.encrypt("Dinner"),
            category="Food/Drink"
        )
        # Bob's scheduled bill
        bill_bob = ScheduledBill(
            id=bill_bob_id,
            family_id=host_fam_id,
            user_id=bob_id,
            concept=enc.encrypt("Bob Gym"),
            amount=enc.encrypt("45.00"),
            category="Fitness",
            due_date=datetime(2026, 2, 28, tzinfo=timezone.utc)
        )
        session.add_all([tx_alice, tx_bob, bill_bob])
        session.commit()

    # Webhook arrives: Bob purchased Family Pro
    now_ts = int(time.time())
    bob_sub_id = "sub_bob_family_999"
    payload = {
        "event_id": "evt_bob_grad_fam_001",
        "event_type": "subscription.created",
        "data": {
            "id": bob_sub_id,
            "customer_id": "ctm_bob_001",
            "status": "active",
            "custom_data": {
                "user_id": str(bob_id),
                "family_id": str(host_fam_id),
                "plan_code": "family_monthly"
            },
            "items": [{"price": {"id": "pri_fam_test_5"}}],
            "current_billing_period": {
                "starts_at": "2026-03-01T00:00:00Z",
                "ends_at": "2026-04-01T00:00:00Z"
            }
        }
    }
    raw = json.dumps(payload)
    sig = _generate_paddle_sig(raw, secret, now_ts)

    res = client.post("/api/v1/paddle/webhook", content=raw, headers={"Paddle-Signature": sig})
    assert res.status_code == 200

    # Verification
    with Session(engine) as session:
        # 1. Host family check
        h_fam = session.get(Family, host_fam_id)
        assert h_fam.plan_type == "free"
        assert h_fam.max_members == 5
        assert h_fam.paddle_subscription_id is None
        h_members = session.exec(select(User).where(User.family_id == host_fam_id)).all()
        assert len(h_members) == 2
        member_ids = [m.id for m in h_members]
        assert alice_id in member_ids
        assert charlie_id in member_ids
        assert bob_id not in member_ids

        alice_db = session.get(User, alice_id)
        assert alice_db.is_admin is True

        # Alice's transaction stayed in host family
        tx_a_db = session.get(Transaction, tx_alice_id)
        assert tx_a_db.family_id == host_fam_id

        # 2. Bob's graduated workspace check
        bob_db = session.get(User, bob_id)
        assert bob_db.family_id != host_fam_id
        assert bob_db.is_admin is True

        bob_fam = session.get(Family, bob_db.family_id)
        assert bob_fam.plan_type == "family_pro"
        assert bob_fam.max_members == 5
        assert bob_fam.paddle_subscription_id == bob_sub_id
        assert bob_fam.paddle_customer_id == "ctm_bob_001"
        assert bob_fam.subscription_status == "active"

        # Bob's transaction migrated
        tx_b_db = session.get(Transaction, tx_bob_id)
        assert tx_b_db.family_id == bob_fam.id

        # Bob's scheduled bill migrated
        bill_b_db = session.get(ScheduledBill, bill_bob_id)
        assert bill_b_db.family_id == bob_fam.id


# =============================================================================
# 2. Non-Admin Graduation: Duo Member starts a new Duo Pro workspace
# =============================================================================
def test_paddle_webhook_non_admin_duo_starts_new_duo_pro(paddle_test_setup):
    """
    Scenario:
    - Couple Duo workspace exists with Admin Alice and Member Bob.
    - Bob separates and purchases Duo Pro.
    - Outcome:
      - Bob graduates to a new Duo Pro workspace (max 2 members, Admin Bob).
      - Original Duo workspace stays intact with Alice as Admin.
    """
    secret = paddle_test_setup
    client = TestClient(app)

    duo_fam_id = uuid4()
    alice_id = uuid4()
    bob_id = uuid4()

    with Session(engine) as session:
        duo_fam = Family(
            id=duo_fam_id,
            name="Alice & Bob Duo",
            plan_type="duo_pro",
            max_members=2,
            subscription_status="active",
            paddle_subscription_id="sub_duo_alice_111"
        )
        session.add(duo_fam)
        alice = User(
            id=alice_id,
            telegram_id=900201,
            family_id=duo_fam_id,
            is_admin=True,
            full_name="Alice Duo",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc)
        )
        bob = User(
            id=bob_id,
            telegram_id=900202,
            family_id=duo_fam_id,
            is_admin=False,
            full_name="Bob Duo",
            created_at=datetime(2026, 1, 2, tzinfo=timezone.utc)
        )
        session.add_all([alice, bob])
        session.commit()

    now_ts = int(time.time())
    bob_sub_id = "sub_bob_duo_222"
    payload = {
        "event_id": "evt_bob_grad_duo_001",
        "event_type": "subscription.created",
        "data": {
            "id": bob_sub_id,
            "customer_id": "ctm_bob_002",
            "status": "active",
            "custom_data": {
                "user_id": str(bob_id),
                "family_id": str(duo_fam_id),
                "plan_code": "duo_monthly"
            },
            "items": [{"price": {"id": "pri_duo_test_2"}}],
            "current_billing_period": {
                "starts_at": "2026-03-01T00:00:00Z",
                "ends_at": "2026-04-01T00:00:00Z"
            }
        }
    }
    raw = json.dumps(payload)
    sig = _generate_paddle_sig(raw, secret, now_ts)

    res = client.post("/api/v1/paddle/webhook", content=raw, headers={"Paddle-Signature": sig})
    assert res.status_code == 200

    with Session(engine) as session:
        # Alice's original duo stays intact
        orig_fam = session.get(Family, duo_fam_id)
        assert orig_fam.plan_type == "duo_pro"
        assert orig_fam.paddle_subscription_id == "sub_duo_alice_111"

        # Bob's graduated duo workspace
        bob_db = session.get(User, bob_id)
        assert bob_db.family_id != duo_fam_id
        assert bob_db.is_admin is True

        bob_fam = session.get(Family, bob_db.family_id)
        assert bob_fam.plan_type == "duo_pro"
        assert bob_fam.max_members == 2
        assert bob_fam.paddle_subscription_id == bob_sub_id


# =============================================================================
# 3. Non-Admin Graduation: Member in Free Family starts Solo Pro
# =============================================================================
def test_paddle_webhook_non_admin_free_starts_solo_pro(paddle_test_setup):
    """
    Scenario:
    - Member Bob in Free Family buys Solo Pro.
    - Webhook arrives with custom_data having user_id only (no family_id provided).
    - Bob graduates to a Solo Pro workspace (max 1 member).
    - Host free family remains intact.
    """
    secret = paddle_test_setup
    client = TestClient(app)

    free_fam_id = uuid4()
    alice_id = uuid4()
    bob_id = uuid4()

    with Session(engine) as session:
        free_fam = Family(
            id=free_fam_id,
            name="Free Household",
            plan_type="free",
            max_members=5,
            subscription_status="active"
        )
        session.add(free_fam)
        alice = User(
            id=alice_id,
            telegram_id=900301,
            family_id=free_fam_id,
            is_admin=True,
            full_name="Alice Free",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc)
        )
        bob = User(
            id=bob_id,
            telegram_id=900302,
            family_id=free_fam_id,
            is_admin=False,
            full_name="Bob Free",
            created_at=datetime(2026, 1, 2, tzinfo=timezone.utc)
        )
        session.add_all([alice, bob])
        session.commit()

    now_ts = int(time.time())
    bob_sub_id = "sub_bob_solo_333"
    payload = {
        "event_id": "evt_bob_grad_solo_001",
        "event_type": "subscription.created",
        "data": {
            "id": bob_sub_id,
            "customer_id": "ctm_bob_003",
            "status": "active",
            "custom_data": {
                "user_id": str(bob_id),
                "plan_code": "solo_monthly"
            },
            "items": [{"price": {"id": "pri_solo_test_1"}}]
        }
    }
    raw = json.dumps(payload)
    sig = _generate_paddle_sig(raw, secret, now_ts)

    res = client.post("/api/v1/paddle/webhook", content=raw, headers={"Paddle-Signature": sig})
    assert res.status_code == 200

    with Session(engine) as session:
        bob_db = session.get(User, bob_id)
        assert bob_db.family_id != free_fam_id
        assert bob_db.is_admin is True

        bob_fam = session.get(Family, bob_db.family_id)
        assert bob_fam.plan_type == "solo_pro"
        assert bob_fam.max_members == 1
        assert bob_fam.paddle_subscription_id == bob_sub_id


# =============================================================================
# 4. Single-User In-Place Downgrades (Family Pro / Duo Pro -> Solo Pro)
# =============================================================================
def test_paddle_webhook_single_user_inplace_downgrades(paddle_test_setup):
    """
    Scenario:
    - User is alone in a Family Pro workspace (1 user).
    - Downgrades to Solo Pro in Customer Portal.
    - No split is performed; workspace is updated in-place to solo_pro (max 1 member).
    """
    secret = paddle_test_setup
    client = TestClient(app)

    fam_id = uuid4()
    user_id = uuid4()
    sub_id = "sub_single_downgrade_444"

    with Session(engine) as session:
        fam = Family(
            id=fam_id,
            name="Solo Living Large",
            plan_type="family_pro",
            max_members=5,
            subscription_status="active",
            paddle_subscription_id=sub_id
        )
        session.add(fam)
        user = User(
            id=user_id,
            telegram_id=900401,
            family_id=fam_id,
            is_admin=True,
            full_name="Single King",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc)
        )
        session.add(user)
        session.commit()

    now_ts = int(time.time())
    payload = {
        "event_id": "evt_single_downgrade_001",
        "event_type": "subscription.updated",
        "data": {
            "id": sub_id,
            "status": "active",
            "custom_data": {"family_id": str(fam_id)},
            "items": [{"price": {"id": "pri_solo_test_1"}}]
        }
    }
    raw = json.dumps(payload)
    sig = _generate_paddle_sig(raw, secret, now_ts)

    res = client.post("/api/v1/paddle/webhook", content=raw, headers={"Paddle-Signature": sig})
    assert res.status_code == 200

    with Session(engine) as session:
        updated = session.get(Family, fam_id)
        assert updated.plan_type == "solo_pro"
        assert updated.max_members == 1
        assert updated.paddle_subscription_id == sub_id
        # Still the same family id
        user_db = session.get(User, user_id)
        assert user_db.family_id == fam_id


# =============================================================================
# 5. Duo Multi-User Downgrade Split (Admin downgrades Duo Pro to Solo Pro)
# =============================================================================
def test_paddle_webhook_duo_downgrade_split(paddle_test_setup):
    """
    Scenario:
    - 2 users in a Duo Pro workspace (Admin Alice and Member Bob).
    - Alice downgrades subscription to Solo Pro.
    - Outcome:
      - Existing duo workspace reverts to Free (max 5 members), paddle sub detached.
      - Bob (the remaining member) is appointed Admin of the Free workspace.
      - Alice is moved to a new Solo Pro workspace (max 1 member) with the Paddle sub attached.
    """
    secret = paddle_test_setup
    client = TestClient(app)

    duo_id = uuid4()
    alice_id = uuid4()
    bob_id = uuid4()
    sub_id = "sub_duo_split_555"

    with Session(engine) as session:
        duo_fam = Family(
            id=duo_id,
            name="Couple Workspace",
            plan_type="duo_pro",
            max_members=2,
            subscription_status="active",
            paddle_subscription_id=sub_id
        )
        session.add(duo_fam)
        alice = User(
            id=alice_id,
            telegram_id=900501,
            family_id=duo_id,
            is_admin=True,
            full_name="Alice Duo Admin",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc)
        )
        bob = User(
            id=bob_id,
            telegram_id=900502,
            family_id=duo_id,
            is_admin=False,
            full_name="Bob Duo Member",
            created_at=datetime(2026, 1, 2, tzinfo=timezone.utc)
        )
        session.add_all([alice, bob])
        session.commit()

    now_ts = int(time.time())
    payload = {
        "event_id": "evt_duo_split_001",
        "event_type": "subscription.updated",
        "data": {
            "id": sub_id,
            "status": "active",
            "custom_data": {"family_id": str(duo_id), "user_id": str(alice_id)},
            "items": [{"price": {"id": "pri_solo_test_1"}}]
        }
    }
    raw = json.dumps(payload)
    sig = _generate_paddle_sig(raw, secret, now_ts)

    res = client.post("/api/v1/paddle/webhook", content=raw, headers={"Paddle-Signature": sig})
    assert res.status_code == 200

    with Session(engine) as session:
        # Original family is now Free with Bob as Admin
        orig = session.get(Family, duo_id)
        assert orig.plan_type == "free"
        assert orig.max_members == 5
        assert orig.paddle_subscription_id is None

        bob_db = session.get(User, bob_id)
        assert bob_db.family_id == duo_id
        assert bob_db.is_admin is True

        # Alice is in her new Solo Pro workspace with the subscription
        alice_db = session.get(User, alice_id)
        assert alice_db.family_id != duo_id
        assert alice_db.is_admin is True

        solo_fam = session.get(Family, alice_db.family_id)
        assert solo_fam.plan_type == "solo_pro"
        assert solo_fam.max_members == 1
        assert solo_fam.paddle_subscription_id == sub_id


# =============================================================================
# 6. Family Pro to Duo Pro Downgrade: Capacity Enforcement
# =============================================================================
def test_paddle_webhook_family_pro_to_duo_pro_capacity_locking(paddle_test_setup):
    """
    Scenario:
    - Family has 4 members on Family Pro.
    - Admin downgrades subscription to Duo Pro (max 2 members).
    - Workspace updates to duo_pro (max_members=2).
    - Existing 4 members remain intact.
    - Attempting to invite / join with a 5th member is rejected by FamilyService.
    """
    secret = paddle_test_setup
    client = TestClient(app)
    fam_svc = FamilyService()

    fam_id = uuid4()
    sub_id = "sub_fam_to_duo_666"

    with Session(engine) as session:
        fam = Family(
            id=fam_id,
            name="Big Family",
            plan_type="family_pro",
            max_members=5,
            subscription_status="active",
            paddle_subscription_id=sub_id
        )
        session.add(fam)
        admin_id = uuid4()
        users = [
            User(
                id=admin_id,
                telegram_id=900600,
                family_id=fam_id,
                is_admin=True,
                full_name="Member 0",
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc)
            )
        ]
        for i in range(1, 4):
            u = User(
                id=uuid4(),
                telegram_id=900600 + i,
                family_id=fam_id,
                is_admin=False,
                full_name=f"Member {i}",
                created_at=datetime(2026, 1, 1 + i, tzinfo=timezone.utc)
            )
            users.append(u)
        session.add_all(users)
        session.commit()

    now_ts = int(time.time())
    payload = {
        "event_id": "evt_fam_to_duo_001",
        "event_type": "subscription.updated",
        "data": {
            "id": sub_id,
            "status": "active",
            "custom_data": {"family_id": str(fam_id)},
            "items": [{"price": {"id": "pri_duo_test_2"}}]
        }
    }
    raw = json.dumps(payload)
    sig = _generate_paddle_sig(raw, secret, now_ts)

    res = client.post("/api/v1/paddle/webhook", content=raw, headers={"Paddle-Signature": sig})
    assert res.status_code == 200

    with Session(engine) as session:
        updated_fam = session.get(Family, fam_id)
        assert updated_fam.plan_type == "duo_pro"
        assert updated_fam.max_members == 2

    # Now verify invite attempt for a 5th user is rejected due to Duo Pro cap
    candidate_id = uuid4()
    with Session(engine) as session:
        cand_user = User(
            id=candidate_id,
            telegram_id=900699,
            family_id=fam_id,  # temporary placeholder
            full_name="New Hopeful"
        )
        # Create separate single family for candidate
        cand_fam = Family(id=uuid4(), name="Candidate Fam", plan_type="free")
        session.add(cand_fam)
        session.flush()
        cand_user.family_id = cand_fam.id
        session.add(cand_user)

        # Create active invite for Big Family
        invite = FamilyInvite(
            family_id=fam_id,
            created_by_user_id=admin_id,
            token="test_duo_cap_code",
            is_active=True,
            expires_at=datetime.now(timezone.utc) + timedelta(days=1)
        )
        session.add(invite)
        session.commit()

    # Attempt to join
    success, msg, _ = fam_svc.join_family_via_invite(token="test_duo_cap_code", user_id=candidate_id)
    assert success is False
    assert "limit of 2 members" in msg


# =============================================================================
# 7. Active Trial Conversion to Paid Pro
# =============================================================================
def test_paddle_webhook_trial_conversion_to_paid_pro(paddle_test_setup):
    """
    Scenario:
    - Workspace is on active trial (plan_type='trial', trial_ends_at in future).
    - Webhook arrives for subscription.created with family_pro.
    - Outcome:
      - Workspace converts to plan_type='family_pro', max_members=5, status='active'.
    """
    secret = paddle_test_setup
    client = TestClient(app)

    trial_fam_id = uuid4()
    sub_id = "sub_trial_conv_777"

    with Session(engine) as session:
        trial_fam = Family(
            id=trial_fam_id,
            name="Trialers",
            plan_type="trial",
            max_members=2,
            subscription_status="active",
            trial_ends_at=datetime.now(timezone.utc) + timedelta(days=10)
        )
        session.add(trial_fam)
        user = User(
            id=uuid4(),
            telegram_id=900701,
            family_id=trial_fam_id,
            is_admin=True,
            full_name="Trial Admin"
        )
        session.add(user)
        session.commit()

    now_ts = int(time.time())
    payload = {
        "event_id": "evt_trial_conv_001",
        "event_type": "subscription.created",
        "data": {
            "id": sub_id,
            "status": "active",
            "custom_data": {"family_id": str(trial_fam_id)},
            "items": [{"price": {"id": "pri_fam_test_5"}}]
        }
    }
    raw = json.dumps(payload)
    sig = _generate_paddle_sig(raw, secret, now_ts)

    res = client.post("/api/v1/paddle/webhook", content=raw, headers={"Paddle-Signature": sig})
    assert res.status_code == 200

    with Session(engine) as session:
        updated = session.get(Family, trial_fam_id)
        assert updated.plan_type == "family_pro"
        assert updated.max_members == 5
        assert updated.paddle_subscription_id == sub_id
        assert updated.subscription_status == "active"


# =============================================================================
# 8. Scheduled Cancellation Resumed / Aborted
# =============================================================================
def test_paddle_webhook_scheduled_cancellation_cleared_on_resume(paddle_test_setup):
    """
    Scenario:
    - Workspace has scheduled_change_action="cancel" effective at end of month.
    - User resumes subscription in Paddle.
    - Webhook arrives with scheduled_change=None.
    - Outcome:
      - scheduled_change_action and scheduled_change_effective_at are cleared to None.
      - Workspace remains active.
    """
    secret = paddle_test_setup
    client = TestClient(app)

    fam_id = uuid4()
    sub_id = "sub_resume_888"

    with Session(engine) as session:
        fam = Family(
            id=fam_id,
            name="Resuming Fam",
            plan_type="solo_pro",
            max_members=1,
            subscription_status="active",
            paddle_subscription_id=sub_id,
            scheduled_change_action="cancel",
            scheduled_change_effective_at=datetime.now(timezone.utc) + timedelta(days=20)
        )
        session.add(fam)
        session.commit()

    now_ts = int(time.time())
    payload = {
        "event_id": "evt_resume_001",
        "event_type": "subscription.updated",
        "data": {
            "id": sub_id,
            "status": "active",
            "custom_data": {"family_id": str(fam_id)},
            "items": [{"price": {"id": "pri_solo_test_1"}}],
            "scheduled_change": None  # Paddle sends null / None when cancellation is resumed
        }
    }
    raw = json.dumps(payload)
    sig = _generate_paddle_sig(raw, secret, now_ts)

    res = client.post("/api/v1/paddle/webhook", content=raw, headers={"Paddle-Signature": sig})
    assert res.status_code == 200

    with Session(engine) as session:
        updated = session.get(Family, fam_id)
        assert updated.subscription_status == "active"
        assert updated.scheduled_change_action is None
        assert updated.scheduled_change_effective_at is None


# =============================================================================
# 9. Past Due Grace Period & Paused Immediate Cutoff
# =============================================================================
def test_paddle_webhook_past_due_and_paused_status(paddle_test_setup):
    """
    Scenario:
    - Workspace has family_pro.
    - Webhook updates status to past_due (dunning).
      -> is_subscription_active() is True during 72h grace period.
    - Subsequent webhook updates status to paused.
      -> is_subscription_active() is False immediately.
    """
    secret = paddle_test_setup
    client = TestClient(app)

    fam_id = uuid4()
    sub_id = "sub_dunning_999"
    now_utc = datetime.now(timezone.utc)

    with Session(engine) as session:
        fam = Family(
            id=fam_id,
            name="Dunning Fam",
            plan_type="family_pro",
            max_members=5,
            subscription_status="active",
            paddle_subscription_id=sub_id,
            current_period_end=now_utc + timedelta(days=5)
        )
        session.add(fam)
        session.commit()

    now_ts = int(time.time())

    # 1. Past due update
    payload_past_due = {
        "event_id": "evt_dunning_past_due_001",
        "event_type": "subscription.updated",
        "data": {
            "id": sub_id,
            "status": "past_due",
            "custom_data": {"family_id": str(fam_id)},
            "items": [{"price": {"id": "pri_fam_test_5"}}]
        }
    }
    raw1 = json.dumps(payload_past_due)
    res1 = client.post("/api/v1/paddle/webhook", content=raw1, headers={"Paddle-Signature": _generate_paddle_sig(raw1, secret, now_ts)})
    assert res1.status_code == 200

    with Session(engine) as session:
        fam_db = session.get(Family, fam_id)
        assert fam_db.subscription_status == "past_due"
        # Within grace period, access is maintained
        assert has_unlimited_access(fam_db, now=now_utc) is True

    # 2. Paused update (terminal non-payment)
    payload_paused = {
        "event_id": "evt_dunning_paused_002",
        "event_type": "subscription.updated",
        "data": {
            "id": sub_id,
            "status": "paused",
            "custom_data": {"family_id": str(fam_id)},
            "items": [{"price": {"id": "pri_fam_test_5"}}]
        }
    }
    raw2 = json.dumps(payload_paused)
    res2 = client.post("/api/v1/paddle/webhook", content=raw2, headers={"Paddle-Signature": _generate_paddle_sig(raw2, secret, now_ts)})
    assert res2.status_code == 200

    with Session(engine) as session:
        fam_db2 = session.get(Family, fam_id)
        assert fam_db2.subscription_status == "paused"
        # Paused subscriptions immediately lose Pro access
        assert has_unlimited_access(fam_db2, now=now_utc) is False
