# Story 17.2: Lemon Squeezy Billing Service & Checkout Generation

**Epic:** Epic 17 - Merchant of Record (Lemon Squeezy) Subscription Engine & Cloud Billing Integration
**Status:** Completed
**Author:** Amelia & Winston
**Date:** 2026-09-02

---

## 1. Overview & Context

To monetize Clanomy SaaS (`ENABLE_SUBSCRIPTIONS=true`) with credit cards, Apple Pay, and Google Pay while letting Lemon Squeezy act as Merchant of Record (handling global VAT/tax remittance), Clanomy implements a native billing service.

---

## 2. Technical Implementation

### 2.1 Lemon Squeezy Client
- In `src/services/billing/lemonsqueezy_billing.py`:
  - Implemented `LemonSqueezyBillingService`.
  - Generates hosted checkout sessions calling the Lemon Squeezy API (`/v1/checkouts`).
  - Injects custom passthrough data: `custom_data={"family_id": str(family.id), "chat_id": str(chat_id)}`.

### 2.2 Upgrade Flow in Telegram
- In `src/services/telegram_service.py` and `src/templates/telegram_messages.py`:
  - `/upgrade` generates inline checkout buttons for Solo Pro ($4.99/mo) and Family Pro ($9.99/mo).

---

## 3. Verification & Acceptance

- Validated via `tests/services/test_lemonsqueezy_billing.py`.
- Verified custom passthrough metadata is correctly preserved in checkout requests.
