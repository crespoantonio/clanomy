---
story_id: "10.4"
epic_id: "10"
title: "Proactive Due & Overdue Bill Alerts in Status Queries"
status: "done"
priority: "high"
---

# Story 10.4: Proactive Due & Overdue Bill Alerts in Status Queries

## User Story
As a User,
I want to be reminded of pending or overdue bills whenever I check our monthly financial status,
So that our household never misses an obligation.

## Acceptance Criteria
- [x] In `QueryService._execute_parsed_query()`, check for pending `ScheduledBill` records in the current timeframe month.
- [x] Identify bills where `due_date <= now()`.
- [x] Format a friendly alert block summarizing overdue and approaching obligations.
- [x] Include proactive settlement instructions (e.g. *`"Si ya pagaste alguna, solo dime 'Pagué la visa'"`*).
- [x] Append the alert block seamlessly to `spending_summary` and `net_cash_flow` responses.

## Tasks / Subtasks
- [x] **Query Engine Integration** (AC: 1, 2)
  - [x] Query pending bills in `src/services/query/service.py`.
- [x] **Alert Formatting** (AC: 3, 4, 5)
  - [x] Generate localized alert blocks in `src/services/query/formatters.py`.
- [x] **Testing**
  - [x] Unit tests in `tests/services/test_scheduled_bills.py` verifying status queries include pending bill alerts.
