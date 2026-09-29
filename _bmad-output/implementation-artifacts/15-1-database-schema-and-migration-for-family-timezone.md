# Story 15.1: Database Schema & Migration for Family Timezone

**Epic:** Epic 15 - Household Timezone Support & Dynamic Temporal Resolution
**Status:** Completed
**Author:** Amelia & Winston
**Date:** 2026-09-01

---

## 1. Overview & Context

To support global users whose local day/month boundaries differ from server UTC time, the database requires persisting each household's timezone.

---

## 2. Technical Implementation

### 2.1 SQLModel Model Update
- In `src/db/models.py`:
  - Added `timezone: str = Field(default="UTC", max_length=64)` to `Family`.

### 2.2 Alembic Migration
- Created `alembic/versions/0008_add_timezone_support.py`:
  - Adds column `timezone` with server default `"UTC"`.
  - Upgrades schema idempotently without data loss.

---

## 3. Verification & Acceptance

- Validated via `tests/db/test_migrations.py`.
- Verified column exists with default `"UTC"` on fresh database initialization.
