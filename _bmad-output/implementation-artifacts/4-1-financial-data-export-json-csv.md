# Story 4.1: Financial Data Export (JSON/CSV)

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a User,
I want to export my complete transaction history via the bot in CSV or JSON format (e.g., "export my data", "download my transactions to CSV", "export json"),
so that I can maintain personal financial backups, import my records into spreadsheets or budgeting tools, and exercise my GDPR data portability rights.

## Acceptance Criteria

1. **Intent Recognition & Extraction for Data Export**:
   - Update `ParsedQueryIntent` or `QueryService` to recognize export intents (`"export_data"`, `"export_csv"`, `"export_json"`).
   - Support common natural language phrases: "export my data", "export to csv", "export json", "download my transactions", "send me my expense history", "backup my data".
   - Extract the desired format (`"csv"` or `"json"`, defaulting to `"csv"` if not specified).
   - Support optional temporal or category filters if specified in the export query (e.g., "export this month to csv").

2. **Decrypted Export Generation Engine (`ExportService`)**:
   - Implement `ExportService` in `src/services/export_service.py` (singleton pattern).
   - Fetch all transactions scoped strictly to the requesting user's `family_id` from PostgreSQL / SQLModel.
   - Decrypt sensitive fields (`amount`, `concept`) in memory using `EncryptionService`.
   - **CSV Export Format Specification**:
     - UTF-8 encoded with standard header: `Timestamp (UTC),Amount,Currency,Category,Concept`.
     - Properly escape special characters, quotes, commas, and newlines in concept descriptions using Python's `csv.writer`.
     - Format timestamp as ISO-8601 string (`YYYY-MM-DD HH:MM:SS UTC`).
   - **JSON Export Format Specification**:
     - Structure with metadata and array of records:
       ```json
       {
         "family_id": "<UUID>",
         "exported_at": "YYYY-MM-DDTHH:MM:SSZ",
         "total_count": 42,
         "transactions": [
           {
             "id": "<UUID>",
             "timestamp": "YYYY-MM-DDTHH:MM:SSZ",
             "amount": 15.50,
             "currency": "USD",
             "category": "Food/Drink",
             "concept": "Coffee with friends"
           }
         ]
       }
       ```

3. **Zero-Leak Temporary File & Auto-Cleanup Pipeline**:
   - Write export payload to an isolated temporary file using `tempfile.mkstemp(prefix="famfin_export_", suffix=f".{format}")`.
   - Enforce guaranteed file removal with a strict `try-finally` block or context manager so that `os.unlink(temp_file_path)` is executed unconditionally after transmission, leaving zero plaintext files on disk.

4. **Telegram Document Dispatch Integration**:
   - Extend `TelegramService` in `src/services/telegram_service.py` with `send_document(chat_id: int, file_path: str, caption: Optional[str] = None) -> None`.
   - Post `multipart/form-data` to `https://api.telegram.org/bot<TOKEN>/sendDocument` with `chat_id`, binary `document` stream, and optional HTML-formatted `caption`.
   - Send an encouraging, friendly caption (e.g., `📊 Here is your exported transaction history (Total: X transactions).`).

5. **Multi-Tenant Isolation & Edge Case Handling**:
   - Enforce strict database scoping by `family_id` so users never receive another family's data.
   - If user has 0 transactions, generate a valid file with headers only (or return a clear empty CSV/JSON document) along with a friendly caption indicating zero records.
   - Multi-currency entries must be exported faithfully preserving individual currency codes.

6. **3s Audit & Performance Logging**:
   - Measure and log export generation time under `[3s Audit] Data export took {duration:.2f} seconds (format: {format}, count: {count}, family_id: {family_id})`.
   - In-memory CSV/JSON compilation must execute in `< 50ms` for up to 5,000 transactions.

7. **Unit & Integration Test Suite**:
   - Create `tests/services/test_export_service.py`:
     - Test CSV formatting with commas, quotes, and non-ASCII characters in concept strings.
     - Test JSON formatting and metadata structure.
     - Test strict `family_id` isolation.
     - Test temporary file creation and automatic cleanup verification (asserting file does not exist after export).
     - Test zero-records export.
   - Update `tests/services/test_telegram_service.py`:
     - Test `send_document` with mocked `httpx.AsyncClient` response.
   - Ensure 100% test pass rate with `.\venv\Scripts\python -m pytest`.

## Tasks / Subtasks

- [x] **TelegramService Extension** (AC: 4)
  - [x] Add `send_document(chat_id: int, file_path: str, caption: Optional[str] = None)` to `src/services/telegram_service.py`.
  - [x] Support multipart form-data upload with `httpx.AsyncClient`.
  - [x] Add unit tests in `tests/services/test_telegram_service.py`.
- [x] **ExportService Core Engine** (AC: 2, 3, 5, 6)
  - [x] Create `src/services/export_service.py` with thread-safe singleton pattern.
  - [x] Implement `generate_csv(transactions: List[DecryptedTransaction], file_path: str) -> None`.
  - [x] Implement `generate_json(transactions: List[DecryptedTransaction], family_id: UUID, file_path: str) -> None`.
  - [x] Implement `export_data(family_id: UUID, format: str = "csv") -> tuple[str, int]`:
    - Fetch and decrypt transactions for `family_id` using `EncryptionService`.
    - Create temp file with `tempfile.mkstemp`.
    - Write formatted data.
    - Return `(temp_file_path, count)`.
  - [x] Implement `export_and_send(family_id: UUID, chat_id: int, format: str = "csv") -> None` with guaranteed `finally: os.unlink` cleanup.
  - [x] Add `[3s Audit]` performance logging.
- [x] **Intent & Query Integration** (AC: 1)
  - [x] Update `ParsedQueryIntent` in `src/services/query_service.py` to support `intent: "export_data"`, `export_format: Optional[str] = "csv"`.
  - [x] Update Ollama system prompt in `src/services/query_service.py` to extract export intents.
  - [x] Integrate export routing in `/api/v1/telegram/webhook` / `ai_orchestrator` to invoke `ExportService`.
- [x] **Comprehensive Unit & Integration Test Suite** (AC: 7)
  - [x] Create `tests/services/test_export_service.py`.
  - [x] Test CSV export generation, escaping, and formatting.
  - [x] Test JSON export structure, timestamps, and UUID serialization.
  - [x] Test `export_and_send` with mocked `TelegramService.send_document` to verify API calls and arg validation.
  - [x] Test temp file cleanup occurs even if `TelegramService` raises an exception (`finally` block coverage).
  - [x] Verify `ExportService` only processes records belonging to the requested `family_id` (data isolation).

### Review Findings

- [x] [Review][Decision] Double LLM Call Latency Penalty — For every standard expense logging message, the system calls QueryService.parse_intent (invoking Ollama) followed by ExtractionService.extract (invoking Ollama a second time). This double LLM call doubles inference latency, violating NFR1 (confirmation in < 3s). We need a strategy (e.g., regex/keyword heuristic or combined parsing prompt) to avoid this double call.
- [x] [Review][Patch] Synchronous Database Session Blocking [src/services/ai_orchestrator.py:90] — DB session query retrieve user is executed on the main event loop thread. Wrap it in asyncio.to_thread.
- [x] [Review][Patch] Synchronous Database Session Blocking [src/services/ai_orchestrator.py:102] — DB session query retrieve user for spending summary is executed on the main event loop thread. Wrap it in asyncio.to_thread.
- [x] [Review][Patch] Exception Swallowing in send_document [src/services/telegram_service.py:24] — send_document catches Exception and logs it, but does not re-raise. Re-raise it so calling service knows sending failed.

## Dev Notes

### Architecture & Service Design

- **Service Pattern**: Follow the existing singleton pattern in `src/services/query_service.py` and `src/services/extraction_service.py`.
- **Decryption Flow**: Reuse `EncryptionService.decrypt()` to decrypt `Transaction.amount` (`f"{amount} {currency}"`) and `Transaction.concept`.
- **Zero Disk Leak Guarantee**:
  ```python
  fd, temp_path = tempfile.mkstemp(prefix=f"famfin_{family_id}_", suffix=f".{format_type}")
  try:
      with os.fdopen(fd, 'w', newline='', encoding='utf-8') as f:
          # write CSV or JSON
          pass
      await telegram_service.send_document(chat_id=chat_id, file_path=temp_path, caption=caption)
  finally:
      if os.path.exists(temp_path):
          try:
              os.unlink(temp_path)
          except Exception as e:
              logger.error(f"Failed to cleanup temp file {temp_path}: {e}")
  ```
- **Async DB Execution**: Always run synchronous database queries inside `asyncio.to_thread` with a dedicated session `with Session(engine) as session:` to avoid blocking FastAPI's event loop.

### References

- [Architecture: Epic 4 Technical Research & Design](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/architecture.md#L342)
- [Architecture: Data Architecture & Encryption](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/architecture.md#L114)
- [Epics: Story 4.1](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/epics.md#L279)
- [PRD: Data Portability (FR14)](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/prd.md#L34)
- [Epic 3 Retrospective](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/implementation-artifacts/epic-3-retro-2026-08-16.md)

## Dev Agent Record

### Agent Model Used

Gemini 3.7 Flash (High)

### Debug Log References

### Completion Notes List

### File List
