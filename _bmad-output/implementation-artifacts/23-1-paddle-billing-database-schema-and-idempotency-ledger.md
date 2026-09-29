# Story 23.1: Paddle Billing Database Schema & Idempotency Ledger

**Epic:** Epic 23 - Paddle Merchant of Record Billing Integration & Household Governance
**Status:** Completed
**Author:** Amelia & Winston
**Date:** 2026-09-11

---

## 1. Overview & Context

To support Paddle Billing as the primary Merchant of Record without third-party vendor lock-in, the database schema must store external Paddle identifiers, track scheduled subscription lifecycle changes (cancellations and tier migrations), and maintain a robust idempotency ledger for incoming webhook deliveries.

---

## 2. Technical Implementation

### 2.1 Alembic Migration
- `alembic/versions/0013_paddle_subscriptions.py`:
  - Adds `paddle_customer_id` (`VARCHAR`, indexed).
  - Adds `paddle_subscription_id` (`VARCHAR`, indexed).
  - Adds `paddle_price_id` (`VARCHAR`).
  - Adds `scheduled_change_action` (`VARCHAR`).
  - Adds `scheduled_change_effective_at` (`TIMESTAMPTZ`).
  - Creates table `processed_webhook` with primary key `event_id` (`VARCHAR(100)`), `event_type` (`VARCHAR(100)`), and `received_at` (`TIMESTAMPTZ`).
  - Enables Row Level Security (RLS) on PostgreSQL and revokes public schema access from `anon` and `authenticated` roles with safe existence checks.

### 2.2 SQLModel Entities
- In `src/db/models.py`:
  - Updated `Family` with Paddle fields.
  - Defined `ProcessedWebhook` table model with primary key `event_id`.

---

## 3. Verification & Acceptance

- Validated via `tests/db/test_migrations.py`.
- Verified SQLite batch alter and PostgreSQL RLS compatibility.
