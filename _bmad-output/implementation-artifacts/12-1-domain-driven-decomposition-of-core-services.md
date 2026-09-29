---
story_id: "12.1"
epic_id: "12"
title: "Domain-Driven Decomposition of Core Services"
status: "done"
priority: "high"
---

# Story 12.1: Domain-Driven Decomposition of Core Services

## User Story
As a Software Engineer,
I want the large monolithic services decoupled into sub-packages with backwards-compatible shims,
So that the codebase is modular, testable, and maintainable without breaking existing imports.

## Acceptance Criteria
- [x] Decompose `extraction_service.py` into package `src/services/extraction/` (`models.py`, `normalizers.py`, `prompts.py`, `fallback.py`, `service.py`).
- [x] Decompose `query_service.py` into package `src/services/query/` (`models.py`, `date_resolver.py`, `aggregator.py`, `formatters.py`, `service.py`).
- [x] Extract command handlers from `ai_orchestrator.py` into `src/services/handlers/` (`family_handler.py`, `notion_handler.py`, `currency_handler.py`, `account_handler.py`).
- [x] Maintain backwards-compatible re-export shims at `src/services/extraction_service.py` and `src/services/query_service.py`.
- [x] Ensure all 347 tests pass without import errors.

## Tasks / Subtasks
- [x] **Extraction Decomposition** (AC: 1, 4)
  - [x] Modularize extraction logic and create re-export shim.
- [x] **Query Decomposition** (AC: 2, 4)
  - [x] Modularize query calculations and create re-export shim.
- [x] **Handler Extraction** (AC: 3)
  - [x] Extract specialized domain handlers in `src/services/handlers/`.
- [x] **Regression Suite** (AC: 5)
  - [x] Run full pytest suite across all modules.
