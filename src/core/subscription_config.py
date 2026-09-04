from dataclasses import dataclass
from typing import Dict, Optional

@dataclass(frozen=True)
class SubscriptionTier:
    """
    Unified specification for a subscription plan tier.
    Centralizes pricing (USD), duration (monthly/yearly), member limits, and features.
    """
    code: str                         # e.g. "solo_pro", "solo_pro_annual", "family_pro", "family_pro_annual"
    internal_plan: str                # Target DB plan_type on Family model: "solo_pro" or "family_pro"
    title: str                        # Display title on checkout & messages
    description: str                  # Short marketing description
    price_display: str                # Display price string (e.g. "$4.99 / month")
    price_usd_cents: int              # Price in USD cents (e.g. 499 for $4.99)
    duration_days: int                # Period duration in days (e.g. 30 for monthly, 365 for annual)
    max_members: int                  # Workspace member capacity (1 for Solo, 2 for Duo, 5 for Family)
    notion_enabled: bool              # Whether Notion database mirroring is enabled
    billing_period_name: str          # "month" or "year"

# Global Free Tier & Trial Constants
FREE_TIER_MONTHLY_LIMIT: int = 20
TRIAL_DURATION_DAYS: int = 60

# Fair-Use Daily Message Rate Limits (Shared Workspace Pool for Pro/Trial)
DAILY_FAIR_USE_LIMITS: Dict[str, int] = {
    "solo_pro": 60,
    "duo_pro": 120,
    "family_pro": 300,
    "trial": 60,
    "lifetime_pro": 40
}
DEFAULT_DAILY_LIMIT: int = 25

# Centralized Subscription Registry
SUBSCRIPTION_TIERS: Dict[str, SubscriptionTier] = {
    "solo_pro": SubscriptionTier(
        code="solo_pro",
        internal_plan="solo_pro",
        title="Clanomy Solo Pro",
        description="⭐️ 60 daily AI extractions, Notion sync & smart queries for 1 user.",
        price_display="$4.99 / month",
        price_usd_cents=499,
        duration_days=30,
        max_members=1,
        notion_enabled=True,
        billing_period_name="month"
    ),
    "duo_pro": SubscriptionTier(
        code="duo_pro",
        internal_plan="duo_pro",
        title="Clanomy Duo Pro",
        description="⭐️ 120 daily AI extractions, Notion sync & shared ledger for 2 partners / couples.",
        price_display="$7.99 / month",
        price_usd_cents=799,
        duration_days=30,
        max_members=2,
        notion_enabled=True,
        billing_period_name="month"
    ),
    "family_pro": SubscriptionTier(
        code="family_pro",
        internal_plan="family_pro",
        title="Clanomy Family Pro",
        description="⭐️ 300 daily AI extractions, Notion sync & shared ledger for up to 5 family members.",
        price_display="$11.99 / month",
        price_usd_cents=1199,
        duration_days=30,
        max_members=5,
        notion_enabled=True,
        billing_period_name="month"
    ),
    "solo_pro_annual": SubscriptionTier(
        code="solo_pro_annual",
        internal_plan="solo_pro",
        title="Clanomy Solo Pro (Annual - 2 Months Free! 🎁)",
        description="⭐️ 1 Full Year of 60 daily AI extractions, Notion sync & smart queries (Save 17%).",
        price_display="$49.99 / year",
        price_usd_cents=4999,
        duration_days=365,
        max_members=1,
        notion_enabled=True,
        billing_period_name="year"
    ),
    "duo_pro_annual": SubscriptionTier(
        code="duo_pro_annual",
        internal_plan="duo_pro",
        title="Clanomy Duo Pro (Annual - 2 Months Free! 🎁)",
        description="⭐️ 1 Full Year of 120 daily AI extractions, Notion sync & shared ledger for 2 partners (Save 17%).",
        price_display="$79.99 / year",
        price_usd_cents=7999,
        duration_days=365,
        max_members=2,
        notion_enabled=True,
        billing_period_name="year"
    ),
    "family_pro_annual": SubscriptionTier(
        code="family_pro_annual",
        internal_plan="family_pro",
        title="Clanomy Family Pro (Annual - 2 Months Free! 🎁)",
        description="⭐️ 1 Full Year of 300 daily AI extractions, Notion sync & shared ledger for up to 5 members (Save 17%).",
        price_display="$119.99 / year",
        price_usd_cents=11999,
        duration_days=365,
        max_members=5,
        notion_enabled=True,
        billing_period_name="year"
    )
}

def get_tier_config(code: str) -> Optional[SubscriptionTier]:
    """Retrieve tier config by code."""
    return SUBSCRIPTION_TIERS.get(code)
