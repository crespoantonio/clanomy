---
story_id: "8.5"
epic_id: "8"
title: "Notion Mirroring & Export Updates for Income Records"
status: "done"
priority: "medium"
---

# Story 8.5: Notion Mirroring & Export Updates for Income Records

Status: done

## User Story
As a User,
I want income records to be synced to my Notion database and included in my GDPR exports,
So that my external dashboards and data backups have a complete, accurate record of my finances.

## Acceptance Criteria
- [x] Update `src/services/notion_mirror.py` (implemented in `src/services/notion_service.py`) to push `Type` property (`Income` vs `Expense`) to Notion database pages.
- [x] Ensure Notion mirroring handles both positive income amounts and expenses gracefully.
- [x] Update CSV and JSON export routines in `src/services/export_service.py` or API routes to include `Type` column:
  - Header: `["Timestamp (UTC)", "Type", "Amount", "Currency", "Category", "Concept", "Logged By"]`
  - Values: `"expense"` or `"income"`
- [x] Add unit tests in `tests/services/test_notion_service.py` and `tests/services/test_export_service.py`.

## Technical Notes
- For Notion databases, if the `Type` select column doesn't exist, log a non-fatal warning or create it if API schema permissions allow, falling back to writing to page properties without breaking execution.

## Tasks / Subtasks

- [x] **Task 1: Notion Mirroring Updates for Income & Type Property** (AC: 1, 2)
  - [x] Update `_build_page_properties` in `src/services/notion_service.py` to match `Type` property names (`"type"`, `"transaction type"`, `"tx_type"`, `"kind"`, `"entry type"`) and set value to `"Income"` or `"Expense"`.
  - [x] Disambiguate `category` matching from `type` matching so that `Category` properties and `Type` properties are populated independently and accurately.
  - [x] Ensure positive numeric amounts are passed for both Income and Expense transactions.
  - [x] Implement schema resilience: if Notion database schema lacks a `Type` column, log a non-fatal message and proceed without failing page creation.
  - [x] Update `sync_pending_transactions` and `test_connection_mirror` in `src/services/notion_service.py` to pass the transaction's resolved type.
- [x] **Task 2: CSV & JSON Export Routine Updates** (AC: 3)
  - [x] Update `_decrypt_transaction` in `src/services/export_service.py` to extract `type` from `Transaction` (`"expense"` or `"income"`) and populate `DecryptedTransaction.type`.
  - [x] Update `generate_csv` in `src/services/export_service.py` to include `Type` column in header and record rows (`["Timestamp (UTC)", "Type", "Amount", "Currency", "Category", "Concept", "Logged By"]`).
  - [x] Update `generate_json` in `src/services/export_service.py` to include `"type": tx.type` in transaction JSON objects.
- [x] **Task 3: Unit & Integration Test Suite** (AC: 4)
  - [x] Add unit tests in `tests/services/test_notion_service.py` for Notion `Type` property mapping (Income vs Expense), schema fallback when `Type` property missing, and catch-up sync with income transactions.
  - [x] Add unit tests in `tests/services/test_export_service.py` verifying CSV headers/rows with `Type` column and JSON output with `type` field for both income and expense records.
  - [x] Run full test suite and verify 100% pass rate (189/189 tests passing).

### Review Findings

- [x] [Review][Decision] Breaking Change for Notion Setups — Removed "type" from category match list, breaking backward compatibility for users using "Type" for Category.
- [x] [Review][Decision] Masking Data Errors with abs() — Applying abs(amount) silently converts negative values to positive. Should it reject negatives?
- [x] [Review][Patch] Unsafe Database Model Modification [src/db/models.py]
- [x] [Review][Patch] DRY Violation in Type Extraction [src/services/ai_orchestrator.py, src/services/export_service.py, src/services/notion_service.py]
- [x] [Review][Patch] Redundant Variable Assignment [src/services/notion_service.py]
- [x] [Review][Patch] Paranoid getattr Usage [src/services/export_service.py]
- [x] [Review][Patch] Destructive Test Modification [tests/services/test_export_service.py]
- [x] [Review][Patch] Superficial Database Testing [tests/services/test_export_service.py]
- [x] [Review][Patch] Unauthorized Modification of Acceptance Criteria [_bmad-output/implementation-artifacts/8-5-notion-mirroring-and-export-updates.md]
- [x] [Review][Patch] Incorrect Log Level for Missing Schema Property [src/services/notion_service.py]

## Dev Notes

- **Notion Page Properties**:
  - `Type`: Select / Multi-Select / Rich Text with capitalized `"Income"` or `"Expense"`.
  - `Concept` / Title: Concept text or default fallback (`"Income"` / `"Expense"`).
  - `Amount`: Positive floating point number (`abs(amount)`).
  - Adaptive schema matching handles custom column names (`Type`, `Transaction Type`, `Kind`, etc.).
- **Export Formats**:
  - CSV Header: `Timestamp (UTC),Type,Amount,Currency,Category,Concept,Logged By`
  - JSON Schema: includes `"type": "income"` | `"expense"` per item in `transactions` array.

## Dev Agent Record

### Agent Model Used

Gemini 3.7 Flash (High)

### Debug Log References

- Baseline test suite verified (182/182 tests passing).
- Red-Green-Refactor cycle executed for Notion service property building, fallback resilience, and sync.
- Red-Green-Refactor cycle executed for CSV and JSON export routines.
- Full test suite execution: 189 passed out of 189 tests in 52.91s.
- `compileall` syntax validation completed with 0 errors.

### Completion Notes List

- Updated `NotionService._build_page_properties` in `src/services/notion_service.py` to support `Type` select, multi-select, and rich_text properties with values `"Income"` vs `"Expense"`.
- Disambiguated category mapping so "type" is reserved for transaction type properties rather than category tags.
- Added graceful schema fallback: if the target Notion database does not contain a `Type` property, the service logs a debug message and creates the page without failure.
- Updated `NotionService.sync_pending_transactions` and `test_connection_mirror` to propagate transaction type.
- Updated `ExportService._decrypt_transaction` in `src/services/export_service.py` to extract `type` (`"expense"` or `"income"`) onto `DecryptedTransaction`.
- Updated `ExportService.generate_csv` to include `Type` in CSV headers and records.
- Updated `ExportService.generate_json` to include `"type"` field in transaction objects in JSON export.
- Added comprehensive unit and integration tests in `tests/services/test_notion_service.py` and `tests/services/test_export_service.py`.

### File List

- `src/services/notion_service.py`
- `src/services/export_service.py`
- `src/db/models.py`
- `src/services/ai_orchestrator.py`
- `tests/services/test_notion_service.py`
- `tests/services/test_export_service.py`
- `_bmad-output/implementation-artifacts/8-5-notion-mirroring-and-export-updates.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`

### Change Log

- 2026-08-25: Implemented Story 8.5 (Notion Mirroring & Export Updates for Income Records). All acceptance criteria satisfied and 189/189 tests passing.
