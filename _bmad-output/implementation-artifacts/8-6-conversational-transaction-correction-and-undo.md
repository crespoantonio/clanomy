---
story_id: "8.6"
epic_id: "8"
title: "Conversational Transaction Correction & Undo (Edit Latest Log)"
status: "done"
priority: "medium"
---

# Story 8.6: Conversational Transaction Correction & Undo (Edit Latest Log)

Status: done

## User Story

As a User,  
I want to send natural language corrections (e.g., "Change the last one to income", "Change last amount to 45", or "Delete the last log"),  
So that I can immediately fix transcription mistakes or incorrect categories without opening a web dashboard.

## Acceptance Criteria

- [x] Upgrade `src/services/query_service.py` & `src/services/extraction_service.py` to recognize correction & undo intents:
  - `"intent": "edit_last" | "undo_last"`
  - Support delta extraction: `new_type: Optional[str]`, `new_amount: Optional[float]`, `new_currency: Optional[str]`, `new_category: Optional[str]`, `new_concept: Optional[str]`.
  - Include fallback regex heuristics for fast offline correction commands (e.g., `^change (the )?(last|latest) (one )?to (income|expense)$`, `^delete (the )?(last|latest) (log|transaction)$`, `^undo( last)?$`).
- [x] Implement `_get_latest_transaction` helper in `src/services/ai_orchestrator.py` querying the user's most recent transaction:
  - `select(Transaction).where(Transaction.user_id == user.id).order_by(Transaction.timestamp.desc()).first()`
- [x] Implement `_handle_transaction_correction` in `src/services/ai_orchestrator.py`:
  - Decrypt target transaction fields using `EncryptionService.decrypt()`.
  - Apply requested changes (`type`, `amount`, `currency`, `category`, `concept`).
  - Re-encrypt modified ciphertext (`amount`, `concept`) and commit database update.
  - Recalculate monthly cash flow snapshot.
  - Return friendly conversational confirmation highlighting what changed (e.g., `âœï¸ Updated latest transaction: ðŸ’° +$3,500.00 (Salary - Acme Corp) [Switched from Expense ðŸ’¸ to Income ðŸ’°]`).
- [x] Implement `_handle_transaction_undo` in `src/services/ai_orchestrator.py`:
  - Delete latest transaction from database.
  - Recalculate monthly cash flow snapshot.
  - Return conversational confirmation (e.g., `ðŸ—‘ï¸ Removed latest transaction: -$45.00 (Lunch)`).
- [x] If Notion mirroring is enabled and `notion_page_id` is present on the transaction:
  - Update page properties or archive the Notion page via `NotionService` in a non-blocking background task.
- [x] Gracefully handle edge cases:
  - User has no transactions to edit or delete $\rightarrow$ reply with friendly guidance (*"You don't have any recent transactions to update."*).
- [x] Add unit and integration tests in `tests/services/test_corrections_and_undo.py` and `tests/services/test_ai_orchestrator.py`.

## Tasks / Subtasks

- [x] **Task 1: Extraction Service Correction Intent & Schema** (AC: 1)
  - [x] Expand Pydantic extraction schema / Ollama prompt to classify `edit_last` and `undo_last` intents with patch fields.
  - [x] Implement regex fallback matching for common voice/text correction phrases.
- [x] **Task 2: AI Orchestrator Correction & Undo Logic** (AC: 2, 3, 4, 6)
  - [x] Implement latest transaction retrieval for the user scope.
  - [x] Implement field-level decryption, delta merging, re-encryption, and commit.
  - [x] Implement transaction deletion for undo requests.
  - [x] Format conversational confirmation messages with updated cash flow metrics.
- [x] **Task 3: Notion Mirror Updates & Background Sync** (AC: 5)
  - [x] Add `update_transaction_page` and `archive_transaction_page` methods to `NotionService`.
  - [x] Trigger background updates when an edited/undone transaction has a `notion_page_id`.
- [x] **Task 4: Unit & Integration Test Suite** (AC: 7)
  - [x] Test type toggle (expense $\leftrightarrow$ income) and monthly totals recalculation.
  - [x] Test amount/category/concept corrections with ciphertext verification.
  - [x] Test undo/deletion flow.
  - [x] Test empty transaction history edge case.
  - [x] Test Notion update/archive mocking.

## Suggested Review Order
1. [`src/services/query_service.py`](file:///c:/Users/cresp/Documents/Projectos/clanomy/src/services/query_service.py): Review `ParsedQueryIntent` delta fields and system prompt updates.
2. [`src/services/notion_service.py`](file:///c:/Users/cresp/Documents/Projectos/clanomy/src/services/notion_service.py): Review `update_transaction_page` and `archive_transaction_page`.
3. [`src/services/ai_orchestrator.py`](file:///c:/Users/cresp/Documents/Projectos/clanomy/src/services/ai_orchestrator.py): Review `_handle_transaction_correction`, `_handle_transaction_undo`, and regex routing shortcuts.
4. [`tests/services/test_corrections_and_undo.py`](file:///c:/Users/cresp/Documents/Projectos/clanomy/tests/services/test_corrections_and_undo.py): Review test cases covering all correction, undo, and Notion mirroring flows.

## Technical Notes

- **Field Re-encryption**: `amount` ciphertext stores `f"{amount} {currency}"` and `concept` stores string plaintext encrypted via `EncryptionService.encrypt()`.
- **Zero-Knowledge Security**: Decryption and re-encryption happen strictly in memory within the orchestrator worker.
- **Latency**: All DB updates and LLM intent parsing remain compliant with the `< 3.0s` SLA. Notion updates are dispatched as background tasks (`asyncio.create_task`).
### Review Findings

- [x] [Review][Patch] Hardcoded decimal assumptions for currencies â€” Uses f{new_amt:.2f} {new_curr} which breaks for zero-decimal currencies.
- [x] [Review][Patch] Irrelevant historical month reporting â€” When undoing a historical transaction, it calculates the historical month's balance instead of the current month's context.
- [x] [Review][Patch] Fragile special intent heuristic for "change" [src/services/ai_orchestrator.py]
- [x] [Review][Patch] Premature background task cancellation [src/services/ai_orchestrator.py]
- [x] [Review][Patch] Non-deterministic transaction ordering [src/services/ai_orchestrator.py]
- [x] [Review][Patch] Unmaintainable intent matching [src/services/ai_orchestrator.py]
- [x] [Review][Patch] Silent schema failure in Notion updates [src/services/notion_service.py]
- [x] [Review][Patch] Incomplete currency fallback mapping [src/services/ai_orchestrator.py]
- [x] [Review][Patch] Missing bounds validation for negative amounts [src/services/query_service.py:104]
- [x] [Review][Patch] Sloppy ORM attribute checking [src/services/ai_orchestrator.py]
- [x] [Review][Patch] Float parse ValueError in _handle_transaction_undo [src/services/ai_orchestrator.py:204]
- [x] [Review][Patch] Float parse ValueError in _handle_transaction_correction [src/services/ai_orchestrator.py:256]
- [x] [Review][Patch] 
ew_type parsed as non-standard string [src/services/query_service.py:103]
- [x] [Review][Patch] Missing update to extraction service [src/services/extraction_service.py]
- [x] [Review][Patch] Created helper function is bypassed [src/services/ai_orchestrator.py:191]
- [x] [Review][Patch] Missing test coverage in ai_orchestrator suite [tests/services/test_ai_orchestrator.py]


