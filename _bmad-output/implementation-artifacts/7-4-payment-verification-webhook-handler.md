---
story_id: "7.4"
epic_id: "7"
title: "Payment Verification & Subscription Lifecycle Webhook Handler"
status: "done"
priority: "high"
---

# Story 7.4: Payment Verification & Subscription Lifecycle Webhook Handler

Status: done

## User Story

As a System,  
I want to securely verify payments, recurring renewals, payment failures, and plan shifts,  
So that user accounts are automatically upgraded, maintained, or gracefully downgraded in real time.

## Acceptance Criteria

- [x] Update `telegram_webhook` in `src/api/routes/telegram.py` to process `pre_checkout_query` and answer within 10 seconds via `answerPreCheckoutQuery(ok=True)`.
- [x] Process `successful_payment` updates:
  - Extract and validate `invoice_payload` against whitelist (`sub_solo_pro`, `sub_family_pro`).
  - Update `Family.plan_type` to `"solo_pro"` or `"family_pro"`.
  - Set `Family.subscription_status = "active"` and `Family.current_period_end = now() + 30 days`.
  - Record `telegram_payment_charge_id`.
  - Send an upbeat welcome/confirmation message acknowledging the upgrade.
  - If a multi-member family switches to `"solo_pro"`, notify non-admin members that the family space is now a Solo plan and they can use `/leavefamily` to start their own personal space.
- [x] Process recurring renewal and cancellation/failure webhook events:
  - Extend `current_period_end` on successful recurring renewal.
  - On cancellation, set `subscription_status = "cancelled"`, retaining Pro access until `current_period_end`.
  - On payment failure or subscription expiry without renewal, set `subscription_status = "expired"`, transition `Family.plan_type = "free"`, and send a friendly notice reassuring that all historical data is safe.
- [x] Ensure `lifetime_pro` accounts cannot be overwritten or downgraded by external webhook events.
- [x] Add unit and integration tests in `tests/api/test_telegram_webhook_core.py` and `tests/services/test_subscription_service.py`.

## Tasks / Subtasks

- [x] **Task 1: Pre-Checkout Query Processing & Answer (`answerPreCheckoutQuery`)** (AC: 1)
  - [x] Implement `TelegramService.answer_pre_checkout_query(pre_checkout_query_id, ok, error_message)` invoking Telegram Bot API `/answerPreCheckoutQuery`.
  - [x] Update `telegram_webhook` in `src/api/routes/telegram.py` to intercept `pre_checkout_query` updates.
  - [x] Validate `invoice_payload` in `pre_checkout_query` and answer with `ok=True` or `ok=False` within the 10-second window.
- [x] **Task 2: Subscription Service Lifecycle Methods & Access Retention** (AC: 2, 3, 4)
  - [x] Update `has_unlimited_access` in `src/services/subscription_service.py` to support `cancelled` status with unexpired `current_period_end`.
  - [x] Implement `extract_plan_and_family_id` and fix `validate_invoice_payload` pattern parsing.
  - [x] Implement `handle_successful_payment` to update plan type, active status, 30-day period end, member caps, and charge ID, protecting `lifetime_pro` against overwriting.
  - [x] Implement `handle_recurring_renewal`, `handle_subscription_cancellation`, `handle_subscription_expiry`, and `handle_payment_failure`.
- [x] **Task 3: Successful Payment & Refund Webhook Route Handling** (AC: 2, 3)
  - [x] In `src/api/routes/telegram.py`, process `message.successful_payment` events.
  - [x] Send upbeat confirmation message on upgrade to the subscriber.
  - [x] When a multi-member family switches to `solo_pro`, send a notification to non-admin members informing them to use `/leavefamily`.
  - [x] Handle `message.refunded_payment` updates to transition workspace gracefully to the free tier.
- [x] **Task 4: Comprehensive Unit & Integration Tests** (AC: 5)
  - [x] Update `tests/api/conftest.py` with mock support for `answer_pre_checkout_query` and payment fixtures.
  - [x] Author unit tests in `tests/services/test_subscription_service.py` and `tests/services/test_telegram_service.py`.
  - [x] Author integration tests in `tests/api/test_telegram_webhook_core.py` for pre_checkout_query, successful_payment (Solo Pro & Family Pro), lifetime protection, multi-member solo switch notification, and refunds.
  - [x] Run full regression test suite and verify 100% pass rate.

## File List

- `src/services/telegram_service.py` (Modified)
- `src/services/subscription_service.py` (Modified)
- `src/api/routes/telegram.py` (Modified)
- `tests/api/conftest.py` (Modified)
- `tests/services/test_telegram_service.py` (Modified)
- `tests/services/test_subscription_service.py` (Modified)
- `tests/api/test_telegram_webhook_core.py` (Modified)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (Modified)
- `_bmad-output/implementation-artifacts/7-4-payment-verification-webhook-handler.md` (Modified)

## Dev Agent Record

### Implementation Plan
1. Implement `TelegramService.answer_pre_checkout_query` calling `/answerPreCheckoutQuery` with timeout resilience.
2. In `src/services/subscription_service.py`, add lifecycle helper functions (`handle_successful_payment`, `handle_recurring_renewal`, `handle_subscription_cancellation`, `handle_subscription_expiry`, `handle_payment_failure`) and update `has_unlimited_access` to retain access during cancelled periods before `current_period_end`.
3. In `src/api/routes/telegram.py`, handle `pre_checkout_query`, `message.successful_payment`, and `message.refunded_payment`, including non-admin member notifications when downgrading a multi-member workspace to Solo Pro.
4. Author comprehensive unit and integration tests across services and webhook endpoints.
5. Run full test suite and build verification.

### Completion Notes
- âœ… Implemented `TelegramService.answer_pre_checkout_query` invoking Telegram Bot API `/answerPreCheckoutQuery`.
- âœ… Updated `telegram_webhook` in `src/api/routes/telegram.py` to intercept `pre_checkout_query` and validate payloads, answering with `ok=True` or `ok=False`.
- âœ… Added lifecycle handling in `src/services/subscription_service.py` (`handle_successful_payment`, `handle_recurring_renewal`, `handle_subscription_cancellation`, `handle_subscription_expiry`, `handle_payment_failure`).
- âœ… Preserved Pro access during cancelled periods before `current_period_end` in `has_unlimited_access`.
- âœ… Protected `lifetime_pro` accounts from external webhook downgrades.
- âœ… Processed `successful_payment` updates with welcome messaging and multi-member Solo Pro `/leavefamily` notifications.
- âœ… Processed `refunded_payment` updates transitioning workspaces gracefully to the Free tier.
- âœ… 244/244 tests passing (100% pass rate) across unit, integration, db, and API suites.
- âœ… Successfully verified container build with `podman build -t clanomy .`.

## Change Log
- **2026-08-26**: Implemented payment verification, `pre_checkout_query` answering, `successful_payment` upgrade processing, subscription lifecycle methods (renewal, cancellation retention, expiry, refunds), member notices, and comprehensive unit/integration test coverage (244 tests passing).


### Review Findings

- [x] [Review][Decision] No grace period on payment failure â€” handle_payment_failure instantly dumps users to free tier. Should we add a grace period?
- [x] [Review][Decision] Unbounded background task loops for notifications â€” Notifying multi-member families fires off unbounded ackground_tasks.add_task, potentially hitting Telegram rate limits. Should we batch or delay?
- [x] [Review][Patch] Refund Loophole for Lifetime Pro & Cross-workspace Down-grade [src/api/routes/telegram.py]
- [x] [Review][Patch] Webhook swallows successful payments on unresolved families [src/api/routes/telegram.py]
- [x] [Review][Patch] Naked except block in pre_checkout_query handler [src/api/routes/telegram.py]
- [x] [Review][Patch] Hardcoded +30 days for subscription periods [src/services/subscription_service.py]
- [x] [Review][Patch] Ignored return value from handle_successful_payment [src/api/routes/telegram.py]
- [x] [Review][Patch] Incorrect non-admin checking logic [src/api/routes/telegram.py]
- [x] [Review][Patch] Expiry sets max_members to 5 [src/services/subscription_service.py]
- [x] [Review][Patch] Loose UUID validation for family_id [src/services/subscription_service.py]
- [x] [Review][Patch] Incorrect naive to UTC conversion in _compare_datetimes [src/services/subscription_service.py]
- [x] [Review][Patch] Missing webhook handlers for lifecycle events [src/api/routes/telegram.py]
- [x] [Review][Patch] Missing user notifications for failure and expiry [src/api/routes/telegram.py]
- [x] [Review][Patch] Missing integration tests for webhook lifecycle events [tests/api/test_telegram_webhook_core.py]
- [x] [Review][Patch] pre_checkout_query lacks id field [src/api/routes/telegram.py]
- [x] [Review][Defer] Local import in webhook function [src/api/routes/telegram.py] â€” deferred, pre-existing


