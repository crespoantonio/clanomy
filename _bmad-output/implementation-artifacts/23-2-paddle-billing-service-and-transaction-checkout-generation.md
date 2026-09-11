# Story 23.2: Paddle Billing Service & Transaction Checkout Generation

**Epic:** Epic 23 - Paddle Merchant of Record Billing Integration & Household Governance
**Status:** Completed
**Author:** Amelia & Winston
**Date:** 2026-09-11

---

## 1. Overview & Context

Users need to upgrade their family workspaces via Telegram (`/upgrade`, `/upgrade duo`, `/upgrade annual`) and receive direct, custom-data-bound checkout links that seamlessly activate their subscriptions upon payment completion.

---

## 2. Technical Implementation

### 2.1 PaddleService Integration
- `src/services/billing/paddle_service.py`:
  - Implements `create_checkout_url(family_id, user_id, plan_code, customer_email)`.
  - Dispatches `POST https://api.paddle.com/transactions` with payload:
    ```json
    {
      "items": [{"price_id": "pri_...", "quantity": 1}],
      "custom_data": {
        "family_id": "...",
        "user_id": "...",
        "plan_code": "..."
      }
    }
    ```
  - Returns `data.checkout.url` or hosted URL fallback (`https://pay.paddle.com/checkout/{id}`).
  - Gracefully returns `None` if unconfigured or unreachable.

### 2.2 BillingService Upgrade Command Orchestration
- `src/services/billing/billing_service.py`:
  - Stateless `_get_checkout_or_info_url(plan_code, family, user)` execution ensuring zero concurrent state-mutation race conditions.
  - Parameterized parsing for `/upgrade` subcommands (`annual`, `solo`, `duo`, `family`).
  - Contextual English/Spanish messaging and role-aware admin checks.

---

## 3. Verification & Acceptance

- Validated via `tests/services/test_paddle_service.py` and `tests/services/test_billing_service.py`.
- Verified custom_data serialization and graceful fallback to `SELF_HOSTED_UPGRADE_MESSAGE`.
