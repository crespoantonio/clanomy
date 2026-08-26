---
story_id: "7.1"
epic_id: "7"
title: "Database Schema Expansion for Subscriptions & 60-Day Trials"
status: "ready-for-dev"
priority: "high"
---

# Story 7.1: Database Schema Expansion for Subscriptions & 60-Day Trials

Status: ready-for-dev

## User Story

As a Developer,  
I want to expand the database models to support subscription tracking, 60-day trials, member caps, monthly reset tracking, and notification states,  
So that we can manage quotas, active Pro plans, and proactive lifecycle messaging reliably.

## Acceptance Criteria

- [ ] Update `Family` model in `src/db/models.py` to include:
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
- [ ] Update `User` model in `src/db/models.py` to include:
  - `has_used_trial: bool = Field(default=False)`
- [ ] Update `src/services/subscription_service.py` to recognize all plan types and enforce trial & unmetered plan logic.
- [ ] Explicitly enforce security rule: `lifetime_pro` is reserved exclusively for direct database administration and MUST NOT be exposed via user commands, LLM tools, or webhook activations.
- [ ] Add/update unit tests in `tests/unit/test_subscription_schema.py` and `tests/db/test_models.py`.

## Technical Notes

- `lifetime_pro` can ONLY be configured via direct database update.
- Backward compatibility: existing family records default to `"free"` with `monthly_tx_count = 0`.
