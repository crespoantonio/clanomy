# Story 21.3: Daily Transaction Quotas & Internal Maintenance Cron

**Epic:** Epic 21 - Three-Tier Pricing Architecture, 60-Day Duo Trial & Daily Fair-Use Quotas
**Status:** Completed
**Author:** Amelia & Winston
**Date:** 2026-09-03

---

## 1. Overview & Context

To prevent runaway API consumption, bot loops, or abuse in SaaS mode, Clanomy enforces fair-use daily rate limits per workspace tier (Trial: 60/day, Solo: 60/day, Duo: 120/day, Family: 300/day). An authenticated internal HTTP maintenance endpoint resets daily counters each midnight and delivers proactive Day 50 and Day 60 trial notifications.

---

## 2. Technical Implementation

### 2.1 Database Schema Migration
- In `alembic/versions/0010_add_family_daily_tx_count.py`:
  - Added `daily_tx_count` column to the `family` table with `default=0`.
  - Incremented on every logged transaction in `AIOrchestrator`.

### 2.2 Quota Enforcement
- In `src/services/subscription_service.py`:
  - Added `can_log_transaction()` check comparing `Family.daily_tx_count` against `DAILY_FAIR_USE_LIMITS[family.plan_type]`.
  - When quota is reached, sends a friendly notice informing the household of the fair-use limit and confirming that reset occurs at midnight.

### 2.3 Internal Maintenance Job Route
- In `src/api/routes/internal_jobs.py`:
  - Implemented `POST /api/internal/jobs/trial-lifecycle`.
  - Authenticated via `X-Job-Secret` or `Authorization: Bearer <CRON_SECRET>` using constant-time comparison (`verify_cron_secret`).
  - Calls `run_daily_trial_notifications(session)`:
    - Resets `daily_tx_count = 0` across all families.
    - Sends Day 50 warning notifications (10 days remaining).
    - Transitions Day 60 expired workspaces to `free` status.

---

## 3. Verification & Acceptance

- Validated via `tests/unit/test_daily_quotas.py`, `tests/api/test_internal_jobs.py`, and `tests/db/test_migrations.py`.
- Verified quota blocking when daily count exceeds tier limit.
- Verified constant-time secret verification rejecting unauthorized HTTP requests with HTTP 401.
