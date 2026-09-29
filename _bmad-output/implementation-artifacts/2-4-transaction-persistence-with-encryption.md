# Story 2.4: Transaction Persistence with Encryption

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a User,
I want my logs to be saved permanently and securely,
so that I can review my spending later.

## Acceptance Criteria

1. **User/Family Retrieval**: Retrieve the `User` from the database using the provided `user_id` (UUID string) to resolve their `family_id` context.
2. **Application-Level Encryption**: Encrypt fields before database insertion using the existing `EncryptionService`:
   - `amount`: Plaintext format is `f"{result.amount} {result.currency}"` (e.g., `"15.0 USD"`).
   - `concept`: Raw description string.
3. **Transaction Persistence**: Create and save a new `Transaction` record in the PostgreSQL database.
4. **Multi-Tenancy Scoping**: Populate both `family_id` and `user_id` on the transaction.
5. **n8n Callback on Success**: Send a success webhook callback to n8n containing the decrypted transaction details.
6. **Error Callback on Failure**: Catch database or encryption failures, rollback the transaction, log the error, and notify n8n with `status: "error"` and a user-friendly message (e.g., `"Failed to save transaction. Please try again later."`).
7. **Performance Preservation**: Run all database operations asynchronously within the background task to keep webhook responses under 100ms and total orchestration under 3 seconds.
8. **Unit & Integration Testing**: Include unit tests verifying database persistence, field encryption, rollback on failure, and correct ID mappings.

## Tasks / Subtasks

- [x] **AI Orchestrator Persistence Implementation** (AC: 1, 2, 3, 4, 5, 6, 7)
  - [x] Import `Session` from `sqlmodel` and `engine` from `src.db.session`.
  - [x] Import `User` and `Transaction` from `src.db.models`.
  - [x] Import `EncryptionService` from `src.core.encryption`.
  - [x] Wrap database operations in `with Session(engine) as session:` context.
  - [x] Query the database by `UUID(user_id)` to resolve `family_id`.
  - [x] Encrypt `f"{result.amount} {result.currency}"` and `result.concept` via `EncryptionService`.
  - [x] Instantiate `Transaction` with encrypted values, keeping `timestamp` as timezone-aware UTC datetime.
  - [x] Wrap `session.commit()` in a try-except block; call `session.rollback()` and raise if it fails.
  - [x] Handle exceptions by setting `status = "error"` and sending the error callback to n8n.
- [x] **Unit & Integration Testing** (AC: 8)
  - [x] Update `tests/services/test_ai_orchestrator.py` to mock `Session` and `engine`.
  - [x] Assert that `Transaction` is created, fields are encrypted, and `session.commit()` is called.
  - [x] Use a mocked context manager pattern for the session to prevent hitting the real database.
  - [x] Add a unit test verifying the database commit failure flow (verify rollback and error callback).
  - [x] Run test suite with `PYTHONPATH=. venv/Scripts/python -m pytest` and ensure all tests pass.

### Review Findings

- [x] [Review][Patch] Required category field omitted from Transaction creation [src/services/ai_orchestrator.py:62-68]
- [x] [Review][Patch] Synchronous Database Access Blocks Event Loop [src/services/ai_orchestrator.py:56-70]
- [x] [Review][Patch] Missing Guard for User with Null family_id [src/services/ai_orchestrator.py:66]
- [x] [Review][Patch] Uncaught ValueError on Invalid user_id UUID String [src/services/ai_orchestrator.py:58-63]
- [x] [Review][Patch] Redundant manual session rollback and nested try-except block [src/services/ai_orchestrator.py:56-74]
- [x] [Review][Patch] EncryptionService Instantiated Per-Request [src/services/ai_orchestrator.py:52]
- [x] [Review][Patch] Unawaited Coroutine Mock raise_for_status in Tests [tests/services/test_ai_orchestrator.py]
- [x] [Review][Defer] Logging raw exception exposes potential database context details [src/services/ai_orchestrator.py:76] — deferred, pre-existing

## Dev Notes

- **Reinvention Prevention**: Reuse `EncryptionService` from `src/core/encryption.py` for field-level encryption. Do not write a new encryption library.
- **Encryption String Format**: Plaintext amount is formatted as `f"{amount} {currency}"` (e.g. `"15.0 USD"`) before calling `encrypt()`. This is because there is no separate currency column in the database schema; encrypting them together in the `amount` string securely preserves the currency information.
- **Database Session Safety**: Use a fresh `Session(engine)` context manager inside the background orchestrate task to avoid sharing sessions across threads/requests and prevent `DetachedInstanceError`.
- **Transaction Rollbacks**: Always perform `session.rollback()` inside the exception handling blocks of database operations to maintain database session consistency.
- **Testing Context Manager Mock**: When mocking `Session(engine)`, ensure you mock `__enter__` to return the mock session instance.
  *Example:*
  ```python
  mock_session = MagicMock()
  mock_session_class = MagicMock()
  mock_session_class.return_value.__enter__.return_value = mock_session
  monkeypatch.setattr("src.services.ai_orchestrator.Session", mock_session_class)
  ```

### Project Structure Notes

- **Orchestrator File**: `src/services/ai_orchestrator.py`
- **Tests File**: `tests/services/test_ai_orchestrator.py`
- **Models File**: `src/db/models.py` (defines `Transaction` schema)

### References

- [Architecture: Data Architecture](file:///C:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/architecture.md#L113)
- [Architecture: Complete Project Directory Structure](file:///C:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/architecture.md#L196)
- [Epics: Story 2.4](file:///C:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/epics.md#L208)
- [PRD: Privacy Core](file:///C:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/prd.md#L79)

## Dev Agent Record

### Agent Model Used

Gemini 3.5 Flash (High)

### Debug Log References

### Completion Notes List

- Implemented database persistence for transactions in `AIOrchestrator` using `sqlmodel`.
- Added encryption to the transaction's `amount` and `concept` strings via `EncryptionService`.
- Added proper try-except wrapping around database transactions with `.rollback()` handling.
- Successfully wrote unit tests using `unittest.mock.MagicMock` to simulate `sqlmodel.Session` and `EncryptionService`.
- All 43 tests pass, meaning regression suite checks out fine.

### File List

- `src/services/ai_orchestrator.py`
- `tests/services/test_ai_orchestrator.py`
