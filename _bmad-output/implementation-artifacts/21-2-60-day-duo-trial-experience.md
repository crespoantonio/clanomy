# Story 21.2: 60-Day Duo Trial Experience

**Epic:** Epic 21 - Three-Tier Pricing Architecture, 60-Day Duo Trial & Daily Fair-Use Quotas
**Status:** Completed
**Author:** Amelia & John
**Date:** 2026-09-03

---

## 1. Overview & Context

To maximize conversion and allow partners/couples to experience the full value of Clanomy's shared ledger, all new workspaces in SaaS mode are initialized with a complimentary 60-day Duo Trial. The trial unlocks Notion syncing and multi-user logging for up to 2 members with a generous daily transaction quota.

---

## 2. Technical Implementation

### 2.1 Workspace Provisioning & Member Limits
- In `src/services/family_service.py`:
  - When creating a family workspace in SaaS mode (`ENABLE_SUBSCRIPTIONS=true`), sets:
    - `plan_type = "trial"`
    - `trial_ends_at = datetime.now(timezone.utc) + timedelta(days=60)`
    - `subscription_status = "active"`
  - Enforces `max_members = 2` for `trial` and `duo_pro` workspaces. When a third user attempts to join via invite link, returns a helpful upgrade prompt explaining that Duo accommodates 2 partners and recommending Family Pro for larger households.

### 2.2 Subscription Service Checks
- In `src/services/subscription_service.py`:
  - `has_unlimited_access()` confirms active trial status until `trial_ends_at`.
  - Notion database synchronization is enabled throughout the 60-day trial window.

---

## 3. Verification & Acceptance

- Validated via `tests/unit/test_trial_duo_limits.py` and `tests/services/test_three_tier_pricing.py`.
- Verified trial expiration calculations (exactly 60 days from creation).
- Verified invite rejection when a 3rd member attempts to join a Duo/Trial workspace.
