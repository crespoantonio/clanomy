# Story 17.4: Customer Billing Portal & Tier Limits

**Epic:** Epic 17 - Merchant of Record (Lemon Squeezy) Subscription Engine & Cloud Billing Integration
**Status:** Completed
**Author:** Amelia & John
**Date:** 2026-09-02

---

## 1. Overview & Context

Subscribers must be able to self-manage their subscriptions, update payment methods, download invoices, or cancel without contacting administrative support.

---

## 2. Technical Implementation

### 2.1 Customer Portal Generation
- In `src/services/billing/lemonsqueezy_billing.py`:
  - `get_customer_portal_url(customer_id)` calls Lemon Squeezy API to generate an authenticated Customer Portal session link.

### 2.2 Telegram Interface
- `/billing`: Detects active subscription, calls `get_customer_portal_url()`, and returns an inline button pointing to the Lemon Squeezy portal.
- Free-tier accounts receive a message explaining they are on the free plan with options to upgrade.

---

## 3. Verification & Acceptance

- Validated via `tests/services/test_lemonsqueezy_billing.py`.
- Verified customer portal generation and link formatting.
