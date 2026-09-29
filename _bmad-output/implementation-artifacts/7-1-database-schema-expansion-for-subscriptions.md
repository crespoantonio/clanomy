---
story_id: "7.1"
epic_id: "7"
title: "Database Schema Expansion for Subscriptions & 60-Day Trials"
status: "done"
priority: "high"
---

# Story 7.1: Database Schema Expansion for Subscriptions & 60-Day Trials

Status: done

## User Story

As a Developer,  
I want to expand the database models to support subscription tracking, 60-day trials, member caps, monthly reset tracking, and notification states,  
So that we can manage quotas, active Pro plans, and proactive lifecycle messaging reliably.

## Acceptance Criteria

- [x] Update `Family` model in `src/db/models.py` to include:
  - `plan_type: str = Field(default="free")` (allowed values: `"free"`, `"trial"`, `"solo_pro"`, `"family_pro"`, `"lifetime_pro"`).
  - `subscription_status: str = Field(default="active")` (allowed values: `"active"`, `"cancelled"`, `"expired"`).
  - `monthly_tx_count: int = Field(default=0)`
  - `last_reset_month: Optional[str] = Field(default=None)` (e.g., `"2026-08"`, enabling zero-cron lazy monthly counter resets).
  - `max_members: int = Field(default=5)`
  - `trial_ends_at: Optional[datetime] = Field(default=None)`
  - `current_period_end: Optional[datetime] = Field(default=None)`
  - `telegram_payment_charge_id: Optional[str] = Field(default=None)`
  - `notified_day_50: bool = Field(default=False)`
  - `notified_day_60: bool = Field(default=False)`
- [x] Update `User` model in `src/db/models.py` to include:
  - `has_used_trial: bool = Field(default=False)`
- [x] Update `src/services/subscription_service.py` to recognize all plan types and enforce trial & unmetered plan logic.
- [x] Explicitly enforce security rule: `lifetime_pro` is reserved exclusively for direct database administration and MUST NOT be exposed via user commands, LLM tools, or webhook activations.
- [x] Add/update unit tests in `tests/unit/test_subscription_schema.py` and `tests/db/test_models.py`.

## Technical Notes

- `lifetime_pro` can ONLY be configured via direct database update.
- Backward compatibility: existing family records default to `"free"` with `monthly_tx_count = 0`.

## File List

- `src/db/models.py` (Modified)
- `src/services/subscription_service.py` (Modified)
- `alembic/versions/0002_subscription_schema_expansion.py` (Created)
- `tests/unit/test_subscription_schema.py` (Modified)
- `tests/db/test_models.py` (Modified)
- `tests/db/test_migrations.py` (Modified)

## Dev Agent Record

### Implementation Plan
1. Update `Family` SQLModel in `src/db/models.py` with `plan_type`, `subscription_status`, `monthly_tx_count`, `last_reset_month`, `max_members`, `trial_ends_at`, `current_period_end`, `telegram_payment_charge_id`, `notified_day_50`, and `notified_day_60`.
2. Update `User` SQLModel in `src/db/models.py` with `has_used_trial`.
3. Update `src/services/subscription_service.py` with `is_unlimited_plan`, `has_unlimited_access` (supporting active trials with date validation), `check_and_reset_monthly_quota` (zero-cron lazy monthly counter reset), `can_log_transaction`, and strict `validate_invoice_payload` payload validation protecting `lifetime_pro`.
4. Create Alembic migration `0002_subscription_schema_expansion.py`.
5. Author comprehensive unit tests in `tests/unit/test_subscription_schema.py`, `tests/db/test_models.py`, and `tests/db/test_migrations.py`.
6. Run full regression test suite (207 tests passed).

### Completion Notes
- âœ… Added `last_reset_month`, `max_members`, `trial_ends_at`, `notified_day_50`, `notified_day_60` to `Family` model in `src/db/models.py`.
- âœ… Added `has_used_trial` to `User` model in `src/db/models.py`.
- âœ… Extended `subscription_service.py` with trial expiration checking, zero-cron lazy monthly quota resets, and strict whitelist validation preventing injection of `lifetime_pro`.
- âœ… Created Alembic migration `0002_subscription_schema_expansion.py` and updated migration tests.
- âœ… 100% of unit, db, and full regression tests passing (207/207 tests pass).

## Change Log

- **2026-08-26**: Expanded `Family` and `User` schema models for Epic 7 subscription & 60-day trial tracking, added migration `0002_subscription_schema_expansion`, updated `subscription_service.py`, and added comprehensive unit and integration tests.

### Review Findings

- [x] [Review][Patch] Side-Effect and Lost Quota Resets (Extract to separate method) in can_log_transaction â€” Mutates quota state in a read-only check but fails to commit it. Should the reset be extracted to a separate command, or should we just commit inside the check?
- [x] [Review][Patch] Fail-Open Trial Exploit â€” 	rial_ends_at is None grants permanent unlimited access. [src/services/subscription_service.py]
- [x] [Review][Patch] Transaction Lockout for Expired Trials/Pro Plans â€” Users locked out completely instead of falling back to free tier. [src/services/subscription_service.py]
- [x] [Review][Patch] Broken SQLite Downgrade Migration â€” op.drop_column used instead of atch_alter_table for SQLite compatibility. [alembic/versions/0002_subscription_schema_expansion.py]
- [x] [Review][Patch] Unused has_used_trial field â€” No enforcement logic exists to prevent multiple trials. [src/services/subscription_service.py]
- [x] [Review][Patch] Missing Validation for Allowed Plan Types â€” Missing Enums/validators in the models. [src/db/models.py]
- [x] [Review][Patch] Hardcoded Magic Numbers â€” Free tier limit is hardcoded as limit=30 in method signature. [src/services/subscription_service.py]
- [x] [Review][Patch] Brittle Server Default Syntax â€” Boolean defaults use raw strings like server_default='false' instead of dialect-appropriate defaults. [alembic/versions/0002_subscription_schema_expansion.py]
- [x] [Review][Defer] Clunky Timezone Handling and Missing Tests [src/services/subscription_service.py] â€” deferred, pre-existing
- [x] [Review][Defer] Missing Indexes for Background Jobs [src/db/models.py] â€” deferred, pre-existing



