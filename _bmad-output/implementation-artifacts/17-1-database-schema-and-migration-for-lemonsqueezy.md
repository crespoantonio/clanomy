# Story 17.1: Database Schema & Migration for Lemon Squeezy

**Epic:** Epic 17 - Merchant of Record (Lemon Squeezy) Subscription Engine & Cloud Billing Integration
**Status:** Completed
**Author:** Amelia & Winston
**Date:** 2026-09-02

---

## 1. Overview & Context

To support real fiat subscriptions via Lemon Squeezy (replacing legacy Telegram Stars), the database schema requires tracking external customer, subscription, and variant IDs.

---

## 2. Technical Implementation

### 2.1 Model Updates
- In `src/db/models.py`:
  - Added to `Family`:
    - `lemonsqueezy_customer_id: Optional[str] = Field(default=None, nullable=True)`
    - `lemonsqueezy_subscription_id: Optional[str] = Field(default=None, nullable=True)`
    - `lemonsqueezy_variant_id: Optional[str] = Field(default=None, nullable=True)`

### 2.2 Alembic Migration
- Created `alembic/versions/0009_add_lemonsqueezy_fields.py`:
  - Adds the three columns with indexes where appropriate.
  - Safe, non-destructive migration.

---

## 3. Verification & Acceptance

- Validated via `tests/db/test_migrations.py`.
- Verified all fields instantiate as `None` for existing and new self-hosted families.
