# Story 14.2: Household Member Segregation & Personal Isolation

**Epic:** Epic 14 - Pre-Built Fast-Path Commands & Hybrid Quota Model
**Status:** Completed
**Author:** Amelia & Winston
**Date:** 2026-09-01

---

## 1. Overview & Context

To give household members full financial transparency while maintaining visibility over their personal spending habits, Clanomy implements distinct member aggregation and personal filtering:
- `/month`: Renders the collective household income, expenses, and net savings, followed by a member breakdown displaying each member's earnings, expenditures, net balance, and top expense category.
- `/me`: Isolates strictly the caller's transactions (`user_id == caller.id`), providing a personalized summary with their individual income, expenses, savings rate, and top 4 expense categories.

---

## 2. Technical Implementation

### 2.1 Query Aggregation
- In `src/services/query/aggregator.py`:
  - `aggregate_by_member()` loops over transactions and groups by `user_id`.
  - Maps user metadata (first name, username) to build `MemberSpending` records.
  - Aggregates income totals and expense totals per member with multi-currency tracking.

### 2.2 Formatting Logic
- In `src/services/query/formatters.py`:
  - `format_month_summary()` renders `👥 Member Breakdown` with icons and percentages.
  - `format_me_summary()` renders caller-specific breakdown, highlighting top expense categories and personal net balance.

### 2.3 Webhook Routing
- In `src/services/handlers/command_handler.py`:
  - Handles `/month` (and `/resumen`) and `/me` (and `/yo`) directly in Python/SQL without AI token consumption.

---

## 3. Verification & Acceptance

- Validated with unit tests in `tests/services/test_command_handlers.py`.
- Verified multi-user households render distinct member totals and individual categories accurately.
