import re
from typing import Dict, Optional, Set, Tuple, Any
from datetime import datetime, timezone, timedelta
from sqlmodel import Session
from src.db.models import Family
from src.core.config import settings

from src.core.subscription_config import (
    SUBSCRIPTION_TIERS,
    SubscriptionTier,
    FREE_TIER_MONTHLY_LIMIT,
    TRIAL_DURATION_DAYS,
    get_tier_config
)

# Strict mapping of allowed Telegram Star invoice payloads to internal plan types
ALLOWED_PAID_PLANS: Dict[str, str] = {
    f"sub_{code}": tier.internal_plan
    for code, tier in SUBSCRIPTION_TIERS.items()
}

VALID_PLAN_TYPES: Set[str] = {"free", "trial", "solo_pro", "family_pro", "lifetime_pro"}
VALID_SUBSCRIPTION_STATUSES: Set[str] = {"active", "cancelled", "expired"}

def _compare_datetimes(target_dt: Optional[datetime], current_dt: datetime) -> bool:
    """Helper to safely compare tz-aware or naive datetimes."""
    if target_dt is None:
        return False
    if target_dt.tzinfo is None and current_dt.tzinfo is not None:
        target_dt = target_dt.replace(tzinfo=timezone.utc)
    elif target_dt.tzinfo is not None and current_dt.tzinfo is None:
        current_dt = current_dt.replace(tzinfo=timezone.utc)
    return current_dt <= target_dt

def is_unlimited_plan(plan_type: str) -> bool:
    """
    Returns True if the plan type provides unlimited transactions.
    """
    return plan_type in ("trial", "solo_pro", "family_pro", "lifetime_pro")

def has_unlimited_access(family: Family, now: Optional[datetime] = None) -> bool:
    """
    Helper to check if a family has unlimited access based on its current plan_type
    and subscription_status.
    - If ENABLE_SUBSCRIPTIONS is False (Self-Hosted mode): always returns True.
    - For active lifetime_pro, solo_pro, family_pro: unlimited access.
    - For active trial workspaces: verifies that trial_ends_at has not expired.
    - For cancelled subscriptions: retains Pro access until current_period_end.
    - For expired or free subscriptions: no unlimited access.
    """
    if not settings.ENABLE_SUBSCRIPTIONS:
        return True

    current_time = now or datetime.now(timezone.utc)

    # Cancelled subscriptions retain Pro access until their paid current_period_end
    if family.subscription_status == "cancelled":
        if family.plan_type in ("solo_pro", "family_pro", "lifetime_pro") and family.current_period_end is not None:
            return _compare_datetimes(family.current_period_end, current_time)
        return False

    if family.subscription_status != "active":
        return False

    if family.plan_type in ("solo_pro", "family_pro", "lifetime_pro"):
        return True

    if family.plan_type == "trial":
        if family.trial_ends_at is not None:
            return _compare_datetimes(family.trial_ends_at, current_time)
        return True

    return False

def check_and_reset_monthly_quota(family: Family, current_date: Optional[datetime] = None) -> bool:
    """
    Checks if a new calendar month has started based on family.last_reset_month.
    If the month has changed (or last_reset_month is None), resets monthly_tx_count to 0
    and updates last_reset_month to current 'YYYY-MM'.
    Returns True if a reset occurred, False otherwise.
    """
    now = current_date or datetime.now(timezone.utc)
    current_month_str = now.strftime("%Y-%m")
    if family.last_reset_month != current_month_str:
        family.monthly_tx_count = 0
        family.last_reset_month = current_month_str
        return True
    return False

def can_log_transaction(family: Family, limit: int = FREE_TIER_MONTHLY_LIMIT, current_date: Optional[datetime] = None) -> bool:
    """
    Determines if a family is allowed to log a new transaction.
    Performs lazy monthly counter reset if month has changed.
    """
    if has_unlimited_access(family, now=current_date):
        return True
    
    # Check for lazy monthly reset
    check_and_reset_monthly_quota(family, current_date=current_date)
    
    # Free tier logic
    if family.plan_type == "free" and family.monthly_tx_count < limit:
        return True
        
    return False

def extract_plan_and_family_id(invoice_payload: str) -> Tuple[str, Optional[str]]:
    """
    Extracts (plan_type, family_id_str) from an invoice payload.
    Raises ValueError if unauthorized or invalid.
    """
    if not invoice_payload:
        raise ValueError("Missing or empty subscription payload")

    if invoice_payload in ALLOWED_PAID_PLANS:
        return ALLOWED_PAID_PLANS[invoice_payload], None

    for prefix, plan_type in sorted(ALLOWED_PAID_PLANS.items(), key=lambda x: len(x[0]), reverse=True):
        if invoice_payload.startswith(f"{prefix}_"):
            family_id_str = invoice_payload[len(prefix)+1:]
            if family_id_str:
                if not re.match(r'^[a-zA-Z0-9_-]+$', family_id_str):
                    raise ValueError(f"Invalid family_id format in payload: {invoice_payload}")
                return plan_type, family_id_str
            return plan_type, None

    raise ValueError(f"Unauthorized or invalid subscription payload: {invoice_payload}")

def validate_invoice_payload(invoice_payload: str) -> str:
    """
    Validates an incoming webhook invoice payload.
    Extracts the plan type from payloads like 'sub_solo_pro' or 'sub_solo_pro_<family_id>'.
    Raises ValueError if unauthorized (e.g. attempting to set lifetime_pro) or if family_id is invalid.
    Returns the mapped internal plan_type.
    """
    plan_type, _ = extract_plan_and_family_id(invoice_payload)
    return plan_type

def handle_successful_payment(
    session: Session,
    family: Family,
    invoice_payload: str,
    charge_id: Optional[str] = None,
    expiration_timestamp: Optional[int] = None,
    now: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Processes a successful payment event for a family workspace.
    - Validates payload against whitelist.
    - Protects lifetime_pro workspaces from accidental downgrades.
    - Updates plan_type to 'solo_pro' (max 1 member) or 'family_pro' (max 5 members).
    - Sets subscription_status = 'active'.
    - Sets current_period_end (30 days from now or expiration timestamp).
    - Records telegram_payment_charge_id.
    """
    target_plan = validate_invoice_payload(invoice_payload)

    # Protect lifetime_pro
    if family.plan_type == "lifetime_pro":
        if charge_id:
            family.telegram_payment_charge_id = charge_id
        session.add(family)
        session.commit()
        session.refresh(family)
        return {"status": "ignored_lifetime", "plan_type": "lifetime_pro", "family": family}

    family.plan_type = target_plan
    family.subscription_status = "active"

    if target_plan == "solo_pro":
        family.max_members = 1
    elif target_plan == "family_pro":
        family.max_members = 5

    # Determine period duration from matching tier config (longest prefix match)
    duration_days = 30
    for code, tier in sorted(SUBSCRIPTION_TIERS.items(), key=lambda x: len(x[0]), reverse=True):
        if invoice_payload == f"sub_{code}" or invoice_payload.startswith(f"sub_{code}_"):
            duration_days = tier.duration_days
            break

    current_time = now or datetime.now(timezone.utc)
    if expiration_timestamp:
        family.current_period_end = datetime.fromtimestamp(expiration_timestamp, tz=timezone.utc)
    else:
        family.current_period_end = current_time + timedelta(days=duration_days)

    if charge_id:
        family.telegram_payment_charge_id = charge_id

    session.add(family)
    session.commit()
    session.refresh(family)

    return {"status": "upgraded", "plan_type": target_plan, "family": family}

def handle_recurring_renewal(
    session: Session,
    family: Family,
    charge_id: Optional[str] = None,
    expiration_timestamp: Optional[int] = None,
    now: Optional[datetime] = None
) -> Family:
    """
    Processes a recurring subscription renewal.
    Extends current_period_end by 30 days and ensures subscription_status = 'active'.
    """
    if family.plan_type == "lifetime_pro":
        return family

    family.subscription_status = "active"
    current_time = now or datetime.now(timezone.utc)

    if expiration_timestamp:
        family.current_period_end = datetime.fromtimestamp(expiration_timestamp, tz=timezone.utc)
    else:
        # Extend from current period end if in the future, otherwise from now
        base_time = current_time
        if family.current_period_end:
            target_dt = family.current_period_end
            if target_dt.tzinfo is None and base_time.tzinfo is not None:
                base_time_cmp = base_time.replace(tzinfo=None)
            elif target_dt.tzinfo is not None and base_time.tzinfo is None:
                base_time_cmp = base_time.replace(tzinfo=timezone.utc)
            else:
                base_time_cmp = base_time

            if target_dt > base_time_cmp:
                base_time = target_dt

        if base_time.tzinfo is None:
            base_time = base_time.replace(tzinfo=timezone.utc)

        family.current_period_end = base_time + timedelta(days=30)

    if charge_id:
        family.telegram_payment_charge_id = charge_id

    session.add(family)
    session.commit()
    session.refresh(family)
    return family

def handle_subscription_cancellation(session: Session, family: Family) -> Family:
    """
    Marks subscription as cancelled while preserving current_period_end.
    Pro features remain active until current_period_end.
    """
    if family.plan_type == "lifetime_pro":
        return family

    family.subscription_status = "cancelled"
    session.add(family)
    session.commit()
    session.refresh(family)
    return family

def handle_subscription_expiry(session: Session, family: Family) -> Family:
    """
    Marks subscription as expired and transitions workspace to the Free tier.
    """
    if family.plan_type == "lifetime_pro":
        return family

    family.subscription_status = "expired"
    family.plan_type = "free"
    family.max_members = 5
    session.add(family)
    session.commit()
    session.refresh(family)
    return family

def handle_payment_failure(session: Session, family: Family) -> Family:
    """
    Handles payment failure by marking subscription expired and falling back to free tier.
    """
    return handle_subscription_expiry(session, family)



