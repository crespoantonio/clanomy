import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from src.db.models import Family, User, FamilyInvite
from src.core.subscription_config import (
    DAILY_FAIR_USE_LIMITS,
    FREE_TIER_MONTHLY_LIMIT,
    TRIAL_DURATION_DAYS
)
from src.services.subscription_service import (
    check_transaction_allowance,
    handle_successful_payment,
    handle_subscription_expiry
)
from src.services.family_service import FamilyService, PlanLimitExceededError
from src.services.messaging_service import MessagingService


@pytest.fixture
def memory_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    return engine


def test_trial_constants_and_daily_limits():
    """Verify that Trial is configured with 60 msgs/day pool and 60 days duration."""
    assert DAILY_FAIR_USE_LIMITS["trial"] == 60
    assert DAILY_FAIR_USE_LIMITS["duo_pro"] == 120
    assert DAILY_FAIR_USE_LIMITS["solo_pro"] == 60
    assert DAILY_FAIR_USE_LIMITS["family_pro"] == 300
    assert TRIAL_DURATION_DAYS == 60
    assert FREE_TIER_MONTHLY_LIMIT == 20


def test_messaging_service_provisions_duo_trial(memory_engine):
    """Verify new user receives a trial Family with max_members=2."""
    with Session(memory_engine) as session:
        messaging_service = MessagingService(session=session)
        user, family = messaging_service.get_or_create_user_and_family({
            "id": 123456789,
            "username": "duo_tester",
            "first_name": "Duo"
        })
        assert family.plan_type == "trial"
        assert family.max_members == 2
        assert family.trial_ends_at is not None
        assert user.is_admin is True
        assert user.has_used_trial is True


def test_create_family_provisions_duo_trial_vs_free(memory_engine):
    """Verify FamilyService.create_family sets max_members=2 on trial and max_members=5 on free."""
    service = FamilyService(engine=memory_engine)
    with Session(memory_engine) as session:
        # Create user
        user = User(
            id=uuid4(),
            telegram_id=200001,
            username="alice",
            has_used_trial=False
        )
        # Placeholder family
        init_fam = Family(id=uuid4(), name="Temp")
        session.add(init_fam)
        session.commit()
        user.family_id = init_fam.id
        session.add(user)
        session.commit()

        # User has not used trial -> gets Duo trial
        trial_fam = service.create_family(user_id=user.id, name="Alice Household")
        assert trial_fam.plan_type == "trial"
        assert trial_fam.max_members == 2

        # Second create_family call -> user has used trial -> gets Free with max_members=5
        free_fam = service.create_family(user_id=user.id, name="Alice Household Free")
        assert free_fam.plan_type == "free"
        assert free_fam.max_members == 5


def test_trial_invite_capacity_enforcement(memory_engine):
    """Verify trial workspaces can only invite 1 partner (max 2 members)."""
    service = FamilyService(engine=memory_engine)
    with Session(memory_engine) as session:
        trial_fam = Family(
            id=uuid4(),
            name="Trial Duo",
            plan_type="trial",
            max_members=2,
            subscription_status="active",
            trial_ends_at=datetime.now(timezone.utc) + timedelta(days=60)
        )
        session.add(trial_fam)
        session.commit()

        owner = User(id=uuid4(), telegram_id=300001, username="owner", family_id=trial_fam.id, is_admin=True)
        session.add(owner)
        session.commit()

        # 1 member: can generate invite
        invite, link = service.create_invite(family_id=trial_fam.id, user_id=owner.id)
        assert invite.token is not None

        # Add partner (now 2 members)
        partner = User(id=uuid4(), telegram_id=300002, username="partner", family_id=trial_fam.id, is_admin=False)
        session.add(partner)
        session.commit()

        # 2 members: generating invite must raise PlanLimitExceededError
        with pytest.raises(PlanLimitExceededError) as exc_info:
            service.create_invite(family_id=trial_fam.id, user_id=owner.id)
        assert "Duo Trial only supports up to 2 members" in str(exc_info.value)
        assert "Family Pro" in str(exc_info.value)


def test_join_family_via_invite_enforces_duo_trial_capacity(memory_engine):
    """Verify 3rd user cannot join a 2-member trial workspace via invite."""
    service = FamilyService(engine=memory_engine)
    with Session(memory_engine) as session:
        trial_fam = Family(
            id=uuid4(),
            name="Trial Duo",
            plan_type="trial",
            max_members=2,
            subscription_status="active",
            trial_ends_at=datetime.now(timezone.utc) + timedelta(days=60)
        )
        session.add(trial_fam)
        session.commit()

        u1 = User(id=uuid4(), telegram_id=400001, username="u1", family_id=trial_fam.id, is_admin=True)
        session.add(u1)
        session.commit()

        # Generate invite when at 1 member
        invite, link = service.create_invite(family_id=trial_fam.id, user_id=u1.id)

        # Partner joins
        u2_fam = Family(id=uuid4(), name="U2 Temp")
        session.add(u2_fam)
        session.commit()
        u2 = User(id=uuid4(), telegram_id=400002, username="u2", family_id=u2_fam.id)
        session.add(u2)
        session.commit()

        success, msg, fam = service.join_family_via_invite(token=invite.token, user_id=u2.id)
        assert success is True

        # Now workspace has 2 members. Third user attempts to join using same or another invite
        u3_fam = Family(id=uuid4(), name="U3 Temp")
        session.add(u3_fam)
        session.commit()
        u3 = User(id=uuid4(), telegram_id=400003, username="u3", family_id=u3_fam.id)
        session.add(u3)
        session.commit()

        # Manually create a valid unexpired invite token
        invite_overflow = FamilyInvite(
            family_id=trial_fam.id,
            created_by_user_id=u1.id,
            token="test_overflow_token",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24)
        )
        session.add(invite_overflow)
        session.commit()

        success, msg, fam = service.join_family_via_invite(token="test_overflow_token", user_id=u3.id)
        assert success is False
        assert "Duo Trial limit of 2 members" in msg


def test_activate_subscription_duo_pro_sets_max_members(memory_engine):
    """Verify handle_successful_payment sets max_members=2 for duo_pro."""
    with Session(memory_engine) as session:
        fam = Family(
            id=uuid4(),
            name="Upgrade Household",
            plan_type="free",
            max_members=5,
            subscription_status="active"
        )
        session.add(fam)
        session.commit()

        result = handle_successful_payment(
            session=session,
            family=fam,
            invoice_payload="sub_duo_pro"
        )
        assert result["family"].plan_type == "duo_pro"
        assert result["family"].max_members == 2


def test_handle_subscription_expiry_transitions_to_free_with_5_members(memory_engine):
    """Verify that expired trial transitions to Free tier with max_members=5."""
    with Session(memory_engine) as session:
        trial_fam = Family(
            id=uuid4(),
            name="Expiring Trial",
            plan_type="trial",
            max_members=2,
            subscription_status="active",
            trial_ends_at=datetime.now(timezone.utc) - timedelta(days=1)
        )
        session.add(trial_fam)
        session.commit()

        expired_fam = handle_subscription_expiry(session=session, family=trial_fam)
        assert expired_fam.plan_type == "free"
        assert expired_fam.subscription_status == "expired"
        assert expired_fam.max_members == 5
