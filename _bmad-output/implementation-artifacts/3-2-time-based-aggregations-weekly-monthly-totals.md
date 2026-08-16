# Story 3.2: Time-Based Aggregations (Weekly/Monthly Totals)

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a User,
I want to see my total spending calculated for specific time periods (such as this week, last week, this month, last month, or custom date ranges),
so that I can understand my spending trends, monitor my cash flow, and stay within my budget.

## Acceptance Criteria

1. **Time-Based Aggregation Data Models**:
   - Define `PeriodComparison` schema in `src/services/query_service.py`:
     - `previous_timeframe`: `str` (e.g., `"last_week"`, `"last_month"`, `"yesterday"`, or `"custom"`)
     - `previous_start_time`: `Optional[datetime]`
     - `previous_end_time`: `Optional[datetime]`
     - `previous_total_amount`: `float`
     - `previous_transaction_count`: `int`
     - `difference_amount`: `float` (current total minus previous total; positive indicates increased spending)
     - `percentage_change`: `Optional[float]` (calculated percentage change; `None` if previous total is zero to avoid division by zero)
   - Define `TimeAggregation` schema in `src/services/query_service.py`:
     - `timeframe`: `str` (e.g., `"today"`, `"yesterday"`, `"this_week"`, `"last_week"`, `"this_month"`, `"last_month"`, `"custom"`, `"all_time"`)
     - `start_time`: `Optional[datetime]`
     - `end_time`: `Optional[datetime]`
     - `total_amount`: `float` (sum of amounts in the primary currency, rounded to 2 decimal places)
     - `primary_currency`: `str` (default `"USD"`, configurable via `settings.DEFAULT_CURRENCY`)
     - `currency_totals`: `Dict[str, float]` (exact amounts summed per currency, e.g. `{"USD": 145.50, "EUR": 30.00}`)
     - `transaction_count`: `int`
     - `average_per_transaction`: `float` (0.0 if `transaction_count` is 0)
     - `daily_breakdown`: `Dict[str, float]` (mapping ISO date strings `YYYY-MM-DD` to total amount in primary currency)
     - `comparison`: `Optional[PeriodComparison]` (populated when comparative time periods are evaluated)
   - Extend `QueryResult` schema in `src/services/query_service.py` to include:
     - `aggregation`: `Optional[TimeAggregation] = None`

2. **Core Aggregation Logic**:
   - Implement `aggregate_transactions(transactions: List[DecryptedTransaction], timeframe: str, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None, primary_currency: str = "USD", calculate_daily: bool = True) -> TimeAggregation`:
     - Accurately compute `currency_totals` dictionary summing amounts per distinct currency code.
     - Extract `total_amount` for the specified `primary_currency` (or sum of all if single currency matches primary).
     - Compute `transaction_count` and `average_per_transaction` (`0.0` when list is empty).
     - When `calculate_daily=True`, group transactions by date `timestamp.strftime("%Y-%m-%d")` and sum primary currency amounts.
     - Handle empty transactions list gracefully without raising exceptions, returning a valid zeroed `TimeAggregation`.

3. **Period-Over-Period Comparison Resolution**:
   - Implement `_resolve_comparison_timeframe(timeframe: str, reference_time: Optional[datetime] = None) -> tuple[Optional[str], Optional[datetime], Optional[datetime]]`:
     - `"this_week"` maps to previous calendar week (Monday 00:00:00 UTC to Sunday 23:59:59 UTC of previous week).
     - `"this_month"` maps to previous calendar month (1st 00:00:00 UTC to last day 23:59:59 UTC of previous month, handling December -> January transitions).
     - `"today"` maps to yesterday (00:00:00 UTC to 23:59:59 UTC of previous day).
     - Unsupported or unanchored timeframes (`"all_time"`, `"custom"`) return `(None, None, None)`.
   - Implement `compute_period_comparison(current_aggregation: TimeAggregation, previous_transactions: List[DecryptedTransaction], previous_timeframe: str, prev_start: Optional[datetime], prev_end: Optional[datetime]) -> PeriodComparison`:
     - Calculate `difference_amount = current_aggregation.total_amount - previous_total`.
     - Calculate `percentage_change = ((current_aggregation.total_amount - previous_total) / previous_total) * 100` if `previous_total > 0`, else `None`.

4. **Integration with `QueryService`**:
   - Update `QueryService.process_query()`:
     - Automatically compute `TimeAggregation` on the retrieved `transactions` and attach to `QueryResult.aggregation`.
     - When `include_comparison=True` (or intent indicates comparative spending e.g. "compared to last month"), fetch previous period transactions in `asyncio.to_thread` using `_resolve_comparison_timeframe` and attach `PeriodComparison`.
   - Add convenience method `QueryService.get_time_aggregation(family_id: UUID, timeframe: str = "this_month", primary_currency: Optional[str] = None, include_comparison: bool = False, reference_time: Optional[datetime] = None) -> TimeAggregation`:
     - Direct API to aggregate spending for standard periods without invoking LLM intent extraction (for scheduled reports, dashboard summaries, and direct bot commands).

5. **Multi-Currency Safety & Primary Currency Configuration**:
   - Add `DEFAULT_CURRENCY: str = "USD"` to `src/core/config.py` in `Settings`.
   - Ensure `currency_totals` preserves distinct currencies without performing arbitrary/unverified exchange rate conversions.

6. **3s Audit Logging & Performance**:
   - In-memory aggregation must execute in `< 10ms` for up to 10,000 decrypted transactions.
   - When period comparison is queried, total execution time must still adhere to the `[3s Audit]` logging standard: `[3s Audit] Aggregation query took X.XX seconds (timeframe: {timeframe}, family_id: {family_id})`.

7. **Unit & Integration Testing**:
   - Update `tests/services/test_query_service.py` with comprehensive test coverage:
     - Test weekly total aggregation for current week and last week.
     - Test monthly total aggregation for current month and last month (including leap years and month boundaries).
     - Test multi-currency transaction lists (`currency_totals` dictionary accuracy).
     - Test daily breakdown generation across multi-day transaction sets.
     - Test period-over-period comparison calculations (spending increase, decrease, zero baseline).
     - Test empty transaction lists return zeroed aggregation without division by zero errors.
     - Test `get_time_aggregation` direct service method.
     - Ensure 100% test pass rate running `.\venv\Scripts\python -m pytest`.

## Tasks / Subtasks

- [x] **Configuration Update** (AC: 5)
  - [x] Add `DEFAULT_CURRENCY: str = "USD"` to `src/core/config.py` in `Settings` class.
- [x] **Data Model Extensions** (AC: 1)
  - [x] Define `PeriodComparison` Pydantic model in `src/services/query_service.py`.
  - [x] Define `TimeAggregation` Pydantic model in `src/services/query_service.py`.
  - [x] Update `QueryResult` model to include `aggregation: Optional[TimeAggregation] = None`.
- [x] **Aggregation Engine Implementation** (AC: 2, 3)
  - [x] Implement `aggregate_transactions()` function in `src/services/query_service.py`.
  - [x] Implement `_resolve_comparison_timeframe()` helper in `src/services/query_service.py`.
  - [x] Implement `compute_period_comparison()` helper in `src/services/query_service.py`.
- [x] **QueryService Integration** (AC: 4, 6)
  - [x] Update `QueryService.process_query()` to compute and attach `TimeAggregation`.
  - [x] Implement `QueryService.get_time_aggregation()` for direct programmatic aggregations.
  - [x] Ensure 3s audit timing includes aggregation calculations.
- [x] **Test Suite Implementation & Verification** (AC: 7)
  - [x] Add unit tests for `aggregate_transactions` with single and multiple currencies in `tests/services/test_query_service.py`.
  - [x] Add unit tests for `_resolve_comparison_timeframe` (week, month, year boundary transitions).
  - [x] Add unit tests for `compute_period_comparison` (percentage change, zero baseline).
  - [x] Add unit tests for `get_time_aggregation` and `process_query` returning aggregated results.
  - [x] Execute `.\venv\Scripts\python -m pytest` and ensure all tests pass.

### Review Findings

- [x] [Review][Patch] Fallback `primary_currency` to single present transaction currency in `aggregate_transactions` when default primary currency is absent [`src/services/query_service.py`:107-113]

## Dev Notes

### Architecture & Service Design

- **RAG-Lite In-Memory Aggregation Principle**:
  Because transaction amounts and concepts are stored as AES-256 Fernet ciphertexts in PostgreSQL (`amount` column contains encrypted string `f"{amount} {currency}"`), SQL-level aggregations (`SUM()`, `AVG()`) cannot be executed directly by PostgreSQL. 
  The service queries decrypted records for the tenant (`family_id`) within the temporal date range (resolved by `_resolve_date_range`), and then aggregates the decrypted records in memory.
- **Service Pattern & Singleton**:
  Maintain the existing thread-safe singleton pattern in `src/services/query_service.py`.
- **Multi-Currency Handling**:
  Transactions can have varying currencies (e.g. `"USD"`, `"EUR"`, `"GBP"`). `currency_totals` dictionary must record exact sums per currency code (e.g. `{"USD": 120.0, "EUR": 45.0}`). `total_amount` represents the sum of transactions matching `primary_currency` (default `"USD"`), avoiding misleading cross-currency addition without verified exchange rates.
- **Calendar & Timezone Calculation Helpers**:
  Use UTC timezone throughout. For month comparisons, compute preceding month boundaries handling January (where preceding month is December of previous year):
  ```python
  if ref_time.month == 1:
      prev_month = 12
      prev_year = ref_time.year - 1
  else:
      prev_month = ref_time.month - 1
      prev_year = ref_time.year
  ```

### Previous Story Intelligence (Story 3.1 Learnings)

- **Async DB Offloading**: Always run synchronous database queries and cryptographic decryption routines inside `asyncio.to_thread()` so the FastAPI event loop is never blocked.
- **Database Session Isolation**: Always instantiate a new `with Session(engine) as session:` within the worker thread to prevent session leakage across concurrent requests.
- **Ollama Timeout & Schema**: Ollama requests must use `asyncio.wait_for(..., timeout=60.0)` and pass `format=ParsedQueryIntent.model_json_schema()`.
- **Testing Pattern**: As seen in `tests/services/test_query_service.py`, wrap async test executions with `import asyncio; asyncio.run(_test())` within synchronous test functions because the environment does not use the `pytest-asyncio` plugin.

### Project Structure Notes

- **Modified Files**:
  - [MODIFY] `src/core/config.py` - Add `DEFAULT_CURRENCY` setting
  - [MODIFY] `src/services/query_service.py` - Add aggregation models, computation functions, and query service methods
  - [MODIFY] `tests/services/test_query_service.py` - Add comprehensive test suite for time-based aggregations
- **Reused Components**:
  - `src/core/config.py` (`settings`)
  - `src/core/encryption.py` (`EncryptionService`)
  - `src/db/models.py` (`Transaction`, `User`, `Family`)
  - `src/db/session.py` (`engine`)

### References

- [Architecture: Data Architecture & Encryption](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/architecture.md#L114)
- [Architecture: Service Layer Pattern](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/architecture.md#L163)
- [Epics: Story 3.2](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/epics.md#L238)
- [PRD: Conversational Queries (ASK)](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/prd.md#L102)
- [Previous Story: Story 3.1](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/implementation-artifacts/3-1-natural-language-query-processor-rag-lite.md#L1)

## Dev Agent Record

### Agent Model Used

Gemini 3.7 Flash (High)

### Debug Log References

### Completion Notes List

- Completed all configuration updates for primary currency.
- Created TimeAggregation and PeriodComparison models.
- Implemented `aggregate_transactions`, `_resolve_comparison_timeframe`, and `compute_period_comparison`.
- Extended QueryService to expose `get_time_aggregation` and integrated it into `process_query`.
- Authored passing unit tests for all features using TDD.

### File List

- `src/core/config.py`
- `src/services/query_service.py`
- `tests/services/test_query_service.py`
