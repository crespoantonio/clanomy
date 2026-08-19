from typing import Dict
from src.db.models import Family

# Strict mapping of allowed Telegram Star invoice payloads to internal plan types
ALLOWED_PAID_PLANS: Dict[str, str] = {
    "sub_solo_pro": "solo_pro",
    "sub_family_pro": "family_pro",
}

def is_unlimited_plan(plan_type: str) -> bool:
    """
    Returns True if the plan type provides unlimited transactions.
    """
    return plan_type in ("solo_pro", "family_pro", "lifetime_pro")

def has_unlimited_access(family: Family) -> bool:
    """
    Helper to check if a family has unlimited access based on its current plan_type
    and subscription_status. 
    """
    if family.subscription_status != "active":
        return False
    return is_unlimited_plan(family.plan_type)

def can_log_transaction(family: Family, limit: int = 30) -> bool:
    """
    Determines if a family is allowed to log a new transaction.
    """
    if has_unlimited_access(family):
        return True
    
    # Free tier logic
    if family.plan_type == "free" and family.monthly_tx_count < limit:
        return True
        
    return False

def validate_invoice_payload(invoice_payload: str) -> str:
    """
    Validates an incoming webhook invoice payload.
    Raises ValueError if unauthorized (e.g. attempting to set lifetime_pro).
    Returns the mapped internal plan_type.
    """
    if invoice_payload not in ALLOWED_PAID_PLANS:
        raise ValueError(f"Unauthorized or invalid subscription payload: {invoice_payload}")
    return ALLOWED_PAID_PLANS[invoice_payload]
