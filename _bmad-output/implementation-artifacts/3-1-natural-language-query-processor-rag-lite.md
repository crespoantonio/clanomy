# Story 3.1: Natural Language Query Processor (RAG-lite)

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a User,
I want to ask questions about my expenses in plain English (e.g., "What did I spend yesterday?", "How much did I spend on groceries this week?", "Show my expenses from last month"),
so that I can quickly review and retrieve my financial records without navigating complex menus or spreadsheets.

## Acceptance Criteria

1. **Natural Language Query Intent Extraction**:
   - Implement `QueryService` in `src/services/query_service.py` to translate unstructured natural language queries into a structured `ParsedQueryIntent` using Ollama.
   - Extract the following fields adhering to a Pydantic schema passed to Ollama's `format` parameter (`ParsedQueryIntent.model_json_schema()`):
     - `intent`: str / literal (`"query_spending"`, `"general_query"`, `"unknown"`)
     - `timeframe`: str (e.g. `"today"`, `"yesterday"`, `"this_week"`, `"last_week"`, `"this_month"`, `"last_month"`, `"all_time"`, or `"custom"`)
     - `start_date`: Optional[str] (ISO date `YYYY-MM-DD` if explicit in the query or `"custom"`)
     - `end_date`: Optional[str] (ISO date `YYYY-MM-DD` if explicit in the query or `"custom"`)
     - `category`: Optional[str] (standardized to one of: `"Food/Drink"`, `"Transport"`, `"Rent/Bills"`, `"Shopping"`, `"Leisure"`, `"Other"`, or `None` if no category filter is requested)
     - `concept_keyword`: Optional[str] (e.g. merchant or item name like `"Starbucks"`, `"Uber"`, or `None` if not specified)
2. **Temporal & Relative Date Range Resolution**:
   - Provide a deterministic date-range calculation method `_resolve_date_range(timeframe, start_date_str, end_date_str, reference_time=None)` that maps relative temporal keywords into explicit UTC `datetime` boundaries `(start_time, end_time)`:
     - `"today"`: Start of current day (`00:00:00.000000 UTC`) to current time or end of day (`23:59:59.999999 UTC`).
     - `"yesterday"`: Start of previous day (`00:00:00.000000 UTC`) to end of previous day (`23:59:59.999999 UTC`).
     - `"this_week"`: Monday `00:00:00.000000 UTC` of the current calendar week to current time / end of week.
     - `"last_week"`: Monday `00:00:00.000000 UTC` through Sunday `23:59:59.999999 UTC` of the previous calendar week.
     - `"this_month"`: Day 1 `00:00:00.000000 UTC` of the current month to current time / end of month.
     - `"last_month"`: First day `00:00:00.000000 UTC` through last day `23:59:59.999999 UTC` of the preceding calendar month.
     - `"custom"`: Parses explicit `start_date` and `end_date` strings into UTC boundaries.
     - `"all_time"` / `None`: Returns `(None, None)` (unbounded).
   - Inject the current UTC date into the LLM system prompt so relative dates ("yesterday", "last Friday") are interpreted with zero ambiguity.
3. **Multi-Tenant Database Querying**:
   - Query the `Transaction` table with mandatory scoping to the requesting user's `family_id`.
   - Apply SQL-level filters: `Transaction.family_id == family_id`, and if bounded: `Transaction.timestamp >= start_time` and `Transaction.timestamp <= end_time`.
   - If `category` is specified, filter `Transaction.category == category` at the database level (leveraging the indexed `category` column).
   - Order matching database records by `Transaction.timestamp.desc()`.
4. **In-Memory AES-256 Decryption & Record Hydration**:
   - Because `amount` (formatted as `f"{amount} {currency}"`) and `concept` are stored as encrypted ciphertext tokens, decrypt each record in memory using `EncryptionService.decrypt()`.
   - Parse the decrypted amount string into numeric `float` amount and 3-letter ISO `currency` code (e.g. `"15.0 USD"` -> `15.0`, `"USD"`).
   - If `concept_keyword` is present in the parsed intent, perform case-insensitive substring matching against the decrypted `concept` string in memory.
   - Return strongly-typed `DecryptedTransaction` objects.
5. **Non-Blocking & Async Execution**:
   - Use `ollama.AsyncClient(host=settings.OLLAMA_BASE_URL)` for non-blocking LLM translation with a 60-second timeout.
   - Run synchronous database querying and cryptographic decryption inside `asyncio.to_thread` to ensure FastAPI's event loop remains unblocked.
6. **3s Audit Logging & Performance**:
   - Measure and log execution duration under the standard audit prefix: `[3s Audit] Query processing took X.XX seconds (model: {model}, family_id: {family_id})`.
7. **Error Handling & Robustness**:
   - Empty/whitespace queries raise `ValueError`.
   - LLM connection/timeout errors or unparseable responses raise custom `QueryProcessingError`.
   - Database queries returning zero matching records return a valid `QueryResult` with an empty `transactions` list (no 500 error or crash).
8. **Unit & Integration Testing**:
   - Provide comprehensive test coverage in `tests/services/test_query_service.py`:
     - Test intent and parameter extraction with mocked Ollama chat responses.
     - Test date range resolution for all temporal keywords ("today", "yesterday", "this_week", "last_week", "this_month", "last_month", "custom").
     - Test category filtering and merchant concept filtering.
     - Test in-memory decryption and amount/currency extraction.
     - Test strict multi-tenant isolation (`family_id` scoping).
     - Test error handling for timeouts, invalid parameters, and empty result sets.

## Tasks / Subtasks

- [x] **Query Service Data Models & Exceptions** (AC: 1, 4, 7)
  - [x] Create `src/services/query_service.py`.
  - [x] Define custom exception `QueryProcessingError(Exception)`.
  - [x] Define Pydantic schema `ParsedQueryIntent`:
    - `intent`: `str` (`"query_spending"`, `"general_query"`, `"unknown"`)
    - `timeframe`: `str` (`"today"`, `"yesterday"`, `"this_week"`, `"last_week"`, `"this_month"`, `"last_month"`, `"all_time"`, `"custom"`)
    - `start_date`: `Optional[str]` (ISO format `YYYY-MM-DD`)
    - `end_date`: `Optional[str]` (ISO format `YYYY-MM-DD`)
    - `category`: `Optional[str]` with validator normalizing to `{"Food/Drink", "Transport", "Rent/Bills", "Shopping", "Leisure", "Other"}` or `None`
    - `concept_keyword`: `Optional[str]`
  - [x] Define Pydantic schema `DecryptedTransaction`:
    - `id`: `UUID`
    - `family_id`: `UUID`
    - `user_id`: `UUID`
    - `amount`: `float`
    - `currency`: `str`
    - `concept`: `str`
    - `category`: `str`
    - `timestamp`: `datetime`
  - [x] Define Pydantic schema `QueryResult`:
    - `intent`: `ParsedQueryIntent`
    - `resolved_start_time`: `Optional[datetime]`
    - `resolved_end_time`: `Optional[datetime]`
    - `transactions`: `List[DecryptedTransaction]`
    - `total_count`: `int`
- [x] **QueryService Implementation** (AC: 1, 2, 3, 4, 5, 6, 7)
  - [x] Implement `QueryService` as a thread-safe singleton pattern using `threading.Lock`.
  - [x] Implement `__init__` initializing `ollama.AsyncClient(host=settings.OLLAMA_BASE_URL)`, `self.model = settings.OLLAMA_MODEL`, and `self.encryption_service = EncryptionService()`.
  - [x] Implement `_resolve_date_range(timeframe: str, start_date_str: Optional[str], end_date_str: Optional[str], reference_time: Optional[datetime] = None) -> tuple[Optional[datetime], Optional[datetime]]` handling all relative timeframes anchored to `reference_time` (default `datetime.now(timezone.utc)`).
  - [x] Implement `_decrypt_transaction(tx: Transaction) -> Optional[DecryptedTransaction]` to safely decrypt `tx.amount` and `tx.concept` and parse numerical amount and currency.
  - [x] Implement synchronous worker `_fetch_and_decrypt_transactions(family_id: UUID, start_time: Optional[datetime], end_time: Optional[datetime], category: Optional[str], concept_keyword: Optional[str]) -> List[DecryptedTransaction]` running in a `with Session(engine) as session:` context.
  - [x] Implement async `process_query(text: str, family_id: UUID, reference_time: Optional[datetime] = None) -> QueryResult`:
    - Validate non-empty query string.
    - Query Ollama with formatted system prompt containing current date reference and structured JSON schema format.
    - Resolve date range.
    - Execute `_fetch_and_decrypt_transactions` in `asyncio.to_thread`.
    - Record and log `[3s Audit]` elapsed timing.
    - Return structured `QueryResult`.
- [x] **Unit & Integration Test Suite** (AC: 8)
  - [x] Create `tests/services/test_query_service.py`.
  - [x] Test Ollama structured extraction mocking `ollama.AsyncClient.chat`.
  - [x] Test temporal date range calculation edge cases (leap years, month transitions, week start on Monday).
  - [x] Test database query execution and strict `family_id` isolation using mocked SQLModel sessions.
  - [x] Test in-memory decryption and fallback on malformed encrypted ciphertext.
  - [x] Test concept keyword in-memory filtering.
  - [x] Test error paths (empty query, Ollama timeout, connection failure).
  - [x] Verify test suite passes with `venv/Scripts/python -m pytest`.

### Review Findings

- [x] [Review][Patch] Ineffective timeout parameter in Ollama chat call [src/services/query_service.py:206]
- [x] [Review][Patch] Rigid category normalization raises ValueError on non-standard LLM output [src/services/query_service.py:28-41]
- [x] [Review][Patch] Log output uses stdout print instead of standard logger [src/services/query_service.py:224]
- [x] [Review][Patch] Uncaught TypeError/ValueError edge cases in custom date range parsing [src/services/query_service.py:126-133]

## Dev Notes

### Architecture & Service Design

- **Service Pattern**: Follow the existing pattern established in `src/services/extraction_service.py` and `src/services/ai_orchestrator.py`.
- **Singleton Guard**: Use thread-safe double-checked locking for `QueryService` instantiation:
  ```python
  class QueryService:
      _instance: Optional['QueryService'] = None
      _lock = threading.Lock()

      def __new__(cls) -> 'QueryService':
          if cls._instance is None:
              with cls._lock:
                  if cls._instance is None:
                      cls._instance = super(QueryService, cls).__new__(cls)
                      cls._instance._initialized = False
          return cls._instance
  ```
- **Ollama Async Client**: Use `ollama.AsyncClient(host=settings.OLLAMA_BASE_URL)` to ensure non-blocking HTTP requests. Always pass `format=ParsedQueryIntent.model_json_schema()` to constrain Ollama's output strictly to the JSON schema.
- **Async DB Offloading**: Always run synchronous SQLModel database queries and cryptographic decryption routines inside `asyncio.to_thread()` to prevent stalling the main asyncio event loop.
- **Database Session Isolation**: Always instantiate a new `with Session(engine) as session:` within the worker thread to prevent cross-request session leakage and threading issues.

### Decryption & Data Flow Details

- **Field-Level Encryption at Rest**: Recall that in `Transaction`, `amount` is stored as Fernet ciphertext of `f"{amount} {currency}"` (e.g. `"15.0 USD"`), and `concept` is stored as Fernet ciphertext of the description.
- **Why RAG-Lite & Decryption on Read**: Because `amount` is encrypted with random IVs/nonces, PostgreSQL cannot execute `SUM(amount)` or SQL `WHERE amount > 50`. The query engine fetches the matching encrypted records for the tenant within the temporal/category bounds, decrypts them in memory, and builds the typed transaction list for downstream aggregation (Story 3.2/3.3) and conversational summarization (Story 3.4).
- **Amount String Parsing Helper**:
  ```python
  def _parse_amount_string(decrypted_str: str) -> tuple[float, str]:
      # e.g., "15.0 USD" -> (15.0, "USD")
      parts = decrypted_str.strip().split()
      if not parts:
          return 0.0, "USD"
      try:
          amount = float(parts[0])
      except ValueError:
          amount = 0.0
      currency = parts[1].upper() if len(parts) > 1 else "USD"
      return amount, currency
  ```

### System Prompt & Intent Extraction

- **System Prompt Guidelines**:
  - State the role as a financial query parser.
  - Provide the current date in UTC (e.g. `Current Date: {current_date_str}`).
  - Specify the exact allowed category strings: `"Food/Drink"`, `"Transport"`, `"Rent/Bills"`, `"Shopping"`, `"Leisure"`, `"Other"`.
  - Specify the standard timeframes: `"today"`, `"yesterday"`, `"this_week"`, `"last_week"`, `"this_month"`, `"last_month"`, `"custom"`, `"all_time"`.
  - Provide instructions for extracting `concept_keyword` if the user is asking about a specific place or item (e.g. "How much did I spend at Starbucks?" -> `concept_keyword: "Starbucks"`).

### 3s Audit Prefix Standard

- Match the established project logging pattern:
  `[3s Audit] Query processing took X.XX seconds (model: {self.model}, family_id: {family_id})`

### Project Structure Notes

- **Service File**: `src/services/query_service.py` [NEW]
- **Tests File**: `tests/services/test_query_service.py` [NEW]
- **Reused Components**:
  - `src/core/config.py` (`settings.OLLAMA_BASE_URL`, `settings.OLLAMA_MODEL`)
  - `src/core/encryption.py` (`EncryptionService`)
  - `src/db/models.py` (`Transaction`, `User`, `Family`)
  - `src/db/session.py` (`engine`)

### References

- [Architecture: Inference Engine](file:///C:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/architecture.md#L100)
- [Architecture: Complete Project Directory Structure](file:///C:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/architecture.md#L196)
- [Epics: Story 3.1](file:///C:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/epics.md#L225)
- [PRD: Conversational Queries ("ASK")](file:///C:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/prd.md#L102)
- [Epic 2 Retrospective: Action Plan for Epic 3](file:///C:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/implementation-artifacts/epic-2-retro-2026-08-14.md#L44)

## Dev Agent Record

### Agent Model Used

Gemini 3.7 Flash (High)

### Debug Log References

### Completion Notes List

- ✅ Implemented the `QueryService` using Ollama for intent extraction with Pydantic JSON schema formatting.
- ✅ Offloaded decryption and database queries to `asyncio.to_thread` for non-blocking execution.
- ✅ Replaced async tests with synchronous wrappers using `asyncio.run` to handle absence of `pytest-asyncio` plugin, ensuring a passing test suite.
- ✅ Successfully updated sprint status and story state to `review`.

### File List

- `src/services/query_service.py`
- `tests/services/test_query_service.py`
