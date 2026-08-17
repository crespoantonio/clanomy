# Story 5.3: Per-Member Spending Attribution

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a User,
I want to see which family member logged a specific expense,
so that we have full transparency in our shared ledger and can track individual contributions to the household budget.

## Acceptance Criteria

1. **Per-Transaction Contributor Attribution**:
   - Every decrypted transaction (`DecryptedTransaction`) includes the identity of the family member who created it:
     - `user_id: UUID` (existing)
     - `user_name: Optional[str] = None` (e.g. `User.full_name` or `User.username` or fallback `"User"`)
     - `user_handle: Optional[str] = None` (e.g. `@username` or `None`)
   - `QueryService._fetch_and_decrypt_transactions` and `ExportService._decrypt_transaction` retrieve and associate user information (e.g. joining `User` or pre-fetching family users in a single query map) to populate `user_name` and `user_handle` without N+1 query overhead.
   - When sample transactions or lists are prepared for LLM prompts or summaries, each entry includes contributor attribution (e.g. *"Coffee ($4.50 USD by Tony)"* or *"Groceries ($85.00 USD by @maria)"*).

2. **Per-Member Spending Aggregation (`MemberBreakdown`)**:
   - Define `MemberSpending` and `MemberBreakdown` Pydantic models in `src/services/query_service.py`:
     ```python
     class MemberSpending(BaseModel):
         user_id: UUID
         user_name: str
         user_handle: Optional[str] = None
         total_amount: float
         primary_currency: str = "USD"
         currency_totals: Dict[str, float]
         transaction_count: int
         percentage_of_total: Optional[float] = None
         average_per_transaction: float
         top_category: Optional[str] = None

     class MemberBreakdown(BaseModel):
         timeframe: str
         start_time: Optional[datetime] = None
         end_time: Optional[datetime] = None
         total_spending: float
         primary_currency: str = "USD"
         members: Dict[str, MemberSpending] # Keyed by user display name
         top_spender: Optional[str] = None
         top_spender_amount: Optional[float] = None
     ```
   - Implement `aggregate_by_member(transactions: List[DecryptedTransaction], timeframe: str, start_time: Optional[datetime], end_time: Optional[datetime], primary_currency: str, overall_total: Optional[float]) -> MemberBreakdown`.
   - Include `member_breakdown: Optional[MemberBreakdown] = None` inside `QueryResult`.

3. **Per-Member Query Intent & Filtering**:
   - Update `ParsedQueryIntent` in `src/services/query_service.py` to include `member_filter: Optional[str] = None`.
   - Update `QueryService.parse_intent` system prompt to recognize member-specific and member-breakdown queries, extracting target member names into `member_filter`:
     - Examples: *"Who spent what this month?"*, *"What did Maria spend this week?"*, *"Who spent the most today?"*, *"Show me Tony's expenses"*, *"Breakdown by family member"*, *"Who bought coffee?"*.
   - When `member_filter` is present, `_fetch_and_decrypt_transactions` filters records to those logged by the specified member (case-insensitive match against `full_name` or `username`).

4. **Conversational Summaries with Attribution**:
   - Update `_build_summary_prompt_context` in `src/services/query_service.py`:
     - If multiple members contributed to the queried period, format a `Member Breakdown` section:
       ```
       Member Breakdown:
       - Tony: 120.00 USD (3 transactions, 58.4% of total, Top category: Shopping)
       - Maria: 85.50 USD (2 transactions, 41.6% of total, Top category: Food/Drink)
       ```
     - In `Sample transactions`, format each item with contributor: `Concept (Amount Currency by Member)`.
   - Update `generate_summary` LLM prompt:
     - Instruct the model to provide empathetic, transparent per-member attribution when multiple contributors exist (e.g. *"This month, your family spent $205.50 across 5 transactions. Tony contributed $120.00 (mostly on Shopping) and Maria spent $85.50 on Groceries."*).
   - Update `generate_fallback_summary`:
     - If `member_breakdown` has multiple members: append member attribution summary (e.g. *"Your family has spent $205.50 across 5 transactions this month (Tony: $120.00; Maria: $85.50)."*).
     - If `member_filter` was applied (e.g. "What did Maria spend?"): formulate response as *"{member_name} has spent $85.50 across 2 transactions this month."*.

5. **Data Export Contributor Attribution (CSV & JSON)**:
   - In `src/services/export_service.py`:
     - `generate_csv`: Update CSV column headers to `["Timestamp (UTC)", "Amount", "Currency", "Category", "Concept", "Logged By"]`. Output `tx.user_name or "User"` in the "Logged By" column.
     - `generate_json`: Include `"user_id": str(tx.user_id)` and `"logged_by": tx.user_name or "User"` in each transaction object.
     - Ensure `export_data` fetches and populates user names without performance degradation.

6. **Performance & Latency (The 3s Rule)**:
   - All DB operations for member resolution and transaction filtering must execute synchronously in worker threads via `asyncio.to_thread()`.
   - Use batch lookups for users (`select(User).where(User.family_id == family_id)`) to build a fast memory map (`{user.id: user}`) to avoid N+1 queries.
   - Measure and log `[3s Audit]` execution times for member breakdown and attribution queries.

7. **Comprehensive Unit & Integration Test Suite**:
   - `tests/services/test_query_service.py`:
     - Test `DecryptedTransaction` creation with `user_name` and `user_handle`.
     - Test `aggregate_by_member` calculation of member totals, percentages, top spenders, and multi-currency attribution.
     - Test query filtering by `member_filter` (exact and case-insensitive).
     - Test `_build_summary_prompt_context` and `generate_fallback_summary` with member breakdown and member-specific filters.
   - `tests/services/test_export_service.py`:
     - Test CSV export includes "Logged By" header and member names.
     - Test JSON export includes `user_id` and `logged_by` fields.
   - `tests/services/test_ai_orchestrator.py`:
     - Test conversational handling of member-specific questions (e.g. "What did Tony spend?").
     - Test member breakdown questions (e.g. "Who spent what?", "spending by member").
   - Ensure 100% test pass rate with `.\venv\Scripts\python -m pytest`.

## Tasks / Subtasks

- [x] **Data Model & Aggregation Extensions** (AC: 1, 2)
  - [x] Add `user_name: Optional[str] = None` and `user_handle: Optional[str] = None` to `DecryptedTransaction` in `src/services/query_service.py`.
  - [x] Implement `MemberSpending` and `MemberBreakdown` Pydantic models in `src/services/query_service.py`.
  - [x] Implement `aggregate_by_member` in `src/services/query_service.py` to calculate per-member sums, transaction counts, percentages, and top spenders.
  - [x] Add `member_breakdown: Optional[MemberBreakdown] = None` to `QueryResult`.
  - [x] Update `_fetch_and_decrypt_transactions` in `src/services/query_service.py` to batch-fetch `User` records for the family and attach `user_name`/`user_handle` to each `DecryptedTransaction`.
- [x] **Query Intent & Member Filtering** (AC: 3)
  - [x] Add `member_filter: Optional[str] = None` to `ParsedQueryIntent` in `src/services/query_service.py`.
  - [x] Update `QueryService.parse_intent` system prompt with member query and breakdown examples.
  - [x] Update `_fetch_and_decrypt_transactions` to filter transactions by `member_filter` when specified.
- [x] **Conversational Summary & Prompt Context Attribution** (AC: 4)
  - [x] Update `_build_summary_prompt_context` to append `Member Breakdown` and per-transaction contributor attributions.
  - [x] Update `generate_summary` LLM system prompt to guide conversational attribution across family members.
  - [x] Update `generate_fallback_summary` to format multi-member contributions and member-specific query summaries.
  - [x] Update `get_spending_summary` and `process_query` to compute and attach `member_breakdown`.
- [x] **Export Service Attribution Updates** (AC: 5)
  - [x] Update `ExportService._decrypt_transaction` and `export_data` to populate `user_name` on `DecryptedTransaction`.
  - [x] Update `generate_csv` to add `"Logged By"` header and column.
  - [x] Update `generate_json` to include `"logged_by"` and `"user_id"` in exported records.
- [x] **AI Orchestrator Integration** (AC: 3, 4, 6)
  - [x] Update `_is_special_intent` in `src/services/ai_orchestrator.py` to recognize member queries (e.g. "who spent", "who bought", "member spending", "spending by person").
  - [x] Ensure orchestrator correctly routes member-specific queries through `QueryService`.
  - [x] Add `[3s Audit]` performance logging.
- [x] **Test Suite Implementation & Verification** (AC: 7)
  - [x] Add unit tests in `tests/services/test_query_service.py` for member aggregation, member filtering, and prompt context.
  - [x] Add unit tests in `tests/services/test_export_service.py` for CSV/JSON member attribution columns.
  - [x] Add integration tests in `tests/services/test_ai_orchestrator.py` for member-specific queries.
  - [x] Run `.\venv\Scripts\python -m pytest` to verify 100% pass rate.

### Review Findings

- [x] [Review][Patch] Fallback Display Name Inconsistency in ExportService [`src/services/export_service.py:75`]
- [x] [Review][Patch] Member Spending Aggregation Keying Collision [`src/services/query_service.py:317`]


## Dev Notes

### Architecture & Service Design

- **Attribution Data Flow**:
  1. `Transaction` table stores `user_id: UUID` (foreign key to `User.id`) and `family_id: UUID` (foreign key to `Family.id`).
  2. In `QueryService._fetch_and_decrypt_transactions` and `ExportService.export_data`, all `User` records in the `family_id` are fetched in a single query:
     ```python
     users = session.exec(select(User).where(User.family_id == family_id)).all()
     user_map = {u.id: (u.full_name or u.username or "User", f"@{u.username}" if u.username else None) for u in users}
     ```
  3. When decrypting each transaction:
     ```python
     display_name, handle = user_map.get(tx.user_id, ("User", None))
     decrypted_tx = DecryptedTransaction(
         id=tx.id,
         family_id=tx.family_id,
         user_id=tx.user_id,
         user_name=display_name,
         user_handle=handle,
         amount=amount,
         currency=currency,
         concept=concept_str,
         category=tx.category,
         timestamp=tx.timestamp
     )
     ```
  4. If `member_filter` is provided (e.g., `member_filter="Maria"`), transactions can be filtered:
     ```python
     if member_filter:
         target = member_filter.strip().lower().lstrip("@")
         results = [
             tx for tx in results 
             if (tx.user_name and target in tx.user_name.lower()) or 
                (tx.user_handle and target in tx.user_handle.lower())
         ]
     ```

- **Per-Member Aggregation (`aggregate_by_member`)**:
  - Computes total spending per member in the primary currency.
  - Computes transaction counts and percentage of overall family spending.
  - Identifies top spending category per member and family top spender.

- **Non-blocking Execution & Performance**:
  - All database queries run within `with Session(engine) as session:` wrapped in `await asyncio.to_thread(...)`.
  - Batch user resolution prevents N+1 query latency, easily satisfying the `< 3.0s` requirement.

### Source Files to Touch

#### [MODIFY] [src/services/query_service.py](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/src/services/query_service.py)
- **Current State**: `DecryptedTransaction` only has `user_id`. `ParsedQueryIntent` has `scope` and `category`. Aggregations only group by time and category.
- **Changes for Story 5.3**:
  - Add `user_name` and `user_handle` to `DecryptedTransaction`.
  - Add `MemberSpending` and `MemberBreakdown` models.
  - Implement `aggregate_by_member()`.
  - Add `member_breakdown` to `QueryResult`.
  - Add `member_filter` to `ParsedQueryIntent` and update `parse_intent` prompt.
  - Update `_fetch_and_decrypt_transactions` to load users map and populate `user_name`/`user_handle`, and filter by `member_filter`.
  - Update `_build_summary_prompt_context`, `generate_summary`, and `generate_fallback_summary` to include member breakdown.
- **Preserve**: All existing category normalization, time-based aggregation, period comparison, and error handling.

#### [MODIFY] [src/services/export_service.py](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/src/services/export_service.py)
- **Current State**: Exports transactions without `Logged By` in CSV or JSON.
- **Changes for Story 5.3**:
  - Update `_decrypt_transaction` and `fetch_and_process` in `export_data` to load family users and populate `user_name` on `DecryptedTransaction`.
  - In `generate_csv`: Include `"Logged By"` in header and output `tx.user_name or "User"` for each row.
  - In `generate_json`: Include `"logged_by": tx.user_name or "User"` in each transaction record.
- **Preserve**: Temp file creation, cleanup in `finally` blocks, and Telegram document transmission.

#### [MODIFY] [src/services/ai_orchestrator.py](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/src/services/ai_orchestrator.py)
- **Current State**: Heuristics in `_is_special_intent` detect family queries and export requests.
- **Changes for Story 5.3**:
  - Add keywords to `_is_special_intent` for member attribution (e.g., "who spent", "who bought", "member spending", "spending by person").
  - Ensure member filters from parsed queries are passed cleanly to `QueryService`.
- **Preserve**: All existing command handling (`/createfamily`, `/invite`, `/family`, `/familytotal`, delete confirmation).

#### [MODIFY] [tests/services/test_query_service.py](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/tests/services/test_query_service.py)
- **Changes**: Add unit tests for member attribution fields, `aggregate_by_member`, member filtering, and conversational summary attribution.

#### [MODIFY] [tests/services/test_export_service.py](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/tests/services/test_export_service.py)
- **Changes**: Add tests for CSV "Logged By" column and JSON "logged_by" field.

#### [MODIFY] [tests/services/test_ai_orchestrator.py](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/tests/services/test_ai_orchestrator.py)
- **Changes**: Add tests for member-specific queries and breakdown routing.

### Anti-Patterns to Prevent

- **N+1 Database Queries**: Never perform a separate `session.get(User, tx.user_id)` for every transaction. Always batch load family users into a dictionary lookup map.
- **Cross-Tenant Leaks**: Ensure user lookup and transaction fetching are strictly constrained by `Transaction.family_id == family_id` and `User.family_id == family_id`.
- **Breaking Export Consumers**: Keep existing CSV columns in order and append `"Logged By"` as the 6th column (`Timestamp (UTC), Amount, Currency, Category, Concept, Logged By`).
- **Blocking Event Loop**: Wrap all database operations and file operations in `asyncio.to_thread`.
- **Vague Summary Generation**: Ensure the LLM system prompt enforces strict fidelity to the exact member names and calculated amounts in the prompt context.

### References

- [Architecture: Multi-Tenancy & Family Scoping](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/architecture.md#L105)
- [Architecture: Project Directory Structure](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/architecture.md#L196)
- [Epics: Story 5.3 (Per-Member Spending Attribution)](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/epics.md#L334)
- [PRD: Family Groups & Shared Ledger (FR11, Journey 3.4)](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/prd.md#L66-L68)
- [Story 5.1: Family Group Creation & Invite Link](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/implementation-artifacts/5-1-family-group-creation-invite-link.md)
- [Story 5.2: Shared Budget Visibility](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/implementation-artifacts/5-2-shared-budget-visibility.md)

## Dev Agent Record

### Agent Model Used

Gemini 3.7 Flash (High)

### Debug Log References

### Completion Notes List

### File List
