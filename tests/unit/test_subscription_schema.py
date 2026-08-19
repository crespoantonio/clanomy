import pytest
from datetime import datetime, timezone
from src.db.models import Family
from src.services.subscription_service import has_unlimited_access, can_log_transaction, validate_invoice_payload

def test_family_default_values():
    """Test that a new Family model has the correct default subscription values."""
    family = Family(name="Test Family")
    assert family.plan_type == "free"
    assert family.subscription_status == "active"
    assert family.monthly_tx_count == 0
    assert family.current_period_end is None
    assert family.telegram_payment_charge_id is None

def test_has_unlimited_access():
    """Test unlimited access helper across different plan types and statuses."""
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

def test_can_log_transaction():
    """Test transaction quota logic for free vs pro tiers."""
    # Free tier under quota
    family_free = Family(plan_type="free", subscription_status="active", monthly_tx_count=29)
    assert can_log_transaction(family_free, limit=30)
    
    # Free tier at/over quota
    family_free.monthly_tx_count = 30
    assert not can_log_transaction(family_free, limit=30)
    
    # Pro tier at/over arbitrary quota (should still be allowed)
    family_pro = Family(plan_type="family_pro", subscription_status="active", monthly_tx_count=999)
    assert can_log_transaction(family_pro, limit=30)

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
