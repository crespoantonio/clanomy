---
story_id: "9.4"
epic_id: "9"
title: "Multi-Currency Query Segregation & Formatting"
status: "done"
priority: "high"
---

# Story 9.4: Multi-Currency Query Segregation & Formatting

## User Story
As a User,
I want my spending summaries and cash flow reports to segregate different currencies cleanly,
So that figures from different currencies are never added together into meaningless totals.

## Acceptance Criteria
- [x] Update `QueryService.aggregate_transactions()` to group transactions by currency and calculate per-currency totals.
- [x] Ensure `generate_fallback_summary()` and LLM prompt context format separate totals per currency.
- [x] Ensure empty-state summaries (0 transactions) render using the household's configured `default_currency` (e.g. `$0.00 ARS`).
- [x] Support bilingual date expressions (*"este mes"*, *"semana pasada"*, *"hoy"*) in `src/services/query/date_resolver.py`.

## Tasks / Subtasks
- [x] **Aggregation Engine** (AC: 1)
  - [x] Update `src/services/query/aggregator.py` with multi-currency buckets.
- [x] **Formatters & Date Resolver** (AC: 2, 3, 4)
  - [x] Update `src/services/query/formatters.py` and `date_resolver.py`.
- [x] **Testing**
  - [x] Test cases in `tests/services/test_query_service.py` for multi-currency segregation and empty states.
