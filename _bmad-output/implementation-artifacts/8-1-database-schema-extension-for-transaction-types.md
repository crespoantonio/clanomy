---
story_id: "8.1"
epic_id: "8"
title: "Database Schema Extension for Transaction Types"
status: "done"
priority: "high"
---

# Story 8.1: Database Schema Extension for Transaction Types

## User Story
As a Developer,
I want to extend the `Transaction` model with a `type` discriminator field,
So that both income and expense transactions can be stored securely and uniformly with application-level encryption.

## Acceptance Criteria
- [ ] Update `src/db/models.py` to add `type: str = Field(default="expense", index=True)` to the `Transaction` SQLModel.
- [ ] Ensure permitted values are `"expense"` and `"income"`.
- [ ] Ensure existing SQLite and PostgreSQL database tables default all pre-existing records to `"expense"`.
- [ ] Ensure `amount` and `concept` remain encrypted at rest via `EncryptionService`.
- [ ] Add unit tests in `tests/db/test_models.py` verifying model creation, defaults, type querying, and cascade deletion.

## Tasks / Subtasks

- [x] **Transaction Model Extension** (AC: 1, 2, 3, 4)
  - [x] Add `type: str = Field(default="expense", index=True)` to `Transaction` in `src/db/models.py`.
  - [x] Ensure docstrings, field comments, and default values reflect `"expense"` and `"income"` types.
- [x] **Unit Testing & Verification** (AC: 1, 2, 3, 4, 5)
  - [x] Add unit tests in `tests/db/test_models.py` for default `type="expense"`.
  - [x] Add unit tests in `tests/db/test_models.py` for explicit `type="income"` creation.
  - [x] Add unit tests for querying transactions filtered by `type` ("expense" vs "income").
  - [x] Ensure encryption of `amount` and `concept` is verified for both income and expense records.
  - [x] Verify cascade deletion remains functional for both types.
  - [x] Run full test suite (`python -m pytest`) to ensure 0 regressions.


### Review Findings

- [x] [Review][Decision] Missing Database Migration and Server Default — No Alembic migration script was generated, violating AC 3. Furthermore, the models.py field needs sa_column_kwargs={"server_default": "expense"} to prevent migration crashes on existing rows. Note: AC 3 demands migration but spec scope restricted files.
- [x] [Review][Patch] Missing Enforcement of Permitted Values [src/db/models.py]
- [x] [Review][Patch] Inconsistent Test Data [tests/db/test_models.py]
- [x] [Review][Patch] Missing Right to be Forgotten Test [tests/db/test_models.py]
- [x] [Review][Patch] Date Metadata Inconsistencies [prd.md]
- [x] [Review][Patch] Unbounded VARCHAR Field [src/db/models.py]
- [x] [Review][Defer] Dangerous Defaulting for Ambiguous Input [Architecture docs] — deferred, pre-existing
- [x] [Review][Defer] Incomplete Mathematical Fallback [Architecture docs] — deferred, pre-existing

## Dev Notes

### Architecture & Service Design
- Follow Option A architecture: a unified `Transaction` table avoids dual table joins, duplicative encryption pipelines, and multi-tenant complexity.
- Schema update in `src/db/models.py`:
  ```python
  class Transaction(SQLModel, table=True):
      id: UUID = Field(default_factory=uuid4, primary_key=True)
      family_id: UUID = Field(foreign_key="family.id", index=True, ondelete="CASCADE")
      user_id: UUID = Field(foreign_key="user.id", index=True, ondelete="CASCADE")
      
      # These fields store base64-encoded ciphertext from EncryptionService
      amount: str 
      concept: str 
      
      type: str = Field(default="expense", index=True) # "expense" | "income"
      category: str = Field(index=True)
      timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)

      notion_page_id: Optional[str] = Field(default=None, nullable=True, index=True)
      notion_synced_at: Optional[datetime] = Field(default=None, nullable=True)

      # Relationships
      family: Family = Relationship(back_populates="transactions")
      user: User = Relationship(back_populates="transactions")
  ```

### Developer Context & Constraints
- **Discriminator Values**: The supported values for `type` are `"expense"` and `"income"`.
- **Default Value**: `default="expense"` ensures backwards compatibility for existing transactions and queries that do not specify type.
- **Index**: `index=True` on `type` allows performant filtering for cash flow queries and income aggregations in Story 8.4.
- **Encryption**: Application-level encryption via `EncryptionService` applies identically to both income and expense transactions for `amount` and `concept`.

### Source Files to Touch
- `src/db/models.py`
- `tests/db/test_models.py`

## Dev Agent Record

### Agent Model Used
Gemini 3.7 Flash (High)

### Debug Log References
- Baseline test suite pass: 141 passed in 34.50s.
- Red phase pytest on `tests/db/test_models.py`: 4 failed as expected (AttributeError: 'Transaction' object has no attribute 'type').
- Green phase pytest on `tests/db/test_models.py`: 16 passed in 0.60s.
- Full test suite regression check: 146 passed in 29.67s.

### Completion Notes List
- Added `type: str = Field(default="expense", index=True)` to `Transaction` model in `src/db/models.py`.
- Added unit tests in `tests/db/test_models.py` covering default type assignment, explicit income type, querying filtered by type, encryption/decryption roundtrip of amount and concept for both types, and cascade deletion.
- Verified all 146 tests pass with 0 regressions.

### File List
- `src/db/models.py`
- `tests/db/test_models.py`
- `_bmad-output/implementation-artifacts/8-1-database-schema-extension-for-transaction-types.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`

### Change Log
- 2026-08-25: Implemented database schema extension for transaction types (income/expense discriminator) with comprehensive unit tests and verified 100% test pass rate.



