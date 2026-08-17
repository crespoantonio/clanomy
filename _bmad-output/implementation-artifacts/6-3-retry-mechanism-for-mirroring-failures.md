# Story 6.3: Retry Mechanism for Mirroring Failures

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a User,
I want the system to automatically retry syncing my transactions if Notion is temporarily down or rate-limited, and allow manual sync catch-up,
so that I never lose a record in my Notion financial dashboard due to transient API failures or network outages.

## Acceptance Criteria

1. **Transient vs. Permanent Error Classification for Notion API**:
   - Classify Notion API and network exceptions into:
     - **Transient (Retryable)**:
       - Network/Connection errors: `httpx.RequestError`, `httpx.TimeoutException`, `httpx.ConnectTimeout`, `httpx.ReadTimeout`.
       - HTTP 429 Rate Limiting (`APIResponseError` with code `rate_limited` or HTTP status 429).
       - HTTP 5xx Server Errors (`APIResponseError` with code `service_unavailable`, `internal_server_error`, or HTTP status 500, 502, 503, 504).
     - **Permanent (Non-Retryable - Fail Immediately)**:
       - HTTP 401 Unauthorized / Invalid Token (`NotionAuthError`, `APIResponseError` with code `unauthorized` or status 401).
       - HTTP 404 Database / Object Not Found (`NotionDatabaseNotFoundError`, `APIResponseError` with code `object_not_found` or status 404).
       - HTTP 400 Bad Request / Validation Error (`APIResponseError` with code `validation_error` or status 400).

2. **Immediate Retry with Exponential Backoff (`tenacity`) in `NotionService`**:
   - Add `tenacity>=9.0.0` to `requirements.txt`.
   - Wrap Notion API operations (such as `notion.pages.create` inside `mirror_transaction` or a dedicated retryable helper `_create_page_with_retry`) using `tenacity.AsyncRetrying` or `@retry` decorator:
     - **Retry condition**: Retry only on transient/retryable exceptions identified in AC 1.
     - **Stop condition**: Stop after 3 attempts (`stop=stop_after_attempt(3)`).
     - **Wait strategy**: Exponential backoff with jitter (`wait=wait_exponential(multiplier=1, min=1, max=10)`).
     - **Logging**: Log each retry attempt at `WARNING` level with `[Notion Mirror] [Retry]` tag indicating attempt number and delay before sleep (`before_sleep=before_sleep_log(logger, logging.WARNING)`).
     - **Failure behavior**: If all retries are exhausted, log final failure at `ERROR` level with `[Notion Mirror]` tag and return `None` (or raise `NotionServiceError` for catch-up workers), without crashing the application.

3. **Transaction Mirroring Status Tracking in Database Model (`Transaction`)**:
   - Update `Transaction` model in `src/db/models.py` to add optional tracking fields:
     - `notion_page_id: Optional[str] = Field(default=None, nullable=True, index=True)` (Stores the Notion page ID once successfully mirrored).
     - `notion_synced_at: Optional[datetime] = Field(default=None, nullable=True)` (Stores UTC timestamp when mirroring succeeded).
   - In `_persist_transaction` (`src/services/ai_orchestrator.py`):
     - Return the created `transaction.id` (UUID).
   - In `NotionService.mirror_transaction`:
     - Accept optional `transaction_id: Optional[UUID] = None`.
     - Upon successful page creation, if `transaction_id` is provided, update `transaction.notion_page_id = page["id"]` and `transaction.notion_synced_at = datetime.now(timezone.utc)` and commit the session.

4. **Catch-Up Synchronization for Prolonged Failures (`sync_pending_transactions`)**:
   - Implement `sync_pending_transactions` in `src/services/notion_service.py`:
     ```python
     async def sync_pending_transactions(
         self,
         family_id: UUID,
         limit: int = 50
     ) -> Dict[str, Any]:
     ```
     - Verifies family has Notion connected (`notion_api_key` and `notion_database_id`). If not connected, returns `{"status": "not_connected", "synced": 0, "failed": 0, "total_pending": 0}`.
     - Queries local `Transaction` records where `family_id == family_id` and `notion_page_id == None`, ordered chronologically (`timestamp.asc()`), up to `limit`.
     - Iterates each pending transaction:
       - Decrypts `amount` and `concept` via `EncryptionService`.
       - Extracts `currency` from decrypted amount string.
       - Retrieves user display name (`user.full_name` or `user.username`).
       - Calls `mirror_transaction(..., transaction_id=tx.id)`.
       - Tracks success and failure counts.
     - Returns summary dictionary: `{"status": "completed", "total_pending": total_count, "synced": success_count, "failed": failed_count}`.

5. **Enhanced `/notion sync` Command in `AIOrchestrator`**:
   - When user sends `/notion sync` or `notion sync`:
     - Check if family is connected to Notion. If not, return guidance to run `/notion`.
     - If connected, call `await notion_service.sync_pending_transactions(family_id)`.
     - If `synced > 0`:
       - Response: `✅ <b>Notion Sync Complete!</b>\nSuccessfully synchronized <b>{synced}</b> pending transaction(s) to <b>{database_name}</b>.` (plus any failure notice if `failed > 0`).
     - If `synced == 0` and `failed == 0`:
       - Response: `✅ <b>Notion Sync is Up to Date!</b>\nAll transactions are already synchronized with your Notion database <b>{database_name}</b>.`
     - If `synced == 0` and `failed > 0`:
       - Response: `⚠️ <b>Notion Sync Failed:</b> Could not reach Notion API for {failed} transaction(s). The system will retry on your next sync or message.`

6. **Non-Blocking Architecture & Fault Isolation**:
   - Background real-time mirroring and retries MUST NOT block the user's Telegram confirmation message (maintaining the 3-second SLA, NFR1).
   - In `_safe_mirror_to_notion`, retries run in the background task. Even if all retries fail, local database persistence remains intact.
   - Stderr / logger output includes detailed stack traces and context (`family_id`, `transaction_id`, exception details) for operational diagnostics.

7. **Comprehensive Test Suite**:
   - `tests/services/test_notion_service.py`:
     - Test transient error retry: mock `notion.pages.create` failing twice with `httpx.ConnectTimeout` or HTTP 429, then succeeding on the 3rd attempt; assert retry succeeds and page is created.
     - Test transient error exhaustion: mock `notion.pages.create` failing 3 times with HTTP 503; assert `mirror_transaction` logs errors, exhausts retries, and returns `None` without crashing.
     - Test permanent error fail-fast: mock `APIResponseError` with 401 Unauthorized or 404 Not Found; assert it fails immediately without retrying.
     - Test `mirror_transaction` with `transaction_id`: assert `Transaction.notion_page_id` and `Transaction.notion_synced_at` are persisted upon success.
     - Test `sync_pending_transactions`: create 3 transactions (2 un-synced, 1 already synced with `notion_page_id`); assert `sync_pending_transactions` only syncs the 2 un-synced transactions, updates their `notion_page_id`, and returns `synced=2`.
   - `tests/services/test_ai_orchestrator.py`:
     - Test expense logging passes `transaction_id` to background mirroring task.
     - Test `/notion sync` command when pending unsynced transactions exist: verify `sync_pending_transactions` is called and formatted reply is returned.
     - Test `/notion sync` command when all transactions are already synced: verify up-to-date reply is returned.
   - `tests/db/test_models.py`:
     - Test `Transaction` model with `notion_page_id` and `notion_synced_at` fields.
   - Full test suite passes 100% (`.\venv\Scripts\python -m pytest`).

## Tasks / Subtasks

- [x] **Dependencies & Database Schema Enhancement** (AC: 1, 3)
  - [x] Add `tenacity>=9.0.0` to `requirements.txt`.
  - [x] Add `notion_page_id: Optional[str] = Field(default=None, nullable=True, index=True)` and `notion_synced_at: Optional[datetime] = Field(default=None, nullable=True)` to `Transaction` in `src/db/models.py`.
  - [x] Update `tests/db/test_models.py` with tests for `notion_page_id` and `notion_synced_at`.
- [x] **Tenacity Retry & Error Classification in NotionService** (AC: 1, 2, 3)
  - [x] Define retry predicate function `_is_transient_notion_error(exception: Exception) -> bool` identifying network errors, 429, and 5xx errors.
  - [x] Implement `_create_page_with_retry` (or decorate page creation) in `src/services/notion_service.py` using `tenacity.AsyncRetrying(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10), retry=retry_if_predicate(_is_transient_notion_error), before_sleep=before_sleep_log(logger, logging.WARNING), reraise=True)`.
  - [x] Update `mirror_transaction()` to accept optional `transaction_id: Optional[UUID] = None` and persist `transaction.notion_page_id` and `transaction.notion_synced_at` in the DB session when mirrored.
- [x] **Catch-Up Synchronization Implementation** (AC: 4, 5)
  - [x] Implement `sync_pending_transactions(self, family_id: UUID, limit: int = 50)` in `src/services/notion_service.py`.
  - [x] Update `AIOrchestrator._persist_transaction` in `src/services/ai_orchestrator.py` to return the new transaction's UUID.
  - [x] Update `AIOrchestrator._safe_mirror_to_notion` in `src/services/ai_orchestrator.py` to pass `transaction_id` to `mirror_transaction`.
  - [x] Upgrade `/notion sync` command handler in `AIOrchestrator.orchestrate` to trigger `sync_pending_transactions` and report synced vs. up-to-date counts.
- [x] **Comprehensive Test Suite & Verification** (AC: 7)
  - [x] Add unit tests in `tests/services/test_notion_service.py` for retry on transient errors (429, 503, timeout), fail-fast on permanent errors (401, 404), `transaction_id` database update, and `sync_pending_transactions`.
  - [x] Add integration tests in `tests/services/test_ai_orchestrator.py` for `/notion sync` with pending vs. up-to-date transactions.
  - [x] Verify 100% test pass rate locally across all modules (DB models, Orchestrator, NotionService).

### Review Findings

- [x] [Review][Patch] Defensive ValueError handling when parsing decrypted amount string during catch-up sync [`src/services/notion_service.py:364`]
- [x] [Review][Patch] Avoid duplicate page creation on concurrent /notion sync and real-time background task [`src/services/notion_service.py:345`]

## Dev Notes

### Architecture & Retry Flow

```
Expense Logged ──► Local DB Persistence (Encrypted Amount & Concept)
                          │ (returns transaction.id)
                          ▼
             Telegram Reply Sent (3s SLA preserved)
                          │
                          ▼ (Background Task: _safe_mirror_to_notion)
             NotionService.mirror_transaction(transaction_id)
                          │
                          ▼
            [Tenacity AsyncRetrying Loop]
             Attempt 1: notion.pages.create()
                ├── Success ──► Update Transaction.notion_page_id & notion_synced_at ──► Done
                └── Transient Error (e.g. 429 / Timeout / 503)
                          │ (Wait 1s exponential backoff + Log Warning)
                          ▼
             Attempt 2: notion.pages.create()
                ├── Success ──► Update Transaction.notion_page_id & notion_synced_at ──► Done
                └── Transient Error (e.g. 503)
                          │ (Wait 2s exponential backoff + Log Warning)
                          ▼
             Attempt 3: notion.pages.create()
                ├── Success ──► Update Transaction.notion_page_id & notion_synced_at ──► Done
                └── Exhausted ──► Log Error [Notion Mirror] Failed to mirror ──► Transaction remains with notion_page_id=None
                                                                                         │
                                                                                         ▼
                                                                Recoverable via: /notion sync (Catch-up sync)
```

### Transient vs Permanent Error Classifier

```python
import httpx
from notion_client import APIResponseError

def is_transient_notion_error(exc: BaseException) -> bool:
    """
    Determines if an exception is transient and should be retried.
    Permanent errors (401 unauthorized, 404 not found, 400 validation error) are NOT retried.
    """
    if isinstance(exc, (httpx.RequestError, httpx.TimeoutException)):
        return True
    
    if isinstance(exc, APIResponseError):
        # Retry on rate limiting
        if exc.code == "rate_limited" or exc.status == 429:
            return True
        # Retry on Notion server side errors
        if exc.code in ("service_unavailable", "internal_server_error") or (exc.status and exc.status >= 500):
            return True
        # Do not retry on client/auth errors (400, 401, 403, 404)
        return False
        
    return False
```

### Tenacity Async Page Creation Helper

```python
from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential, retry_if_exception, before_sleep_log

async def _create_page_with_retry(self, notion: AsyncClient, database_id: str, properties: Dict[str, Any]) -> Dict[str, Any]:
    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception(is_transient_notion_error),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True
    ):
        with attempt:
            return await notion.pages.create(
                parent={"database_id": database_id},
                properties=properties
            )
```

### Catch-Up Sync Implementation (`sync_pending_transactions`)

```python
async def sync_pending_transactions(self, family_id: UUID, limit: int = 50) -> Dict[str, Any]:
    family = self.session.get(Family, family_id)
    if not family or not family.notion_api_key or not family.notion_database_id:
        return {"status": "not_connected", "synced": 0, "failed": 0, "total_pending": 0}

    statement = (
        select(Transaction)
        .where(Transaction.family_id == family_id)
        .where(Transaction.notion_page_id == None)  # noqa: E711
        .order_by(Transaction.timestamp.asc())
        .limit(limit)
    )
    pending_txs = self.session.exec(statement).all()
    if not pending_txs:
        return {"status": "completed", "synced": 0, "failed": 0, "total_pending": 0}

    synced_count = 0
    failed_count = 0

    for tx in pending_txs:
        try:
            # Decrypt ciphertext
            decrypted_amount_str = self.encryption.decrypt(tx.amount)
            decrypted_concept = self.encryption.decrypt(tx.concept)
            
            # Parse amount & currency
            parts = decrypted_amount_str.split()
            amount_val = float(parts[0]) if parts else 0.0
            currency_val = parts[1] if len(parts) > 1 else "USD"

            # Get user display name
            user = self.session.get(User, tx.user_id) if tx.user_id else None
            user_name = (user.full_name or user.username) if user else None

            res = await self.mirror_transaction(
                family_id=family_id,
                amount=amount_val,
                currency=currency_val,
                concept=decrypted_concept,
                category=tx.category,
                timestamp=tx.timestamp,
                user_name=user_name,
                transaction_id=tx.id
            )
            if res and res.get("status") == "mirrored":
                synced_count += 1
            else:
                failed_count += 1
        except Exception as e:
            logger.error(f"[Notion Mirror] Failed to catch-up sync transaction {tx.id}: {e}")
            failed_count += 1

    return {
        "status": "completed",
        "synced": synced_count,
        "failed": failed_count,
        "total_pending": len(pending_txs)
    }
```

### Source Files to Touch

#### [MODIFY] [requirements.txt](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/requirements.txt)
- Add `tenacity>=9.0.0` to dependencies.

#### [MODIFY] [src/db/models.py](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/src/db/models.py)
- Add `notion_page_id: Optional[str] = Field(default=None, nullable=True, index=True)` and `notion_synced_at: Optional[datetime] = Field(default=None, nullable=True)` to `Transaction`.

#### [MODIFY] [src/services/notion_service.py](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/src/services/notion_service.py)
- Import `tenacity` utilities (`AsyncRetrying`, `stop_after_attempt`, `wait_exponential`, `retry_if_exception`, `before_sleep_log`).
- Implement `is_transient_notion_error` helper.
- Update `mirror_transaction` to use tenacity retry on transient errors and accept optional `transaction_id: Optional[UUID] = None`. When provided and successful, update `transaction.notion_page_id` and `transaction.notion_synced_at` in the database.
- Implement `sync_pending_transactions(self, family_id: UUID, limit: int = 50)` for catch-up synchronization.

#### [MODIFY] [src/services/ai_orchestrator.py](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/src/services/ai_orchestrator.py)
- Update `_persist_transaction` to return the created `transaction.id`.
- Pass `transaction_id` into `_safe_mirror_to_notion` and forward to `notion_service.mirror_transaction`.
- Update `/notion sync` command handler to call `sync_pending_transactions` and report results.

#### [MODIFY] [tests/services/test_notion_service.py](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/tests/services/test_notion_service.py)
- Add tests for transient error retries, failure exhaustion, permanent error fail-fast, `transaction_id` database update, and `sync_pending_transactions`.

#### [MODIFY] [tests/services/test_ai_orchestrator.py](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/tests/services/test_ai_orchestrator.py)
- Add tests for `/notion sync` with pending vs. up-to-date transactions.

#### [MODIFY] [tests/db/test_models.py](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/tests/db/test_models.py)
- Add test verifying `Transaction` instantiation and querying with `notion_page_id` and `notion_synced_at`.

### Anti-Patterns to Prevent

- **Retrying Permanent Errors**: Never retry 401 Unauthorized or 404 Database Not Found; these will fail 100% of the time and waste execution time/tokens.
- **Blocking Request Loop with Retries**: Retries with exponential backoff (e.g. 1s + 2s + 4s) must ONLY occur in the background task (`_safe_mirror_to_notion` or `sync_pending_transactions`). The user's Telegram acknowledgment MUST never be delayed by Notion retries.
- **Data Inconsistency on Sync**: When `sync_pending_transactions` runs, always decrypt `amount` and `concept` safely in memory and parse currency correctly without corrupting local records.
- **Session Collisions**: Ensure background tasks create their own dedicated `Session(engine)` instance when updating transaction records after mirroring.

### Project Structure Notes

- Alignment with unified project structure: all services stay in `src/services/`, database models in `src/db/models.py`.
- No new architectural directories needed.

### References

- [Epics: Story 6.3 (Retry Mechanism for Mirroring)](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/epics.md#L376-L388)
- [PRD: Consistency & Reliability (NFR8, FR12, FR13)](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/prd.md#L111-L113)
- [Architecture: Notion Sync Worker & Service Layer Pattern](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/architecture.md#L28-L38)
- [Story 6.2: Real-Time Log Mirroring](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/implementation-artifacts/6-2-real-time-log-mirroring.md)
- [Story 6.1: Notion Workspace Connection](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/implementation-artifacts/6-1-notion-workspace-connection.md)

## Dev Agent Record

### Agent Model Used

Gemini 3.7 Flash (High)

### Debug Log References

### Completion Notes List

### File List
