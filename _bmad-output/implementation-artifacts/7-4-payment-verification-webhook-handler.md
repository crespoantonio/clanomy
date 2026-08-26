---
story_id: "7.4"
epic_id: "7"
title: "Payment Verification & Subscription Lifecycle Webhook Handler"
status: "ready-for-dev"
priority: "high"
---

# Story 7.4: Payment Verification & Subscription Lifecycle Webhook Handler

Status: ready-for-dev

## User Story

As a System,  
I want to securely verify payments, recurring renewals, payment failures, and plan shifts,  
So that user accounts are automatically upgraded, maintained, or gracefully downgraded in real time.

## Acceptance Criteria

- [ ] Update `telegram_webhook` in `src/api/routes/telegram.py` to process `pre_checkout_query` and answer within 10 seconds via `answerPreCheckoutQuery(ok=True)`.
- [ ] Process `successful_payment` updates:
  - Extract and validate `invoice_payload` against whitelist (`sub_solo_pro`, `sub_family_pro`).
  - Update `Family.plan_type` to `"solo_pro"` or `"family_pro"`.
  - Set `Family.subscription_status = "active"` and `Family.current_period_end = now() + 30 days`.
  - Record `telegram_payment_charge_id`.
  - Send an upbeat welcome/confirmation message acknowledging the upgrade.
  - If a multi-member family switches to `"solo_pro"`, notify non-admin members that the family space is now a Solo plan and they can use `/leavefamily` to start their own personal space.
- [ ] Process recurring renewal and cancellation/failure webhook events:
  - Extend `current_period_end` on successful recurring renewal.
  - On cancellation, set `subscription_status = "cancelled"`, retaining Pro access until `current_period_end`.
  - On payment failure or subscription expiry without renewal, set `subscription_status = "expired"`, transition `Family.plan_type = "free"`, and send a friendly notice reassuring that all historical data is safe.
- [ ] Ensure `lifetime_pro` accounts cannot be overwritten or downgraded by external webhook events.
- [ ] Add unit and integration tests in `tests/api/test_telegram_webhook_core.py` and `tests/services/test_subscription_service.py`.
