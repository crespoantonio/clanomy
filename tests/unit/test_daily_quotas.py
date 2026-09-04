import pytest
from uuid import uuid4
from datetime import datetime, timezone
from sqlmodel import Session, create_engine, SQLModel
from sqlalchemy.pool import StaticPool

from src.db.models import Family, User
from src.core.subscription_config import (
    FREE_TIER_MONTHLY_LIMIT,
    DAILY_FAIR_USE_LIMITS
)
from src.services.subscription_service import (
    check_transaction_allowance,
    can_log_transaction,
    reset_daily_quotas
)
from src.core.config import settings


@pytest.fixture
def memory_session():
    """In-memory SQLite session with full schema initialized."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_free_tier_monthly_quota_enforced_and_never_daily():
    family = Family(
        name="Free Family",
        plan_type="free",
        subscription_status="active",
        monthly_tx_count=19,
        daily_tx_count=15
    )

    # 19 logs: allowed
    allowed, reason, limit = check_transaction_allowance(family)
    assert allowed is True
    assert reason is None

    # 20 logs: blocked by monthly limit
    family.monthly_tx_count = 20
    allowed, reason, limit = check_transaction_allowance(family)
    assert allowed is False
    assert reason == "monthly_limit"
    assert limit == 20


def test_solo_pro_daily_pool_enforced():
    family = Family(
        name="Solo Workspace",
        plan_type="solo_pro",
        subscription_status="active",
        monthly_tx_count=500,
        daily_tx_count=59
    )

    # 59 logs today: allowed
    allowed, reason, limit = check_transaction_allowance(family)
    assert allowed is True

    # 60 logs today: blocked by daily fair-use cap
    family.daily_tx_count = 60
    allowed, reason, limit = check_transaction_allowance(family)
    assert allowed is False
    assert reason == "daily_limit"
    assert limit == 60


def test_duo_pro_daily_pool_enforced():
    family = Family(
        name="Duo Workspace",
        plan_type="duo_pro",
        subscription_status="active",
        daily_tx_count=119
    )

    allowed, reason, limit = check_transaction_allowance(family)
    assert allowed is True

    family.daily_tx_count = 120
    allowed, reason, limit = check_transaction_allowance(family)
    assert allowed is False
    assert reason == "daily_limit"
    assert limit == 120


def test_family_pro_and_trial_daily_pool_enforced():
    family = Family(
        name="Household",
        plan_type="family_pro",
        subscription_status="active",
        daily_tx_count=299
    )

    allowed, reason, limit = check_transaction_allowance(family)
    assert allowed is True

    family.daily_tx_count = 300
    allowed, reason, limit = check_transaction_allowance(family)
    assert allowed is False
    assert reason == "daily_limit"
    assert limit == 300

    # 60-Day Trial receives 35/day
    from datetime import timedelta
    trial_fam = Family(
        name="Trial Household",
        plan_type="trial",
        subscription_status="active",
        trial_ends_at=datetime.now(timezone.utc) + timedelta(days=30),
        daily_tx_count=35
    )
    allowed, reason, limit = check_transaction_allowance(trial_fam)
    assert allowed is False
    assert reason == "daily_limit"
    assert limit == 35


def test_reset_daily_quotas_preserves_free_tier_monthly_count(memory_session):
    # Free family: 18 monthly logs, 5 today
    free_fam = Family(
        name="Free Family",
        plan_type="free",
        subscription_status="active",
        monthly_tx_count=18,
        daily_tx_count=5
    )
    # Pro family: 450 monthly logs, 58 today
    pro_fam = Family(
        name="Solo Pro",
        plan_type="solo_pro",
        subscription_status="active",
        monthly_tx_count=450,
        daily_tx_count=58
    )
    memory_session.add(free_fam)
    memory_session.add(pro_fam)
    memory_session.commit()

    # Trigger daily 10:00 UTC silent reset
    resets = reset_daily_quotas(memory_session)
    assert resets >= 1

    memory_session.refresh(free_fam)
    memory_session.refresh(pro_fam)

    # Pro family daily count is zeroed
    assert pro_fam.daily_tx_count == 0
    assert pro_fam.monthly_tx_count == 450

    # Free family monthly count is 100% PRESERVED!
    assert free_fam.monthly_tx_count == 18


def test_daily_limit_enforced_when_subscriptions_disabled():
    """Verifies that daily fair-use limits are enforced even in self-hosted / subscriptions-disabled mode."""
    original = settings.ENABLE_SUBSCRIPTIONS
    try:
        settings.ENABLE_SUBSCRIPTIONS = False

        family = Family(
            name="Self-Hosted Workspace",
            plan_type="solo_pro",
            subscription_status="active",
            daily_tx_count=59
        )

        # Under limit: allowed
        allowed, reason, limit = check_transaction_allowance(family)
        assert allowed is True
        assert reason is None
        assert limit == 60

        # At/Over limit: blocked by daily_limit even though ENABLE_SUBSCRIPTIONS=False
        family.daily_tx_count = 60
        allowed, reason, limit = check_transaction_allowance(family)
        assert allowed is False
        assert reason == "daily_limit"
        assert limit == 60

        # Free tier workspace in self-hosted mode also respects default daily limit (25)
        free_fam = Family(
            name="Free Self-Hosted",
            plan_type="free",
            subscription_status="active",
            daily_tx_count=25
        )
        allowed, reason, limit = check_transaction_allowance(free_fam)
        assert allowed is False
        assert reason == "daily_limit"
        assert limit == 25
    finally:
        settings.ENABLE_SUBSCRIPTIONS = original

