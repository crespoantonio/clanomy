# Story 3.3: Category-Based Spending Filters

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a User,
I want to filter and analyze my spending history by specific categories (such as "Food/Drink", "Transport", "Rent/Bills", "Shopping", "Leisure", "Other", or related aliases like "Groceries" and "Utilities"),
so that I can identify specific spending leaks, understand category-level cash outflows, and manage my household budget effectively.

## Acceptance Criteria

1. **Category-Based Data Models**:
   - Define `CategorySpending` schema in `src/services/query_service.py`:
     - `category`: `str` (the canonical category name, e.g., `"Food/Drink"`)
     - `total_amount`: `float` (sum of transaction amounts matching `primary_currency`, rounded to 2 decimal places)
     - `primary_currency`: `str` (default `"USD"`, configurable via `settings.DEFAULT_CURRENCY`)
     - `currency_totals`: `Dict[str, float]` (exact amounts summed per distinct currency code, e.g. `{"USD": 75.50, "EUR": 20.00}`)
     - `transaction_count`: `int` (number of transactions in this category)
     - `percentage_of_total`: `Optional[float]` (percentage of overall spending across all categories in the period; `None` if overall total is 0.0)
     - `average_per_transaction`: `float` (0.0 if `transaction_count` is 0)
   - Define `CategoryBreakdown` schema in `src/services/query_service.py`:
     - `timeframe`: `str` (e.g., `"today"`, `"this_week"`, `"this_month"`, `"last_month"`, `"custom"`, `"all_time"`)
     - `start_time`: `Optional[datetime]`
     - `end_time`: `Optional[datetime]`
     - `total_spending`: `float` (overall sum of spending across all categories in `primary_currency`)
     - `primary_currency`: `str` (default `"USD"`)
     - `categories`: `Dict[str, CategorySpending]` (mapping canonical category names to their respective `CategorySpending` records, sorted by `total_amount` descending)
     - `top_category`: `Optional[str]` (category name with the highest spending amount; `None` if no spending)
     - `top_category_amount`: `Optional[float]` (highest spending amount; `None` if no spending)
   - Extend `TimeAggregation` schema in `src/services/query_service.py` to include:
     - `category_breakdown`: `Dict[str, float] = {}` (mapping category names to total amount in primary currency)
   - Extend `QueryResult` schema in `src/services/query_service.py` to include:
     - `category_breakdown`: `Optional[CategoryBreakdown] = None`

2. **Category Normalization & Alias/Synonym Resolution**:
   - Enhance category normalization in `ParsedQueryIntent` and `src/services/query_service.py`:
     - Maintain the 6 canonical system categories: `"Food/Drink"`, `"Transport"`, `"Rent/Bills"`, `"Shopping"`, `"Leisure"`, `"Other"`.
     - Implement `resolve_category_alias(input_category: Optional[str]) -> Optional[str]` helper that maps common synonyms/aliases to canonical categories:
       - `"Food/Drink"`: `groceries`, `grocery`, `food`, `drink`, `drinks`, `dining`, `restaurant`, `restaurants`, `coffee`, `cafe`, `supermarket`, `lunch`, `dinner`, `breakfast`, `snacks`, `bar`, `pub`, `takeout`, `delivery`
       - `"Transport"`: `transport`, `transportation`, `uber`, `taxi`, `cab`, `gas`, `fuel`, `petrol`, `bus`, `train`, `subway`, `metro`, `transit`, `parking`, `toll`, `flight`, `flights`, `airline`
       - `"Rent/Bills"`: `rent`, `bills`, `utilities`, `utility`, `electricity`, `electric`, `water`, `gas bill`, `power`, `internet`, `wifi`, `phone`, `mobile`, `mortgage`, `insurance`, `subscription`, `subscriptions`
       - `"Shopping"`: `shopping`, `clothes`, `clothing`, `apparel`, `shoes`, `electronics`, `gadgets`, `hardware`, `tools`, `amazon`, `books`, `home`, `furniture`
       - `"Leisure"`: `leisure`, `entertainment`, `movies`, `cinema`, `games`, `gaming`, `concerts`, `hobby`, `hobbies`, `sports`, `gym`, `fitness`, `vacation`, `travel`, `clubbing`, `party`
       - `"Other"`: `other`, `misc`, `miscellaneous`, `uncategorized`, `fees`, `bank fees`, `donations`, `gifts`
     - If an exact canonical category is passed (case-insensitive), return canonical form directly.
     - If an alias matches, return the mapped canonical category.
     - If unmapped non-empty string, return `"Other"`. If `None` or empty, return `None`.

3. **Core Category Aggregation Engine**:
   - Implement `aggregate_by_category(transactions: List[DecryptedTransaction], timeframe: str = "all_time", start_time: Optional[datetime] = None, end_time: Optional[datetime] = None, primary_currency: str = "USD", overall_total: Optional[float] = None) -> CategoryBreakdown`:
     - Group transactions by `tx.category`.
     - For each category, compute `currency_totals`, `total_amount` (in `primary_currency`), `transaction_count`, and `average_per_transaction`.
     - If `overall_total` is not explicitly provided, calculate it as the sum of all transactions matching `primary_currency` across all categories.
     - Calculate `percentage_of_total` for each category: `(cat_total / overall_total) * 100` if `overall_total > 0`, else `None`.
     - Identify `top_category` and `top_category_amount`.
     - Populate `CategoryBreakdown` with `categories` sorted by `total_amount` in descending order.
     - Handle empty transactions list gracefully without division by zero, returning a zeroed `CategoryBreakdown`.

4. **Integration with `QueryService.process_query()`**:
   - In `QueryService.process_query()`:
     - If `intent.category` is specified (e.g., user asks "How much did I spend on Food/Drink this month?"), normalize it using `resolve_category_alias()` and filter SQL transactions by `Transaction.category == resolved_category`.
     - Populate `aggregation.category_breakdown` with category-to-amount mapping for all retrieved transactions.
     - In addition to `TimeAggregation`, generate and attach `CategoryBreakdown` to `QueryResult.category_breakdown`.
     - If user query is a category breakdown query without a specific category filter (e.g., "Show my spending breakdown by category for this month"), retrieve all transactions for the timeframe and compute the full `CategoryBreakdown`.

5. **Direct Category Aggregation API**:
   - Implement `QueryService.get_category_aggregation(family_id: UUID, category: Optional[str] = None, timeframe: str = "this_month", primary_currency: Optional[str] = None, reference_time: Optional[datetime] = None) -> CategoryBreakdown`:
     - Direct, non-LLM method for API routes, scheduled reports, and category dashboard commands.
     - When `category` is provided, filters for that specific category (resolving aliases).
     - When `category` is `None`, aggregates across all categories in the specified timeframe.
     - Runs synchronous DB calls in `asyncio.to_thread`.

6. **Multi-Currency Safety & 3s Audit Performance**:
   - `currency_totals` dictionary must preserve distinct currencies per category without loss or unverified conversions.
   - Category filtering and aggregation must execute in `< 10ms` for in-memory datasets up to 10,000 transactions.
   - Include 3s Audit log: `[3s Audit] Category query took {elapsed:.2f} seconds (category: {category}, timeframe: {timeframe}, family_id: {family_id})`.

7. **Unit & Integration Testing**:
   - Add comprehensive tests in `tests/services/test_query_service.py`:
     - Test category normalization with exact canonical names, lowercase names, and aliases (e.g., `"groceries"` -> `"Food/Drink"`, `"utilities"` -> `"Rent/Bills"`, `"hardware"` -> `"Shopping"`).
     - Test `aggregate_by_category` with multiple categories, verifying `percentage_of_total`, `top_category`, and descending sort order.
     - Test single-category filtering where only transactions for the requested category are returned.
     - Test empty transaction sets return zeroed `CategoryBreakdown` without division-by-zero errors.
     - Test multi-currency category aggregations (`currency_totals` accuracy per category).
     - Test `get_category_aggregation` method with and without specific category filters.
     - Test `process_query` with category-filtered queries (mocking Ollama response).
     - Ensure 100% test pass rate across the full test suite with `.\venv\Scripts\python -m pytest`.

## Tasks / Subtasks

- [x] **Data Model & Schema Extensions** (AC: 1)
  - [x] Define `CategorySpending` Pydantic model in `src/services/query_service.py`.
  - [x] Define `CategoryBreakdown` Pydantic model in `src/services/query_service.py`.
  - [x] Update `TimeAggregation` model to include `category_breakdown: Dict[str, float] = {}`.
  - [x] Update `QueryResult` model to include `category_breakdown: Optional[CategoryBreakdown] = None`.
- [x] **Category Normalization & Alias Engine** (AC: 2)
  - [x] Implement `resolve_category_alias()` helper function in `src/services/query_service.py`.
  - [x] Update `ParsedQueryIntent.normalize_category()` validator to leverage `resolve_category_alias()`.
- [x] **Category Aggregation Engine Implementation** (AC: 3, 6)
  - [x] Implement `aggregate_by_category()` function in `src/services/query_service.py`.
  - [x] Support `percentage_of_total`, `currency_totals`, `top_category`, and descending sort order.
  - [x] Update `aggregate_transactions()` to populate `category_breakdown` dictionary.
- [x] **QueryService Integration & Direct API** (AC: 4, 5, 6)
  - [x] Update `QueryService.process_query()` to compute and attach `CategoryBreakdown` to `QueryResult`.
  - [x] Implement `QueryService.get_category_aggregation()` method for programmatic category queries.
  - [x] Update Ollama system prompt in `process_query` to include category aliases guidance.
  - [x] Add `[3s Audit]` logging for category query execution times.
- [x] **Unit & Integration Test Suite** (AC: 7)
  - [x] Add tests for `resolve_category_alias` with standard and alias inputs in `tests/services/test_query_service.py`.
  - [x] Add tests for `aggregate_by_category` (multi-category, percentage calculation, top category).
  - [x] Add tests for empty transaction lists and zero-spending edge cases.
  - [x] Add tests for `get_category_aggregation` with specific category and all categories.
  - [x] Add integration tests for `process_query` with category queries.
  - [x] Execute `.\venv\Scripts\python -m pytest` to verify all tests pass.

### Review Findings

- [x] [Review][Patch] Fallback `effective_currency` to single present transaction currency in `aggregate_by_category` when default primary currency is absent [`src/services/query_service.py`:197-217]
- [x] [Review][Patch] Handle whitespace variations around slash in category names (e.g., `"Food / Drink"`) in `resolve_category_alias` [`src/services/query_service.py`:27-48]

## Dev Notes

### Architecture & Service Design

- **RAG-Lite In-Memory Aggregation with SQL Indexing**:
  Because `category` is an unencrypted, indexed column in PostgreSQL (`category: str = Field(index=True)` in `src/db/models.py`), filtering by category at the database level (`Transaction.category == resolved_category`) is efficient and indexed.
  However, because `amount` is stored as AES-256 ciphertext, calculation of `total_amount`, `currency_totals`, `percentage_of_total`, and `average_per_transaction` must be performed in memory after decrypting the records for the tenant (`family_id`).
- **Canonical Categories**:
  The 6 canonical categories defined in Epic 2 (`ExtractionService`) are:
  - `"Food/Drink"`
  - `"Transport"`
  - `"Rent/Bills"`
  - `"Shopping"`
  - `"Leisure"`
  - `"Other"`
- **Category Aliases**:
  Users frequently use natural language synonyms when querying (e.g., "How much did I spend on groceries?" or "What were my utility bills this month?"). `resolve_category_alias()` maps these common synonyms into canonical categories while allowing `concept_keyword` search as a fallback if the user asks for a specific vendor or item.
- **Top Category & Ranking**:
  `CategoryBreakdown.categories` should be sorted with the highest spending category first, providing immediate insights into primary spending categories.

### Previous Story Intelligence (Stories 3.1 & 3.2 Learnings)

- **Async Database Offloading**: Run synchronous database queries and cryptographic decryption routines inside `asyncio.to_thread()` to prevent blocking the FastAPI event loop.
- **Database Session Isolation**: Always instantiate a new `with Session(engine) as session:` within the worker thread to prevent session leakage across concurrent requests.
- **Thread-Safe Singleton**: Maintain the double-checked locking singleton pattern in `QueryService`.
- **Testing Pattern**: Wrap async test executions with `import asyncio; asyncio.run(_test())` within synchronous test functions in `tests/services/test_query_service.py`.

### Project Structure Notes

- **Modified Files**:
  - [MODIFY] `src/services/query_service.py` - Add category models, alias resolution, `aggregate_by_category`, and `get_category_aggregation`
  - [MODIFY] `tests/services/test_query_service.py` - Add comprehensive unit and integration test coverage for category filtering and breakdown
- **Reused Components**:
  - `src/core/config.py` (`settings`, `DEFAULT_CURRENCY`)
  - `src/core/encryption.py` (`EncryptionService`)
  - `src/db/models.py` (`Transaction`, `User`, `Family`)
  - `src/db/session.py` (`engine`)

### References

- [Architecture: Data Architecture & Encryption](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/architecture.md#L114)
- [Architecture: Service Layer Pattern](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/architecture.md#L163)
- [Epics: Story 3.3](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/epics.md#L251)
- [PRD: Conversational Queries (ASK)](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/prd.md#L102)
- [Previous Story: Story 3.2](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/implementation-artifacts/3-2-time-based-aggregations-weekly-monthly-totals.md#L1)

## Dev Agent Record

### Agent Model Used

Gemini 3.1 Pro (Low)

### Debug Log References

### Completion Notes List
- Implemented models (`CategorySpending`, `CategoryBreakdown`) and updated existing ones (`TimeAggregation`, `QueryResult`).
- Implemented category alias resolution and updated `ParsedQueryIntent` to use it.
- Created `aggregate_by_category` to generate metrics and sort categories by spending.
- Updated `process_query` to compute and attach `CategoryBreakdown` and added `get_category_aggregation` method.
- Passed 100% of unit tests successfully (`pytest` on 60 items).

### File List
- `src/services/query_service.py`
- `tests/services/test_query_service.py`
