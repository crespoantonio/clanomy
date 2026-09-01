from dataclasses import dataclass
from typing import Dict, Optional

@dataclass(frozen=True)
class SubscriptionTier:
    """
    Unified specification for a subscription plan tier.
    Centralizes pricing (Stars), duration (monthly/yearly), member limits, and metadata.
    Automatically computes Telegram Stars subscription_period_seconds from duration_days.
    """
    code: str                         # e.g. "solo_pro", "solo_pro_annual", "family_pro", "family_pro_annual"
    internal_plan: str                # Target DB plan_type on Family model: "solo_pro" or "family_pro"
    title: str                        # Display title on Telegram invoices & messages
    description: str                  # Short marketing description
    stars: int                        # Cost in Telegram Stars
    duration_days: int                # Period duration in days (e.g. 30 for monthly, 365 for annual)
    max_members: int                  # Workspace member capacity (1 for Solo, 5 for Family)
    notion_enabled: bool              # Whether Notion database mirroring is enabled
    billing_period_name: str          # "month" or "year"

    @property
    def subscription_period_seconds(self) -> int:
        """Calculates Telegram Stars auto-renewal period in seconds (duration_days * 86,400s)."""
        return self.duration_days * 86400

# Global Free Tier & Trial Constants
FREE_TIER_MONTHLY_LIMIT: int = 20
TRIAL_DURATION_DAYS: int = 60

# Centralized Subscription Registry (Only specify duration_days - seconds are auto-calculated!)
SUBSCRIPTION_TIERS: Dict[str, SubscriptionTier] = {
    "solo_pro": SubscriptionTier(
        code="solo_pro",
        internal_plan="solo_pro",
        title="Clanomy Solo Pro",
        description="⭐️ Unlimited AI logging, Notion sync & smart queries for 1 individual user.",
        stars=200,
        duration_days=30,
        max_members=1,
        notion_enabled=True,
        billing_period_name="month"
    ),
    "family_pro": SubscriptionTier(
        code="family_pro",
        internal_plan="family_pro",
        title="Clanomy Family Pro",
        description="⭐️ Unlimited AI logging, Notion sync & shared ledger for up to 5 family members.",
        stars=450,
        duration_days=30,
        max_members=5,
        notion_enabled=True,
        billing_period_name="month"
    ),
    "solo_pro_annual": SubscriptionTier(
        code="solo_pro_annual",
        internal_plan="solo_pro",
        title="Clanomy Solo Pro (Annual - 2 Months Free! 🎁)",
        description="⭐️ 1 Full Year of Unlimited AI logging, Notion sync & smart queries (Save 17%).",
        stars=2000,
        duration_days=365,
        max_members=1,
        notion_enabled=True,
        billing_period_name="year"
    ),
    "family_pro_annual": SubscriptionTier(
        code="family_pro_annual",
        internal_plan="family_pro",
        title="Clanomy Family Pro (Annual - 2 Months Free! 🎁)",
        description="⭐️ 1 Full Year of Unlimited AI logging, Notion sync & shared ledger for up to 5 members (Save 17%).",
        stars=4500,
        duration_days=365,
        max_members=5,
        notion_enabled=True,
        billing_period_name="year"
    )
}

def get_tier_config(code: str) -> Optional[SubscriptionTier]:
    """Retrieve tier config by code."""
    return SUBSCRIPTION_TIERS.get(code)
