---
story_id: "8.6"
epic_id: "8"
title: "Conversational Transaction Correction & Undo (Edit Latest Log)"
status: "ready-for-dev"
priority: "medium"
---

# Story 8.6: Conversational Transaction Correction & Undo (Edit Latest Log)

Status: ready-for-dev

## User Story

As a User,  
I want to send natural language corrections (e.g., "Change the last one to income", "Change last amount to 45", or "Delete the last log"),  
So that I can immediately fix transcription mistakes or incorrect categories without opening a web dashboard.

## Acceptance Criteria

- [ ] Upgrade `src/services/extraction_service.py` to recognize correction & undo intents:
  - `"intent": "edit_last" | "undo_last"`
  - Support delta extraction: `new_type: Optional[str]`, `new_amount: Optional[float]`, `new_currency: Optional[str]`, `new_category: Optional[str]`, `new_concept: Optional[str]`.
  - Include fallback regex heuristics for fast offline correction commands (e.g., `^change (the )?(last|latest) (one )?to (income|expense)$`, `^delete (the )?(last|latest) (log|transaction)$`, `^undo( last)?$`).
- [ ] Implement `_get_latest_transaction` helper in `src/services/ai_orchestrator.py` querying the user's most recent transaction:
  - `select(Transaction).where(Transaction.user_id == user.id).order_by(Transaction.timestamp.desc()).first()`
- [ ] Implement `_handle_transaction_correction` in `src/services/ai_orchestrator.py`:
  - Decrypt target transaction fields using `EncryptionService.decrypt()`.
  - Apply requested changes (`type`, `amount`, `currency`, `category`, `concept`).
  - Re-encrypt modified ciphertext (`amount`, `concept`) and commit database update.
  - Recalculate monthly cash flow snapshot.
  - Return friendly conversational confirmation highlighting what changed (e.g., `✏️ Updated latest transaction: 💰 +$3,500.00 (Salary - Acme Corp) [Switched from Expense 💸 to Income 💰]`).
- [ ] Implement `_handle_transaction_undo` in `src/services/ai_orchestrator.py`:
  - Delete latest transaction from database.
  - Recalculate monthly cash flow snapshot.
  - Return conversational confirmation (e.g., `🗑️ Removed latest transaction: -$45.00 (Lunch)`).
- [ ] If Notion mirroring is enabled and `notion_page_id` is present on the transaction:
  - Update page properties or archive the Notion page via `NotionService` in a non-blocking background task.
- [ ] Gracefully handle edge cases:
  - User has no transactions to edit or delete $\rightarrow$ reply with friendly guidance (*"You don't have any recent transactions to update."*).
- [ ] Add unit and integration tests in `tests/services/test_ai_orchestrator.py`, `tests/services/test_extraction_service.py`, and `tests/api/test_telegram_webhook_core.py`.

## Tasks / Subtasks

- [ ] **Task 1: Extraction Service Correction Intent & Schema** (AC: 1)
  - [ ] Expand Pydantic extraction schema / Ollama prompt to classify `edit_last` and `undo_last` intents with patch fields.
  - [ ] Implement regex fallback matching for common voice/text correction phrases.
- [ ] **Task 2: AI Orchestrator Correction & Undo Logic** (AC: 2, 3, 4, 6)
  - [ ] Implement latest transaction retrieval for the user scope.
  - [ ] Implement field-level decryption, delta merging, re-encryption, and commit.
  - [ ] Implement transaction deletion for undo requests.
  - [ ] Format conversational confirmation messages with updated cash flow metrics.
- [ ] **Task 3: Notion Mirror Updates & Background Sync** (AC: 5)
  - [ ] Add `update_transaction_page` and `archive_transaction_page` methods to `NotionService`.
  - [ ] Trigger background updates when an edited/undone transaction has a `notion_page_id`.
- [ ] **Task 4: Unit & Integration Test Suite** (AC: 7)
  - [ ] Test type toggle (expense $\leftrightarrow$ income) and monthly totals recalculation.
  - [ ] Test amount/category/concept corrections with ciphertext verification.
  - [ ] Test undo/deletion flow.
  - [ ] Test empty transaction history edge case.
  - [ ] Test Notion update/archive mocking.

## Technical Notes

- **Field Re-encryption**: `amount` ciphertext stores `f"{amount} {currency}"` and `concept` stores string plaintext encrypted via `EncryptionService.encrypt()`.
- **Zero-Knowledge Security**: Decryption and re-encryption happen strictly in memory within the orchestrator worker.
- **Latency**: All DB updates and LLM intent parsing must remain compliant with the `< 3.0s` SLA. Notion updates are dispatched as background tasks (`asyncio.create_task`).
