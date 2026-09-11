# Story 23.4: Customer Portal & Non-Admin Member Graduation Workflow

**Epic:** Epic 23 - Paddle Merchant of Record Billing Integration & Household Governance
**Status:** Completed
**Author:** Amelia & Winston
**Date:** 2026-09-11

---

## 1. Overview & Context

To give subscribers full self-service autonomy and empower individual family members to upgrade into their own independent family workspaces without breaking the host family, Clanomy provides Paddle Customer Portal sessions and member graduation orchestration.

---

## 2. Technical Implementation

### 2.1 Authenticated Customer Portal Sessions
- `src/services/billing/paddle_service.py` & `src/services/billing/billing_service.py`:
  - Implements `create_customer_portal_session(customer_id, subscription_ids)`.
  - Sends `POST https://api.paddle.com/customers/{customer_id}/portal-sessions`.
  - Returns temporary authenticated session URL for card management, receipts, and plan changes.
  - Bound to `/billing` command in Telegram with role-aware admin verification.

### 2.2 Member Graduation Workflow
- `src/services/family_service.py`:
  - `graduate_member_to_new_workspace(user_id, target_plan)`:
    - Creates a new sovereign `Family` workspace with the user as Admin.
    - Preserves default currency from the prior family.
    - Atomically migrates all personal `Transaction` records belonging to `user.id` to the new `family.id`.
    - Leaves the existing family workspace completely intact.
  - In `src/api/routes/paddle.py`:
    - Automatically triggered when a non-admin member completes checkout for their own subscription plan.
    - Re-attaches managed instances to ensure clean ORM state.

---

## 3. Verification & Acceptance

- Validated via `tests/services/test_family_service.py` (`test_graduate_member_to_new_workspace`) and `tests/services/test_billing_service.py` (`test_handle_billing_command_admin_generates_paddle_portal_session`).
