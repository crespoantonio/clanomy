# Story 1.3: Multi-Tenant Database Schema (SQLModel)

Status: ready-for-dev

## Story

**As a Developer,**
I want a database schema that supports families and encrypted transactions,
so that I can store data with strict isolation and security.

## Acceptance Criteria

1. **Given** the `src/db/models.py` file, **when** I define the `User`, `Family`, and `Transaction` models, **then** they are correctly mapped to PostgreSQL tables via SQLModel.
2. **And** the `Transaction` model includes a mandatory `family_id` foreign key with an index for high-performance multi-tenant filtering.
3. **And** the `Transaction` model includes a `user_id` foreign key to attribute expenses to specific family members.
4. **And** sensitive fields (`amount`, `concept`) in the `Transaction` model are defined as `String` (to store the base64-encoded Fernet ciphertext from `EncryptionService`).
5. **And** all models use `UUIDv4` as the primary key type for global uniqueness and to avoid leaking record counts via sequential IDs.
6. **And** appropriate bidirectional `Relationship` attributes are defined (e.g., `Family.users`, `User.transactions`, `Family.transactions`).
7. **And** the `init_db` function in `src/db/session.py` is updated to create all tables in the database on application startup.

## Tasks / Subtasks

- [x] **Model Definition** (AC: 1, 2, 3, 4, 5, 6)
  - [x] Implement `Family` model in `src/db/models.py`.
  - [x] Implement `User` model in `src/db/models.py` with `telegram_id` (unique index).
  - [x] Implement `Transaction` model in `src/db/models.py` with `family_id` and `user_id`.
  - [x] Add `Relationship` attributes for all models to enable easy navigation.
- [x] **Database Initialization** (AC: 7)
  - [x] Update `src/db/session.py`'s `init_db()` to call `SQLModel.metadata.create_all(engine)`.
  - [x] Register `init_db()` in `src/main.py` using a FastAPI `lifespan` event or an `on_event("startup")` (lifespan is preferred in modern FastAPI).
- [x] **Unit Testing** (AC: 1, 2, 6)
  - [x] Create `tests/db/test_models.py`.
  - [x] Test creating a complete hierarchy: Family -> User -> Transaction.
  - [x] Verify that deleting a Family cascades to its Transactions (GDPR compliance).
  - [x] Verify that `family_id` is required for every Transaction.

### Review Findings

- [x] [Review][Patch] Missing DB-level `CASCADE` [`src/db/models.py`:40-41]
- [x] [Review][Patch] Missing explicit `BIGINT` for Telegram ID [`src/db/models.py`:24]
- [x] [Review][Patch] Unhandled `init_db()` failure [`src/main.py`:10]
- [x] [Review][Patch] Missing `user_id` index in `Transaction` [`src/db/models.py`:41]
- [x] [Review][Patch] Potential conflicting cascades [`src/db/models.py`:17,32]
- [x] [Review][Defer] Lack of Alembic/Migrations [`src/db/session.py`:11] — deferred, pre-existing

## Developer Context

- **Multi-Tenancy**: This is the most critical architectural constraint. Every query in future stories (Epic 3) will be scoped by `family_id`. Ensure the field is indexed.
- **Encryption Storage**: Fields `amount` and `concept` MUST store ciphertext. While the PRD says "Amount" is a number, in the DB it must be a `String` (Ciphertext) because we encrypt at the application level.
- **Library**: We use `SQLModel` which combines Pydantic and SQLAlchemy. Refer to the documentation for `Relationship` and `Field(foreign_key=...)`.
- **Identity**: `telegram_id` is the unique identifier for users coming from the bot. Use `BigInt` for this field as Telegram IDs can be large.

### Naming Conventions (Architecture Compliance)
- Tables: `snake_case` (e.g., `transaction`, `family`, `user`).
- Fields: `snake_case`.
- Classes: `PascalCase`.

### Technical Guardrails
- **Primary Keys**: `uuid.UUID`, `default_factory=uuid.uuid4`.
- **Foreign Keys**: Use `ondelete="CASCADE"` for transactions linked to users/families.
- **Encrypted Fields**: Store as `String`.

## Architecture Compliance

- **Location**: `src/db/models.py`.
- **ORM**: SQLModel.
- **DB**: PostgreSQL.
- **Pattern**: Service Layer pattern (Business logic stays out of models).

## Previous Story Intelligence (1.2)

- The `EncryptionService` in `src/core/encryption.py` is ready. It returns URL-safe base64 strings.
- The DB models defined here will receive these strings during the save operation (to be implemented in Story 2.4).

## Latest Technical Specifics (SQLModel)

- Ensure you import `Relationship` and `Field` from `sqlmodel`.
- For `UUID` support, use the standard `uuid` module.
- For `DateTime`, use `datetime.datetime` with `default_factory=datetime.utcnow`.

## Project Context Reference

- [Architecture: Data Architecture](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/architecture.md#L112)
- [Architecture: Project Structure](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/architecture.md#L192)
- [Epics: Story 1.3](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/epics.md#L137)

## Dev Agent Record

### Agent Model Used

Gemini 2.0 Flash

### Debug Log References

- [pytest results](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/tests/db/test_models.py) - 5 tests passed (SQLite in-memory).

### Completion Notes List

- Implemented `Family`, `User`, and `Transaction` models in `src/db/models.py`.
- Enforced `family_id` scoping on `Transaction` and `User` models.
- Defined sensitive fields (`amount`, `concept`) as `String` for ciphertext storage.
- Implemented `UUIDv4` primary keys for all models.
- Added bidirectional relationships with cascade deletes for data integrity.
- Updated `src/db/session.py` to support table creation.
- Registered `init_db()` in `src/main.py` via FastAPI `lifespan` event.
- Verified implementation with unit tests covering hierarchy creation and multi-tenant constraints.

### File List
- `src/db/models.py`
- `src/db/session.py`
- `src/main.py`
- `tests/db/test_models.py`

### Change Log
- Initial implementation of the multi-tenant database schema (2026-05-09).

## Story Completion Status

- **Status**: done
- **Analysis**: Implementation complete, code review findings addressed, and verified via unit tests.
- **Date**: 2026-05-09
