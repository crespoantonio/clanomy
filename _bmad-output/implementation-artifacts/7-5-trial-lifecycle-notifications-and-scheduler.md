---
story_id: "7.5"
epic_id: "7"
title: "Proactive Trial Lifecycle Notifications Scheduler (Day 50 & Day 60)"
status: "review"
priority: "medium"
---

# Story 7.5: Proactive Trial Lifecycle Notifications Scheduler (Day 50 & Day 60)

Status: review

## User Story

As a User,  
I want to be proactively notified 10 days before my trial ends and when my trial completes,  
So that I understand my transition to the Free tier, know that my past data is safe, and have a clear option to subscribe.

## Acceptance Criteria

- [x] Implement a daily trial notification task/service in `src/services/notification_scheduler.py`:
  - Queries active trial families where `trial_ends_at <= now() + 10 days` and `notified_day_50 == False`.
  - Queries expired trial families where `trial_ends_at <= now()` and `notified_day_60 == False` with no active paid plan.
- [x] Format and send the **Day 50 Nudge Message**:
  - Summarizes value delivered (transactions tracked by family during the trial).
  - Warns that the 60-day trial will finish in 10 days.
  - Presents available tiers (**Family Pro** 300 Stars/mo, **Solo Pro** 150 Stars/mo) and `/upgrade` CTA.
  - Sets `Family.notified_day_50 = True`.
- [x] Format and send the **Day 60 Transition Message**:
  - Automatically transitions `Family.plan_type` to `"free"`.
  - Reassures user that all historical data, past Ask queries, and Notion sync remain 100% safe and intact.
  - Clearly explains the Free tier limits: 30 transaction logs/month shared across the family workspace.
  - Provides a friendly `/upgrade` CTA.
  - Sets `Family.notified_day_60 = True`.
- [x] Add unit and mock integration tests in `tests/services/test_notification_scheduler.py`.

## Tasks / Subtasks

- [x] **Task 1: Trial Query & Notification Service in `src/services/notification_scheduler.py`** (AC: 1, 2, 3)
  - [x] Implement `NotificationScheduler` class and helper methods in `src/services/notification_scheduler.py`.
  - [x] Implement `get_day_50_trial_families(session, now=None)` querying active trial families (`plan_type == "trial"`, `trial_ends_at <= now + 10 days`, `trial_ends_at > now`, `notified_day_50 == False`).
  - [x] Implement `get_day_60_trial_families(session, now=None)` querying expired trial families (`trial_ends_at <= now`, `notified_day_60 == False`, and `plan_type not in ("solo_pro", "family_pro", "lifetime_pro")`).
  - [x] Implement `format_day_50_message(family, tx_count)` with value summary, 10-day notice, tier breakdown, and `/upgrade` CTA.
  - [x] Implement `format_day_60_message(family)` with free tier transition, 100% data safety assurance, 30 logs/mo explanation, and `/upgrade` CTA.
  - [x] Implement `process_day_50_notifications(session, telegram_service=None, now=None)` to count transactions, notify members with `telegram_id`, and update `notified_day_50 = True`.
  - [x] Implement `process_day_60_notifications(session, telegram_service=None, now=None)` to transition `plan_type = "free"`, update `notified_day_60 = True`, and notify members with `telegram_id`.
  - [x] Implement `run_daily_trial_notifications(session=None, engine=None, telegram_service=None, now=None)` returning a summary dictionary.
- [x] **Task 2: Background Scheduling Lifecycle in FastAPI Lifespan** (AC: 1)
  - [x] Implement background scheduler loop functions (`start_notification_scheduler`, `stop_notification_scheduler`) in `src/services/notification_scheduler.py`.
  - [x] Wire scheduler startup and shutdown into FastAPI `lifespan` in `src/main.py`.
- [x] **Task 3: Comprehensive Unit & Integration Tests in `tests/services/test_notification_scheduler.py`** (AC: 4)
  - [x] Test Day 50 and Day 60 candidate query filtering across various datetime and plan combinations.
  - [x] Test message formatting (Day 50 value summary + CTA, Day 60 data reassurance + limits + CTA).
  - [x] Test Day 50 and Day 60 execution, notification dispatch, state persistence, and idempotency.
  - [x] Test protection for paid plans (`solo_pro`, `family_pro`, `lifetime_pro`).
  - [x] Run full regression suite and verify 100% pass rate.

## File List

- `src/services/subscription_service.py` (Modified)
- `src/api/routes/telegram.py` (Modified)
- `src/services/notification_scheduler.py` (New)
- `src/main.py` (Modified)
- `tests/services/test_notification_scheduler.py` (New)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (Modified)
- `_bmad-output/implementation-artifacts/7-5-trial-lifecycle-notifications-and-scheduler.md` (Modified)

## Dev Agent Record

### Implementation Plan
1. Author `tests/services/test_notification_scheduler.py` covering all ACs (RED phase).
2. Implement `src/services/notification_scheduler.py` with query methods, message formatters, notification dispatchers, and async loop runner (GREEN phase).
3. Connect background task management in `src/main.py` lifespan (REFACTOR phase).
4. Run all unit and integration tests to verify 100% success and execute container build verification.

### Completion Notes
- ✅ Implemented `NotificationScheduler` and `run_daily_trial_notifications` in `src/services/notification_scheduler.py`.
- ✅ Implemented Day 50 trial nudge query, transaction value summary formatter, Telegram dispatch to family members, and `notified_day_50` DB update.
- ✅ Implemented Day 60 trial transition query, Free tier migration (`plan_type = "free"`, `max_members = 1`, `subscription_status = "expired"`), 100% data safety reassurance formatter, Telegram dispatch, and `notified_day_60` DB update.
- ✅ Protected paid plans (`solo_pro`, `family_pro`, `lifetime_pro`) against Day 60 downgrades.
- ✅ Connected background scheduler startup and graceful cancellation in FastAPI `lifespan` in `src/main.py`.
- ✅ Added comprehensive unit and integration tests in `tests/services/test_notification_scheduler.py`.
- ✅ Ran full regression test suite with 255/255 passing tests (100% pass rate).
- ✅ Validated container build with `podman build -t clanomy .`.

## Change Log
- **2026-08-26**: Implemented proactive trial lifecycle notification scheduler (Day 50 nudge & Day 60 Free tier transition), message formatters, FastAPI lifespan integration, and full test suite coverage (255/255 tests passing).
