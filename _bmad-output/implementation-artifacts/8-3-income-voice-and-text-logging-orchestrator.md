---
story_id: "8.3"
epic_id: "8"
title: "Income Voice & Text Logging Orchestrator"
status: "done"
priority: "high"
---

# Story 8.3: Income Voice & Text Logging Orchestrator

Status: done

## User Story
As a User,
I want to log my income via voice notes and text in under 3 seconds,
So that I get an immediate, upbeat confirmation of my earnings and our household's monthly cash flow.

## Acceptance Criteria
- [x] Update `src/services/ai_orchestrator.py` to persist `type` field on `Transaction` records during async background processing.
- [x] Maintain field-level encryption on `amount` and `concept` for income records.
- [x] Implement conversational income confirmation feedback in `src/services/ai_orchestrator.py` / `src/services/messaging.py`:
  - Visual indicator: 💰 / Income badge
  - Display extracted amount, currency, category, and concept/source
  - Include monthly earnings total and updated net cash flow snapshot
- [x] Log execution timing in compliance with the "3s Audit".
- [x] Add integration tests in `tests/services/test_ai_orchestrator.py` and `tests/api/test_telegram_webhook_core.py` verifying the end-to-end income flow.

## Technical Notes
- Conversational UX Template:
  ```text
  💰 Income Logged: +$3,500.00 (Salary - Acme Corp)
  📊 August Snapshot:
  • Total In: $3,500.00
  • Total Out: $1,200.00
  • Net Savings: +$2,300.00 (65%)
  ```

## Tasks / Subtasks

- [x] **Task 1: Transaction Persistence & Type Propagation** (AC: 1, 2)
  - [x] Update `AIOrchestrator._persist_transaction` to accept `tx_type: str = "expense"` and assign `type=tx_type` on `Transaction`.
  - [x] Update `AIOrchestrator.orchestrate` extraction block to pass `tx_type=result.type` when persisting transactions.
  - [x] Ensure field-level encryption for `amount` (`f"{result.amount} {result.currency}"`) and `concept` is applied regardless of transaction type.
- [x] **Task 2: Monthly Cash Flow Snapshot & Conversational Income Feedback** (AC: 3, 4)
  - [x] Implement `_get_monthly_cash_flow_snapshot` helper in `src/services/ai_orchestrator.py` to query and decrypt all family transactions for the target month and calculate:
    - Total In ($\sum \text{income}$ for currency)
    - Total Out ($\sum \text{expense}$ for currency)
    - Net Savings ($\text{Total In} - \text{Total Out}$)
    - Savings rate percentage ($(\text{Net Savings} / \text{Total In}) \times 100$ when $\text{Total In} > 0$)
  - [x] Implement formatting helper for income confirmation messages matching the conversational template.
  - [x] Support retroactive date notes (e.g. `(logged for Aug 11, 2026)`) and multi-currency symbols ($/€/£/etc.).
  - [x] Log execution timings for income orchestration under `[3s Audit]`.
- [x] **Task 3: Unit & Integration Test Suite** (AC: 5)
  - [x] Add unit and integration tests in `tests/services/test_ai_orchestrator.py` covering text income logging, audio income logging, retroactive income logging, negative net savings, and currency formatting.
  - [x] Add integration tests in `tests/api/test_telegram_webhook_core.py` verifying end-to-end income processing through the webhook endpoint.
  - [x] Validate 100% test pass rate (171 tests passed) and no regressions across existing test suite.

## Dev Notes

- **Database Model**: `Transaction` model has `type: str = Field(default="expense", ...)` where valid types are `"expense"` and `"income"`.
- **Extraction Result**: `ExtractionResult.type` provides `"income"` or `"expense"`, defaulting safely to `"expense"`.
- **Encryption**: `amount` ciphertext stores `f"{result.amount} {result.currency}"` and `concept` stores `result.concept`. Decryption is done via `EncryptionService.decrypt()`.
- **Snapshot Scoping**: Cash flow snapshot is scoped by `family_id` and the calendar month of the transaction timestamp. Multi-currency segregation ensures matching transaction currencies are calculated accurately.

## Dev Agent Record

### Agent Model Used

Gemini 3.7 Flash (High)

### Debug Log References

- Fixed `Transaction.type` SQLModel field mapping in `src/db/models.py`.
- Updated `_persist_transaction` in `src/services/ai_orchestrator.py` to support `tx_type` and propagate it to `Transaction`.
- Implemented `_format_currency` and `_get_monthly_cash_flow_snapshot` in `src/services/ai_orchestrator.py`.
- Formatted dual confirmation message (standard expense message vs income badge with month snapshot).
- Verified full test suite (171 tests passed) and compileall validation.

### Completion Notes List

- Updated `_persist_transaction` in `src/services/ai_orchestrator.py` to persist `type="income"` or `type="expense"`.
- Maintained AES-256 field-level encryption on `amount` and `concept` across all income logging channels.
- Added `_get_monthly_cash_flow_snapshot` computing Total In, Total Out, Net Savings, and savings percentage for the relevant month.
- Implemented conversational income feedback with 💰 badge, concept/category details, and monthly cash flow snapshot.
- Preserved `[3s Audit]` latency logging for all audio and text pipeline executions.
- Added extensive test coverage across `tests/services/test_ai_orchestrator.py` and `tests/api/test_telegram_webhook_core.py`.

### File List

- `src/db/models.py`
- `src/services/ai_orchestrator.py`
- `tests/api/conftest.py`
- `tests/api/test_telegram_webhook_core.py`
- `tests/services/test_ai_orchestrator.py`
- `_bmad-output/implementation-artifacts/8-3-income-voice-and-text-logging-orchestrator.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`

### Change Log

- 2026-08-25: Implemented income voice and text logging orchestrator with monthly cash flow snapshots and comprehensive test suite for Story 8.3.

### Review Findings
- [x] [Review][Decision] Shadowing Built-in Keyword — The field 	x_type was renamed to 	ype in src/db/models.py. This shadows the Python built-in 	ype. Should we revert to 	x_type (using an alias) or keep 	ype?
- [x] [Review][Decision] O(N) Snapshot Calculation / Decryption — _get_monthly_cash_flow_snapshot retrieves and sequentially decrypts all transactions for the month, risking OOM and the 3-second SLA. Should we optimize this now or defer?
- [x] [Review][Patch] Missing 	ype in Notion Mirroring [src/services/ai_orchestrator.py]
- [x] [Review][Patch] Garbled Encoding/Corrupted Characters [src/services/ai_orchestrator.py]
- [x] [Review][Patch] Regression in Error Handling for _get_user_info [src/services/ai_orchestrator.py]
- [x] [Review][Patch] Flawed Date Range Logic using microseconds=1 [src/services/ai_orchestrator.py]
- [x] [Review][Patch] Duplicated Logic for date_str generation [src/services/ai_orchestrator.py]
- [x] [Review][Patch] Brittle Type Handling in Snapshot calculation [src/services/ai_orchestrator.py]
- [x] [Review][Patch] Incomplete Documentation for _persist_transaction [src/services/ai_orchestrator.py]
- [x] [Review][Patch] Unhandled None for currency [src/services/ai_orchestrator.py:169]
- [x] [Review][Patch] Unhandled None for mount [src/services/ai_orchestrator.py:172]
- [x] [Review][Patch] Unhandled None for concept or category [src/services/ai_orchestrator.py:302]
- [x] [Review][Patch] Unhandled None for 	ext [tests/api/conftest.py:350]
- [x] [Review][Patch] Incomplete Edge Case Formatting for Zero Net Savings [src/services/ai_orchestrator.py]
- [x] [Review][Defer] Brittle Test Mocks — deferred, pre-existing
