from typing import Dict, Optional, Set
from datetime import datetime, timezone
from src.db.models import Family

# Strict mapping of allowed Telegram Star invoice payloads to internal plan types
ALLOWED_PAID_PLANS: Dict[str, str] = {
    "sub_solo_pro": "solo_pro",
    "sub_family_pro": "family_pro",
}

VALID_PLAN_TYPES: Set[str] = {"free", "trial", "solo_pro", "family_pro", "lifetime_pro"}
VALID_SUBSCRIPTION_STATUSES: Set[str] = {"active", "cancelled", "expired"}

def is_unlimited_plan(plan_type: str) -> bool:
    """
    Returns True if the plan type provides unlimited transactions.
    """
    return plan_type in ("trial", "solo_pro", "family_pro", "lifetime_pro")

def has_unlimited_access(family: Family, now: Optional[datetime] = None) -> bool:
    """
    Helper to check if a family has unlimited access based on its current plan_type
    and subscription_status.
    For trial workspaces, verifies that trial_ends_at has not expired.
    """
    if family.subscription_status != "active":
        return False

    if family.plan_type in ("solo_pro", "family_pro", "lifetime_pro"):
        return True

    if family.plan_type == "trial":
        if family.trial_ends_at is not None:
            current_time = now or datetime.now(timezone.utc)
            # Handle potential tz-aware vs naive comparisons cleanly
            if family.trial_ends_at.tzinfo is None and current_time.tzinfo is not None:
                current_time = current_time.replace(tzinfo=None)
            elif family.trial_ends_at.tzinfo is not None and current_time.tzinfo is None:
                current_time = current_time.replace(tzinfo=timezone.utc)

            if current_time > family.trial_ends_at:
                return False
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

def can_log_transaction(family: Family, limit: int = 30, current_date: Optional[datetime] = None) -> bool:
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

def validate_invoice_payload(invoice_payload: str) -> str:
    """
    Validates an incoming webhook invoice payload.
    Extracts the plan type from payloads like 'sub_solo_pro' or 'sub_solo_pro_<family_id>'.
    Raises ValueError if unauthorized (e.g. attempting to set lifetime_pro) or if family_id is invalid.
    Returns the mapped internal plan_type.
    """
    if not invoice_payload:
        raise ValueError("Missing or empty subscription payload")

    if invoice_payload in ALLOWED_PAID_PLANS:
        return ALLOWED_PAID_PLANS[invoice_payload]

    import uuid
    for prefix, plan_type in ALLOWED_PAID_PLANS.items():
        if invoice_payload.startswith(f"{prefix}_"):
            family_id_str = invoice_payload[len(prefix)+1:]
            if family_id_str:
                try:
                    uuid.UUID(family_id_str)
                except ValueError:
                    raise ValueError(f"Invalid family_id format in payload: {invoice_payload}")
            return plan_type

    raise ValueError(f"Unauthorized or invalid subscription payload: {invoice_payload}")


