import pytest
from datetime import datetime, timezone, timedelta
import uuid
from src.db.models import Family, User
from src.services.subscription_service import (
    has_unlimited_access,
    can_log_transaction,
    validate_invoice_payload,
    check_and_reset_monthly_quota,
    is_unlimited_plan,
)

def test_family_default_values():
    """Test that a new Family model has the correct default subscription values."""
    family = Family(name="Test Family")
    assert family.plan_type == "free"
    assert family.subscription_status == "active"
    assert family.monthly_tx_count == 0
    assert family.last_reset_month is None
    assert family.max_members == 5
    assert family.trial_ends_at is None
    assert family.current_period_end is None
    assert family.telegram_payment_charge_id is None
    assert family.notified_day_50 is False
    assert family.notified_day_60 is False

def test_user_default_values():
    """Test that a new User model has the correct default has_used_trial value."""
    user = User(telegram_id=12345, family_id=uuid.uuid4())
    assert user.has_used_trial is False

def test_is_unlimited_plan():
    """Test is_unlimited_plan recognizing trial and pro tiers."""
    assert not is_unlimited_plan("free")
    assert is_unlimited_plan("trial")
    assert is_unlimited_plan("solo_pro")
    assert is_unlimited_plan("family_pro")
    assert is_unlimited_plan("lifetime_pro")

def test_has_unlimited_access():
    """Test unlimited access helper across different plan types, trials, and statuses."""
    # Free
    family_free = Family(plan_type="free", subscription_status="active")
    assert not has_unlimited_access(family_free)
    
    # Solo Pro
    family_solo = Family(plan_type="solo_pro", subscription_status="active")
    assert has_unlimited_access(family_solo)
    
    # Family Pro
    family_pro = Family(plan_type="family_pro", subscription_status="active")
    assert has_unlimited_access(family_pro)
    
    # Lifetime Pro
    family_lifetime = Family(plan_type="lifetime_pro", subscription_status="active")
    assert has_unlimited_access(family_lifetime)
    
    # Inactive subscriptions
    family_expired = Family(plan_type="family_pro", subscription_status="expired")
    assert not has_unlimited_access(family_expired)

    # Active 60-day trial (trial_ends_at in the future)
    future_time = datetime.now(timezone.utc) + timedelta(days=30)
    family_trial_active = Family(
        plan_type="trial",
        subscription_status="active",
        trial_ends_at=future_time
    )
    assert has_unlimited_access(family_trial_active)

    # Expired trial (trial_ends_at in the past)
    past_time = datetime.now(timezone.utc) - timedelta(days=1)
    family_trial_expired = Family(
        plan_type="trial",
        subscription_status="active",
        trial_ends_at=past_time
    )
    assert not has_unlimited_access(family_trial_expired)

    # Cancelled trial
    family_trial_cancelled = Family(
        plan_type="trial",
        subscription_status="cancelled",
        trial_ends_at=future_time
    )
    assert not has_unlimited_access(family_trial_cancelled)

def test_can_log_transaction():
    """Test transaction quota logic for free vs pro vs trial tiers."""
    # Free tier under quota
    family_free = Family(plan_type="free", subscription_status="active", monthly_tx_count=29)
    assert can_log_transaction(family_free, limit=30)
    
    # Free tier at/over quota
    family_free.monthly_tx_count = 30
    assert not can_log_transaction(family_free, limit=30)
    
    # Pro tier at/over arbitrary quota (should still be allowed)
    family_pro = Family(plan_type="family_pro", subscription_status="active", monthly_tx_count=999)
    assert can_log_transaction(family_pro, limit=30)

    # Active Trial tier at/over arbitrary quota (should still be allowed)
    future_time = datetime.now(timezone.utc) + timedelta(days=20)
    family_trial = Family(plan_type="trial", subscription_status="active", trial_ends_at=future_time, monthly_tx_count=999)
    assert can_log_transaction(family_trial, limit=30)

def test_lazy_monthly_quota_reset():
    """Test zero-cron lazy monthly counter reset behavior."""
    # Month 1: Jul 2026, hit limit
    family = Family(
        plan_type="free",
        subscription_status="active",
        monthly_tx_count=30,
        last_reset_month="2026-07"
    )
    
    jul_date = datetime(2026, 7, 31, 23, 59, 0, tzinfo=timezone.utc)
    assert not can_log_transaction(family, limit=30, current_date=jul_date)
    assert family.monthly_tx_count == 30
    assert family.last_reset_month == "2026-07"

    # Month 2: Aug 2026, new month initiates lazy reset
    aug_date = datetime(2026, 8, 1, 0, 1, 0, tzinfo=timezone.utc)
    assert can_log_transaction(family, limit=30, current_date=aug_date)
    assert family.monthly_tx_count == 0
    assert family.last_reset_month == "2026-08"

def test_check_and_reset_monthly_quota():
    """Test standalone helper for checking and resetting monthly quota."""
    family = Family(plan_type="free", monthly_tx_count=15, last_reset_month="2026-07")
    
    # Same month: no reset
    reset_same = check_and_reset_monthly_quota(family, current_date=datetime(2026, 7, 20, tzinfo=timezone.utc))
    assert reset_same is False
    assert family.monthly_tx_count == 15
    assert family.last_reset_month == "2026-07"

    # Next month: resets
    reset_next = check_and_reset_monthly_quota(family, current_date=datetime(2026, 8, 1, tzinfo=timezone.utc))
    assert reset_next is True
    assert family.monthly_tx_count == 0
    assert family.last_reset_month == "2026-08"

def test_validate_invoice_payload():
    """Test webhook payload whitelist to ensure lifetime_pro cannot be injected."""
    # Valid payloads
    assert validate_invoice_payload("sub_solo_pro") == "solo_pro"
    assert validate_invoice_payload("sub_family_pro") == "family_pro"
    
    # Invalid or malicious payloads
    with pytest.raises(ValueError, match="Unauthorized or invalid subscription payload"):
        validate_invoice_payload("sub_lifetime_pro")
        
    with pytest.raises(ValueError):
        validate_invoice_payload("lifetime_pro")
        
    with pytest.raises(ValueError):
        validate_invoice_payload("free")

    with pytest.raises(ValueError):
        validate_invoice_payload("trial")

