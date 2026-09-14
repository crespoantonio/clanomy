# Story 23.3: Cryptographic Paddle Webhook Verification & Subscription Lifecycle

**Epic:** Epic 23 - Paddle Merchant of Record Billing Integration & Household Governance
**Status:** Completed
**Author:** Amelia & Murat
**Date:** 2026-09-11

---

## 1. Overview & Context

Inbound webhooks from Paddle Billing must be cryptographically authenticated, protected against replay attacks, and processed idempotently to synchronize subscription statuses and manage scheduled changes.

---

## 2. Technical Implementation

### 2.1 Cryptographic Signature Verification & Replay Protection
- `src/services/billing/paddle_service.py` & `src/api/routes/paddle.py`:
  - Enforces `Paddle-Signature` header verification formatted as `ts=<timestamp>;h1=<hmac_sha256>`.
  - Rejects timestamp drift exceeding 5 seconds against server time (`abs(current_ts - ts) > 5`).
  - Constant-time HMAC-SHA256 comparison using `hmac.compare_digest`.
  - Returns HTTP 401 on signature mismatch or replay expiration.

### 2.2 Idempotency & Lifecycle Event Handling
- In `src/api/routes/paddle.py`:
  - Queries `session.get(ProcessedWebhook, event_id)`; returns 200 OK immediately if already processed.
  - Event `subscription.created` & `subscription.updated`:
    - Updates `family.paddle_subscription_id`, `family.paddle_customer_id`, `family.plan_type`, `family.max_members`, and `family.current_period_end`.
    - Captures `scheduled_change_action` and `scheduled_change_effective_at`.
    - Sends private activation Telegram notification to paying admin.
    - If `scheduled_change.action == "cancel"`, broadcasts localized cancellation notice to all family members.
  - Event `subscription.canceled`:
    - Sets `family.subscription_status = "canceled"`.
    - Transitions to Free tier (20 logs/mo limit) if `current_period_end` has elapsed.
  - Event `transaction.completed`:
    - Links transaction charge ID to workspace.
  - Records processed record in `processed_webhook` and commits.

---

## 3. Verification & Acceptance

- Comprehensive test coverage in `tests/api/test_paddle_webhooks.py`:
  - Signature verification and forgery rejection.
  - Replay attack tolerance testing.
  - Idempotency deduplication verification.
  - Cancellation broadcast to all members.
