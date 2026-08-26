import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from src.db.models import Family, User
from src.services.subscription_service import (
    can_log_transaction,
    has_unlimited_access,
    check_and_reset_monthly_quota,
    is_unlimited_plan,
)

def test_has_unlimited_access_pro_and_trial():
    # Active trial
    f_trial = Family(
        plan_type="trial",
        subscription_status="active",
        trial_ends_at=datetime.now(timezone.utc) + timedelta(days=30)
    )
    assert has_unlimited_access(f_trial) is True

    # Expired trial
    f_trial_expired = Family(
        plan_type="trial",
        subscription_status="active",
        trial_ends_at=datetime.now(timezone.utc) - timedelta(days=1)
    )
    assert has_unlimited_access(f_trial_expired) is False

    # Pro plans
    for p in ["solo_pro", "family_pro", "lifetime_pro"]:
        f_pro = Family(plan_type=p, subscription_status="active")
        assert has_unlimited_access(f_pro) is True

    # Inactive pro plan without period end
    f_cancelled_no_end = Family(plan_type="family_pro", subscription_status="cancelled", current_period_end=None)
    assert has_unlimited_access(f_cancelled_no_end) is False

    # Cancelled pro plan with future period end -> retains access
    f_cancelled_valid = Family(
        plan_type="family_pro",
        subscription_status="cancelled",
        current_period_end=datetime.now(timezone.utc) + timedelta(days=15)
    )
    assert has_unlimited_access(f_cancelled_valid) is True

    # Cancelled pro plan with expired period end -> no access
    f_cancelled_expired = Family(
        plan_type="family_pro",
        subscription_status="cancelled",
        current_period_end=datetime.now(timezone.utc) - timedelta(days=1)
    )
    assert has_unlimited_access(f_cancelled_expired) is False

    # Expired plan -> no access
    f_expired = Family(
        plan_type="free",
        subscription_status="expired",
        current_period_end=datetime.now(timezone.utc) - timedelta(days=1)
    )
    assert has_unlimited_access(f_expired) is False

def test_can_log_transaction_free_tier_limits():
    # Free tier under 30
    f_free = Family(plan_type="free", monthly_tx_count=10, last_reset_month=datetime.now(timezone.utc).strftime("%Y-%m"))
    assert can_log_transaction(f_free) is True

    # Free tier at limit 30
    f_free_max = Family(plan_type="free", monthly_tx_count=30, last_reset_month=datetime.now(timezone.utc).strftime("%Y-%m"))
    assert can_log_transaction(f_free_max) is False

    # Free tier beyond limit
    f_free_over = Family(plan_type="free", monthly_tx_count=35, last_reset_month=datetime.now(timezone.utc).strftime("%Y-%m"))
    assert can_log_transaction(f_free_over) is False

def test_can_log_transaction_lazy_monthly_reset():
    # Month is old -> should reset to 0 and allow transaction
    last_month_str = (datetime.now(timezone.utc) - timedelta(days=35)).strftime("%Y-%m")
    current_month_str = datetime.now(timezone.utc).strftime("%Y-%m")

    f_reset = Family(plan_type="free", monthly_tx_count=30, last_reset_month=last_month_str)
    assert can_log_transaction(f_reset) is True
    assert f_reset.monthly_tx_count == 0
    assert f_reset.last_reset_month == current_month_str

def test_validate_invoice_payload():
    from src.services.subscription_service import validate_invoice_payload

    # Exact match
    assert validate_invoice_payload("sub_solo_pro") == "solo_pro"
    assert validate_invoice_payload("sub_family_pro") == "family_pro"

    # Prefixed match with family_id
    assert validate_invoice_payload("sub_solo_pro_123e4567-e89b-12d3-a456-426614174000") == "solo_pro"
    assert validate_invoice_payload("sub_family_pro_custom-fam-id") == "family_pro"

    # Invalid / Unauthorized payloads
    with pytest.raises(ValueError, match="Unauthorized or invalid subscription payload"):
        validate_invoice_payload("sub_lifetime_pro")

    with pytest.raises(ValueError, match="Unauthorized or invalid subscription payload"):
        validate_invoice_payload("invalid_payload")

def test_extract_plan_and_family_id():
    from src.services.subscription_service import extract_plan_and_family_id

    plan, fam_id = extract_plan_and_family_id("sub_solo_pro")
    assert plan == "solo_pro"
    assert fam_id is None

    plan, fam_id = extract_plan_and_family_id("sub_family_pro_123e4567-e89b-12d3-a456-426614174000")
    assert plan == "family_pro"
    assert fam_id == "123e4567-e89b-12d3-a456-426614174000"

    with pytest.raises(ValueError):
        extract_plan_and_family_id("sub_lifetime_pro")

def test_handle_successful_payment_lifecycle():
    from sqlmodel import Session, create_engine, SQLModel
    from sqlalchemy.pool import StaticPool
    from src.services.subscription_service import handle_successful_payment

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        family = Family(plan_type="free", subscription_status="active", max_members=5)
        session.add(family)
        session.commit()
        session.refresh(family)

        # Upgrade to Solo Pro
        res = handle_successful_payment(
            session=session,
            family=family,
            invoice_payload=f"sub_solo_pro_{family.id}",
            charge_id="tg_charge_111"
        )
        assert res["status"] == "upgraded"
        assert family.plan_type == "solo_pro"
        assert family.subscription_status == "active"
        assert family.max_members == 1
        assert family.telegram_payment_charge_id == "tg_charge_111"
        assert family.current_period_end is not None

        # Upgrade to Family Pro
        res2 = handle_successful_payment(
            session=session,
            family=family,
            invoice_payload=f"sub_family_pro_{family.id}",
            charge_id="tg_charge_222"
        )
        assert res2["status"] == "upgraded"
        assert family.plan_type == "family_pro"
        assert family.subscription_status == "active"
        assert family.max_members == 5
        assert family.telegram_payment_charge_id == "tg_charge_222"

def test_handle_successful_payment_protects_lifetime_pro():
    from sqlmodel import Session, create_engine, SQLModel
    from sqlalchemy.pool import StaticPool
    from src.services.subscription_service import handle_successful_payment

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        family = Family(plan_type="lifetime_pro", subscription_status="active", max_members=10)
        session.add(family)
        session.commit()
        session.refresh(family)

        res = handle_successful_payment(
            session=session,
            family=family,
            invoice_payload=f"sub_solo_pro_{family.id}",
            charge_id="tg_charge_333"
        )
        assert res["status"] == "ignored_lifetime"
        assert family.plan_type == "lifetime_pro"
        assert family.subscription_status == "active"
        assert family.max_members == 10
        assert family.telegram_payment_charge_id == "tg_charge_333"

def test_handle_recurring_renewal_and_cancellation():
    from sqlmodel import Session, create_engine, SQLModel
    from sqlalchemy.pool import StaticPool
    from src.services.subscription_service import (
        handle_recurring_renewal,
        handle_subscription_cancellation,
        handle_subscription_expiry,
        handle_payment_failure
    )

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        now = datetime.now(timezone.utc)
        family = Family(
            plan_type="family_pro",
            subscription_status="active",
            current_period_end=now + timedelta(days=5),
            max_members=5
        )
        session.add(family)
        session.commit()
        session.refresh(family)

        # Recurring renewal extends period end
        renewed = handle_recurring_renewal(session, family, charge_id="charge_renew_1", now=now)
        assert renewed.subscription_status == "active"
        assert renewed.telegram_payment_charge_id == "charge_renew_1"
        renewed_end = renewed.current_period_end.replace(tzinfo=timezone.utc) if renewed.current_period_end.tzinfo is None else renewed.current_period_end
        assert renewed_end > now + timedelta(days=30)

        # Cancellation sets status to cancelled while retaining period end
        period_end_before = renewed.current_period_end
        cancelled = handle_subscription_cancellation(session, family)
        assert cancelled.subscription_status == "cancelled"
        assert cancelled.plan_type == "family_pro"
        assert cancelled.current_period_end == period_end_before

        # Expiry sets status to expired and plan_type to free
        expired = handle_subscription_expiry(session, family)
        assert expired.subscription_status == "expired"
        assert expired.plan_type == "free"

        # Payment failure transitions to free and expired
        failed = handle_payment_failure(session, family)
        assert failed.subscription_status == "expired"
        assert failed.plan_type == "free"


