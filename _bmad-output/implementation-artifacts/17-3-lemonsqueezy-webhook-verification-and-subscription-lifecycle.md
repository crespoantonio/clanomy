# Story 17.3: Lemon Squeezy Webhook Verification & Subscription Lifecycle

**Epic:** Epic 17 - Merchant of Record (Lemon Squeezy) Subscription Engine & Cloud Billing Integration
**Status:** Completed
**Author:** Amelia & Winston
**Date:** 2026-09-02

---

## 1. Overview & Context

External billing webhooks must be cryptographically verified using HMAC-SHA256 signatures before processing payloads, ensuring only authentic Lemon Squeezy events update family subscriptions.

---

## 2. Technical Implementation

### 2.1 Cryptographic Signature Verification
- In `src/services/billing/lemonsqueezy_billing.py`:
  - `verify_webhook_signature(raw_body, signature_header)` computes HMAC-SHA256 using `LEMONSQUEEZY_WEBHOOK_SECRET` and performs constant-time comparison.

### 2.2 Event Dispatcher
- In `src/api/routes/lemonsqueezy.py`:
  - Receives `POST /api/webhooks/lemonsqueezy`.
  - Dispatches events:
    - `subscription_created`: Sets `subscription_status="active"`, updates plan type, records customer ID.
    - `subscription_updated`: Updates status, renewal dates, and variant IDs.
    - `subscription_cancelled`: Marks status as cancelled with grace period.
    - `subscription_resumed`, `subscription_paused`, `subscription_expired`.
    - `order_created`: Handles one-off or initial orders.

---

## 3. Verification & Acceptance

- Validated with unit and webhook tests in `tests/services/test_lemonsqueezy_billing.py`.
- Verified forged or altered signatures are rejected with HTTP 401.
