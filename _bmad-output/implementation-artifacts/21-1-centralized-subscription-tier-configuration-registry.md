# Story 21.1: Centralized Subscription Tier Configuration Registry

**Epic:** Epic 21 - Three-Tier Pricing Architecture, 60-Day Duo Trial & Daily Fair-Use Quotas
**Status:** Completed
**Author:** Amelia & John
**Date:** 2026-09-03

---

## 1. Overview & Context

To support a 3-tier subscription architecture (Solo Pro, Duo Pro, Family Pro) across monthly and annual durations, plan specifications, limits, and pricing must be centralized into a single immutable registry rather than scattered across database models, message templates, and route controllers.

---

## 2. Technical Implementation

### 2.1 Subscription Tier Dataclass & Registry
- In `src/core/subscription_config.py`:
  - Created `@dataclass(frozen=True) class SubscriptionTier`:
    - `code`: Unique identifier (e.g. `solo_pro`, `duo_pro_annual`).
    - `internal_plan`: Mapped database plan (`solo_pro`, `duo_pro`, `family_pro`).
    - `title`: Display name with marketing badges.
    - `description`: Feature summary.
    - `price_display`: Formatted price string.
    - `price_usd_cents`: Integer cents for checkout calculations.
    - `duration_days`: 30 for monthly, 365 for annual.
    - `max_members`: 1 for Solo, 2 for Duo, 5 for Family.
    - `notion_enabled`: True for all Pro tiers.
    - `billing_period_name`: `"month"` or `"year"`.
  - Registered all monthly and annual variants in `SUBSCRIPTION_TIERS`.
  - Provided helper functions `get_tier_config(plan_code)` and `get_tier_by_internal_plan()`.

---

## 3. Verification & Acceptance

- Validated via `tests/services/test_three_tier_pricing.py`.
- Verified 17% annual discount calculation across all tiers.
- Confirmed member limit attributes reflect 1, 2, and 5 users accurately.
