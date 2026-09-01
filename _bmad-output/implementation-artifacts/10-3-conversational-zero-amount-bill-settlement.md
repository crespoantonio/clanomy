---
story_id: "10.3"
epic_id: "10"
title: "Conversational Zero-Amount Bill Settlement"
status: "done"
priority: "high"
---

# Story 10.3: Conversational Zero-Amount Bill Settlement

## User Story
As a User,
I want to say *"Pagué la visa"* or *"Paid the electric bill"* without mentioning the amount,
So that the bot marks the pending bill as paid and logs the expense under my name automatically.

## Acceptance Criteria
- [x] In `AIOrchestrator`, detect payment verbs (*"pagué"*, *"paid"*, *"aboné"*, *"liquidé"*, *"cancelé"*) when amount is missing.
- [x] Implement `_settle_bill_without_amount()` with user-scoped precedence:
  1. Search pending `ScheduledBill` for sender (`bill.user_id == current_user.id`).
  2. If none match, search pending bills for family (`bill.family_id == current_family.id`).
- [x] Decrypt bill amount and create a new `Transaction` under category `"Rent/Bills"`.
- [x] Update bill `status="paid"` and link `paid_transaction_id`.
- [x] Trigger Notion mirroring for the settlement transaction.
- [x] If no matching bill exists, gracefully ask for the amount without throwing an error.

## Tasks / Subtasks
- [x] **Settlement Engine** (AC: 1, 2, 3, 4, 5)
  - [x] Implement `_settle_bill_without_amount` in `src/services/ai_orchestrator.py`.
- [x] **Clarification Fallback** (AC: 6)
  - [x] Add friendly prompt when concept does not match any pending bills.
- [x] **Verification**
  - [x] Test cases in `tests/services/test_scheduled_bills.py` verifying own-user precedence, family fallback, and not-found handling.
