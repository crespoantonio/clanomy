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

    # Inactive pro plan
    f_cancelled = Family(plan_type="family_pro", subscription_status="cancelled")
    assert has_unlimited_access(f_cancelled) is False

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
