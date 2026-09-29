# Story 4.2: Account Deletion ("Right to be Forgotten")

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a User,
I want to permanently delete my account and all associated transaction records via the bot (GDPR Right to be Forgotten),
so that I retain complete control over my privacy and personal financial data.

## Acceptance Criteria

1. **Deletion Intent Recognition & Confirmation Flow**:
   - Update `ParsedQueryIntent` in `src/services/query_service.py` to recognize deletion intent: `"delete_account"`.
   - Support common natural language triggers: "delete my account", "remove my data", "delete all my transactions", "erase my account", "forget me".
   - Support confirmation safety flow:
     - When the user asks to delete their account, the system prompts with a clear warning:
       `⚠️ Are you sure you want to permanently delete your account and all associated financial records? This action is irreversible.\n\nTo confirm, please reply with: <b>CONFIRM DELETE</b>`
     - If the user sends `CONFIRM DELETE`, the system executes the permanent purge.
     - If the user sends anything else, the deletion request is cancelled.

2. **Atomic Cascade Deletion Engine (`AccountService` or `DeletionService`)**:
   - Implement `AccountService.delete_account(user_id: UUID) -> None` in `src/services/account_service.py`.
   - Execute in a single atomic database transaction using `Session(engine)`:
     - Fetch the `User` and associated `Family`.
     - If the `Family` has no other members (or solely this user), delete the `Family` entity, which triggers SQLModel/SQLAlchemy relationship cascades (`cascade="all, delete-orphan"`) and database foreign key cascades (`ondelete="CASCADE"`) to delete all associated `Transaction` and `User` records.
     - If the `Family` has other members (multi-tenant edge case for Phase 2), delete only this `User` and their attributed transactions, leaving the family intact.
     - Enforce `session.commit()` with `session.rollback()` on any failure.
   - Run the synchronous database deletion in a background thread via `asyncio.to_thread()`.

3. **Multi-Tenant Isolation & Zero Data Residual Guarantee**:
   - Deletion must only delete records belonging to the requesting user/family. No records from any other family or user can ever be affected.
   - Assert via automated tests that querying `User` and `Transaction` tables by `user_id` and `family_id` returns `0` records post-deletion.

4. **Telegram Feedback & Session Termination**:
   - After successful deletion, dispatch a friendly, reassuring confirmation message via Telegram Bot API:
     `✅ Your account and all associated transaction records have been permanently deleted from our database. Thank you for using FamFin-AI! If you ever wish to return, simply send /start.`
   - Ensure that subsequent messages from this Telegram user treat them as a new user requiring registration via `/start` (or recreate a fresh ledger).

5. **Performance & Latency (The 3s Rule)**:
   - Account deletion and confirmation dispatch must complete in `< 1.0s` (measured and logged via `[3s Audit] Account deletion completed in {duration:.2f}s for user_id={user_id}`).

6. **Comprehensive Unit & Integration Test Suite**:
   - Create `tests/services/test_account_service.py`:
     - Test deletion of user and single-member family (verifying all users and transactions in the family are purged).
     - Test multi-user family deletion behavior (verifying only the target user is removed).
     - Test database rollback resilience on simulated commit error.
     - Test confirmation trigger and cancellation parsing.
     - Verify 100% test pass rate with `.\venv\Scripts\python -m pytest`.

## Tasks / Subtasks

- [x] **AccountService Core Deletion Engine** (AC: 2, 3, 5)
  - [x] Create `src/services/account_service.py` (singleton pattern).
  - [x] Implement `delete_account(user_id: UUID) -> bool`:
    - Fetch User and Family.
    - Execute atomic delete with SQLModel cascade.
    - Verify zero residual records.
  - [x] Add `[3s Audit]` performance timer and logger.
- [x] **Query Intent & Confirmation Flow** (AC: 1)
  - [x] Add `intent: "delete_account"` to `ParsedQueryIntent` in `src/services/query_service.py`.
  - [x] Update Ollama system prompt to classify account deletion requests.
  - [x] Update `_is_query_or_export` in `src/services/ai_orchestrator.py` (rename/extend to `_is_special_intent`) to include deletion keywords (`delete`, `remove`, `erase`, `forget`, `purge`, `confirm delete`).
- [x] **AI Orchestrator Integration** (AC: 1, 4)
  - [x] Handle `"delete_account"` intent: return confirmation warning prompt.
  - [x] Handle `"CONFIRM DELETE"` exact message: invoke `AccountService.delete_account()` and send final farewell message.
- [x] **Unit & Integration Test Suite** (AC: 6)
  - [x] Create `tests/services/test_account_service.py`.
  - [x] Test atomic deletion and cascade verification.
  - [x] Test orchestrator handling of `delete_account` and `CONFIRM DELETE`.
  - [x] Run full test suite with `.\venv\Scripts\python -m pytest` and verify 100% passing.

## Change Log

- Created `AccountService` to handle atomic cascade deletions with `SQLModel`
- Updated `QueryService` system prompt to recognize `delete_account` intent
- Renamed `_is_query_or_export` to `_is_special_intent` in `AIOrchestrator`
- Integrated `delete_account` intent confirmation flow and exact match processing
- Added unit tests for `AccountService` and `AIOrchestrator` deletion logic

### Review Findings

- [x] [Review][Patch] Missing Default Database Engine Fallback [src/services/account_service.py:18] — AccountService does not fall back to default db_engine when instantiated without arguments, causing Session(self.engine) to fail in production.
- [x] [Review][Patch] Brittle Inline Duck Typing Object [src/services/ai_orchestrator.py:117] — Replace type('obj', ...) with ParsedQueryIntent(intent="delete_account") for schema safety.

## Dev Notes

### Architecture & Service Design

- **Service Pattern**: Follow the existing singleton pattern in `src/services/export_service.py` and `src/services/query_service.py`.
- **Database Cascade Logic**:
  ```python
  def _delete_account_sync(user_id: UUID) -> None:
      with Session(engine) as session:
          user = session.get(User, user_id)
          if not user:
              return
          family = session.get(Family, user.family_id) if user.family_id else None
          if family and len(family.users) <= 1:
              session.delete(family)
          else:
              session.delete(user)
          session.commit()
  ```
- **Non-blocking Execution**: Run `_delete_account_sync` using `await asyncio.to_thread(_delete_account_sync, user_id)`.

### References

- [Architecture: Multi-Tenant Cascade Deletes Validation](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/architecture.md#L418)
- [Architecture: Data Architecture & Encryption](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/architecture.md#L114)
- [Epics: Story 4.2](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/epics.md#L292)
- [PRD: Data Erasure (FR15)](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/prd.md#L35)
- [Story 4.1 Implementation](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/implementation-artifacts/4-1-financial-data-export-json-csv.md)

## Dev Agent Record

### Agent Model Used

Gemini 3.1 Pro (Low)

### Debug Log References

- Tests failed initially because `ObjectDeletedError` from SQLAlchemy when asserting deleted object fields. Solved by extracting `tx_id` first.
- Replaced `@pytest.mark.asyncio` with `@pytest.mark.anyio` per project test patterns.

### Completion Notes List

- Implemented `AccountService.delete_account` to safely and atomically purge users and families.
- Added `delete_account` intent to `QueryService`.
- Orchestrator handles `delete_account` warnings and processes `CONFIRM DELETE`.
- Covered with passing unit tests. 

### File List

- `src/services/account_service.py` (Created)
- `tests/services/test_account_service.py` (Created)
- `src/services/query_service.py` (Modified)
- `src/services/ai_orchestrator.py` (Modified)
- `tests/services/test_ai_orchestrator.py` (Modified)
