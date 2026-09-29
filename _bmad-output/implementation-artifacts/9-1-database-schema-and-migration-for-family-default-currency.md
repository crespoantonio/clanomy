---
story_id: "9.1"
epic_id: "9"
title: "Database Schema & Migration for Family Default Currency"
status: "done"
priority: "high"
---

# Story 9.1: Database Schema & Migration for Family Default Currency

## User Story
As a Developer,
I want to add a `default_currency` field to the `Family` model with a database migration,
So that each household can store and maintain its primary operating currency.

## Acceptance Criteria
- [x] Update `src/db/models.py` to add `default_currency: str = Field(default="USD", sa_column_kwargs={"server_default": "USD"}, max_length=3)` to `Family`.
- [x] Create Alembic revision `0005_add_family_default_currency.py` adding `default_currency` column to `family` with server default `'USD'`.
- [x] Ensure existing family rows default cleanly to `"USD"`.
- [x] Verify model defaults and database roundtrips via unit tests in `tests/services/test_query_service.py` and `tests/unit/test_subscription_schema.py`.

## Tasks / Subtasks
- [x] **Model Update** (AC: 1, 3)
  - [x] Add `default_currency` field with SQLModel annotations in `src/db/models.py`.
- [x] **Alembic Migration** (AC: 2, 3)
  - [x] Author migration `alembic/versions/0005_add_family_default_currency.py`.
  - [x] Verify forward and backward downgrade steps.
- [x] **Testing & Verification** (AC: 4)
  - [x] Add automated checks for default values and column constraints.
