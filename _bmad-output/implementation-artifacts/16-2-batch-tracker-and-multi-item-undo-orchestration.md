# Story 16.2: Batch Tracker & Multi-Item Undo Orchestration

**Epic:** Epic 16 - Compound Batch Transaction Extraction & Multi-Item Undo
**Status:** Completed
**Author:** Amelia & Winston
**Date:** 2026-09-02

---

## 1. Overview & Context

When multiple transactions are created in a single batch, a subsequent `/undo` command by the user should roll back all transactions in that batch simultaneously rather than requiring repeated undo invocations.

---

## 2. Technical Implementation

### 2.1 Batch Tracker Component
- In `src/services/handlers/batch_tracker.py`:
  - `BatchTracker`: Maps `user_id` to the list of `transaction_id` UUIDs generated in their latest batch event.
  - Exposes `record_batch(user_id, transaction_ids)` and `get_last_batch(user_id)`.

### 2.2 Transaction Handler Rollback
- In `src/services/handlers/transaction_handler.py`:
  - `undo_last_transaction()` inspects `BatchTracker`.
  - If a batch is registered, it soft-deletes/reverts all transactions in that batch in a single atomic database transaction.
  - Returns a combined confirmation acknowledging all reverted items.

---

## 3. Verification & Acceptance

- Validated via `tests/unit/test_batch_extraction_and_undo.py`.
- Verified batch creation followed by `/undo` completely restores the prior ledger balance.
