---
story_id: "10.1"
epic_id: "10"
title: "ScheduledBill Database Model & Encrypted Schema Migration"
status: "done"
priority: "high"
---

# Story 10.1: ScheduledBill Database Model & Encrypted Schema Migration

## User Story
As a Developer,
I want to create a `ScheduledBill` table with encrypted fields and foreign keys,
So that upcoming household obligations are stored securely with zero-knowledge privacy.

## Acceptance Criteria
- [x] Create `ScheduledBill` SQLModel in `src/db/models.py` with:
  - `id: UUID = Field(default_factory=uuid4, primary_key=True)`
  - `family_id: UUID = Field(foreign_key="family.id", index=True, ondelete="CASCADE")`
  - `user_id: UUID = Field(foreign_key="user.id", index=True, ondelete="CASCADE")`
  - `amount: str` (ciphertext)
  - `concept: str` (ciphertext)
  - `category: str = Field(index=True)`
  - `due_date: datetime = Field(index=True)`
  - `status: str = Field(default="pending", index=True, max_length=15)`
  - `paid_transaction_id: Optional[UUID] = Field(default=None, foreign_key="transaction.id", ondelete="SET NULL")`
- [x] Author Alembic migration `0006_add_scheduled_bill.py`.
- [x] Add relationship on `Family` (`scheduled_bills: List["ScheduledBill"]`).
- [x] Verify model CRUD and field encryption with unit tests in `tests/services/test_scheduled_bills.py`.

## Tasks / Subtasks
- [x] **Model Definition** (AC: 1, 3)
  - [x] Add `ScheduledBill` model and update `Family` relationships in `src/db/models.py`.
- [x] **Database Migration** (AC: 2)
  - [x] Create `alembic/versions/0006_add_scheduled_bill.py`.
- [x] **Test Verification** (AC: 4)
  - [x] Add test cases in `tests/services/test_scheduled_bills.py`.
