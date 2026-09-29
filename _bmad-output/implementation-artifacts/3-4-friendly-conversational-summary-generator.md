# Story 3.4: Friendly Conversational Summary Generator

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a User,
I want the bot to summarize my financial history and query results in a warm, friendly, conversational tone (including period comparisons, category insights, and encouraging highlights),
so that I feel financially aware, in control of my household budget, and motivated without the stress and spreadsheet anxiety of dry financial tables.

## Acceptance Criteria

1. **Conversational Summary Field in Data Models**:
   - Extend `QueryResult` schema in `src/services/query_service.py`:
     - `summary: Optional[str] = None` (the conversational, natural language summary generated for the query)
   - Ensure full backwards compatibility with all existing fields in `QueryResult` (`intent`, `resolved_start_time`, `resolved_end_time`, `transactions`, `total_count`, `aggregation`, `category_breakdown`).

2. **Grounded Context Assembly & Prompt Engineering**:
   - Implement `_build_summary_prompt_context(query_result: QueryResult, user_name: Optional[str] = None) -> str` (or equivalent helper) that compiles computed deterministic data into factual context for the LLM:
     - User query intent and timeframe (e.g., `"this_week"`, `"this_month"`, `"today"`, `"last_month"`, `"custom"`, `"all_time"`)
     - Total spending in primary currency (e.g., `"45.00 USD"`) and full `currency_totals` dictionary if multiple currencies exist
     - Transaction count and average per transaction
     - Top spending category and percentage share (e.g., `"Food/Drink: $45.00 (60.0% of total)"`)
     - Period comparison metrics if available (previous total, difference amount, percentage change up or down)
     - Concise sample concepts from the transaction list (e.g., `"Coffee at Starbucks ($5.00)", "Supermarket groceries ($40.00)"`)
   - System prompt instructions for Ollama:
     - Tone: Warm, supportive, empathetic, and encouraging personal financial assistant.
     - Subtle visual cues: Use appropriate, tasteful emojis (e.g., ☕ for food/drink, 🚗 for transport, 📉/📈 for comparison, 🎉 for under budget, 💡 for insights).
     - **Strict Factual Fidelity (Anti-Hallucination)**: The summary must strictly reflect ONLY the numbers, categories, dates, and concepts provided in the prompt context. It must NEVER invent dollar amounts, merchants, or comparison percentages not in the data.
     - Conciseness: Keep the summary between 2 and 4 sentences (concise and punchy for mobile messaging like Telegram).
     - Zero-Spending Empathy: When `total_count == 0` or total spending is 0.0, provide a friendly, reassuring message (e.g., `"You haven't logged any expenses for this week yet! You're sitting pretty at $0.00."`).
     - Multi-Currency Clarity: Clearly mention secondary currencies if present (e.g., `"$50.00 USD plus €20.00 EUR"`).

3. **Deterministic Fallback Summary Engine (Offline / Zero-Downtime Resilience)**:
   - Implement `generate_fallback_summary(query_result: QueryResult, user_name: Optional[str] = None) -> str`:
     - Rule-based, template-driven summary generator that operates with zero external dependencies and zero latency (< 1ms).
     - Provides instant fallback if Ollama is unreachable, times out, or throws an exception.
     - Handles zero-spending: `"You haven't logged any expenses for {timeframe} yet (Total: $0.00 {currency})."`
     - Handles period comparison: `"You've spent {total} {currency} across {count} transactions this {timeframe} (Top category: {top_cat} at {top_amount}). That's {diff} ({pct}%) {more/less} than {prev_timeframe} ({prev_total} {currency})!"`
     - Handles general category spending and multi-currency totals without errors or missing fields.

4. **Conversational Summary Generation Engine (`generate_summary`)**:
   - Implement `QueryService.generate_summary(query_result: QueryResult, user_name: Optional[str] = None, use_llm: bool = True) -> str`:
     - If `use_llm=True` (default): Call Ollama asynchronously with the structured context and prompt, applying a 30.0s timeout.
     - If Ollama generation succeeds and returns non-empty text, return the sanitized, trimmed response.
     - If Ollama fails, times out, or returns empty text: Log warning and immediately return `generate_fallback_summary(query_result, user_name)`.
     - Log performance under the 3s Audit standard: `[3s Audit] Conversational summary generation took {elapsed:.2f} seconds (llm_used: {bool})`.

5. **Integration with `QueryService.process_query()`**:
   - Extend `QueryService.process_query()` signature:
     `async def process_query(self, text: str, family_id: UUID, user_name: Optional[str] = None, generate_summary: bool = True, reference_time: Optional[datetime] = None) -> QueryResult:`
   - After computing `TimeAggregation`, `PeriodComparison`, and `CategoryBreakdown`, when `generate_summary=True`, invoke `self.generate_summary(query_result, user_name=user_name)` and populate `query_result.summary`.

6. **Direct Summary API & Standalone Helper**:
   - Implement `QueryService.get_spending_summary(family_id: UUID, timeframe: str = "this_month", category: Optional[str] = None, user_name: Optional[str] = None, reference_time: Optional[datetime] = None) -> str`:
     - Direct convenience method that retrieves aggregations, builds `QueryResult`, generates a conversational summary, and returns the formatted text directly.

7. **Unit & Integration Test Suite**:
   - Add comprehensive tests in `tests/services/test_query_service.py`:
     - Test `_build_summary_prompt_context` with single-category, multi-category, comparison data, multi-currency, and empty transactions.
     - Test `generate_fallback_summary` across all scenarios:
       - Normal spending with spending decrease (e.g. 10% less than last week).
       - Spending increase (e.g. 15% more than last month).
       - Zero spending / empty transaction list.
       - Single non-default currency and multi-currency scenarios.
     - Test `generate_summary` with mocked Ollama success response.
     - Test `generate_summary` with Ollama failure / timeout (asserting fallback summary is returned seamlessly without raising unhandled exceptions).
     - Test `process_query` end-to-end verifying `result.summary` is populated.
     - Test `get_spending_summary` direct convenience method.
     - Ensure 100% test pass rate across the full test suite (`pytest`).

## Tasks / Subtasks

- [x] **Data Model Extension** (AC: 1)
  - [x] Add `summary: Optional[str] = None` field to `QueryResult` in `src/services/query_service.py`.
- [x] **Context Assembly & Prompt Design** (AC: 2)
  - [x] Implement `_build_summary_prompt_context()` helper function in `src/services/query_service.py`.
  - [x] Define the system prompt with anti-hallucination guardrails, emoji conventions, and tone guidelines.
- [x] **Deterministic Fallback Summary Generator** (AC: 3)
  - [x] Implement `generate_fallback_summary()` helper function in `src/services/query_service.py`.
  - [x] Support zero-spending, positive/negative period comparisons, top category breakdown, and multi-currency outputs.
- [x] **Summary Generation Engine Implementation** (AC: 4, 6)
  - [x] Implement `QueryService.generate_summary()` method with async Ollama invocation and automatic fallback.
  - [x] Add `[3s Audit]` performance logging for summary generation.
  - [x] Implement `QueryService.get_spending_summary()` direct method.
- [x] **`QueryService.process_query()` Integration** (AC: 5)
  - [x] Update `QueryService.process_query()` to accept `user_name` and `generate_summary` parameters.
  - [x] Attach generated summary to `QueryResult.summary`.
- [x] **Comprehensive Unit & Integration Testing** (AC: 7)
  - [x] Test `_build_summary_prompt_context()` formatting with rich dataset and empty dataset.
  - [x] Test `generate_fallback_summary()` for zero spending, comparison decrease, comparison increase, and multi-currency.
  - [x] Test `generate_summary()` with mocked Ollama success.
  - [x] Test `generate_summary()` with Ollama exception/timeout triggering fallback.
  - [x] Test `process_query()` integration with summary output.
  - [x] Test `get_spending_summary()` convenience method.
  - [x] Run full test suite with `.\venv\Scripts\python -m pytest` and ensure 100% pass rate.

### Review Findings

- [x] [Review][Patch] Handle zero difference (`difference_amount == 0.0`) in `generate_fallback_summary` [`src/services/query_service.py`:385-387]
- [x] [Review][Patch] Refine zero-spending condition in `generate_fallback_summary` so `total_count > 0` with zero amount shows transaction count [`src/services/query_service.py`:363]

## Dev Notes

### Architecture & Service Design

- **RAG-Lite Summary Generation Pipeline**:
  1. Intent Extraction & Date Resolution: Ollama extracts `ParsedQueryIntent` (Story 3.1).
  2. Database Fetch & Decryption: SQLModel fetches tenant-scoped transactions with `family_id`; Fernet AES-256 decrypts amounts & concepts in `asyncio.to_thread` (Story 3.1).
  3. Deterministic In-Memory Aggregation: `aggregate_transactions` (Story 3.2), `compute_period_comparison` (Story 3.2), and `aggregate_by_category` (Story 3.3) calculate exact numbers, currency totals, percentages, and comparison diffs.
  4. Conversational Summary Generation (Story 3.4): The exact numbers and insights are formatted into a compact context block and passed to Ollama (or fallback template) to generate a friendly, human, empathetic summary.
- **Anti-Hallucination Guardrails**:
  LLMs can hallucinate math and figures if asked to calculate from raw records. In FamFin-AI, all mathematical calculations (sums, averages, percentage changes, category shares) are computed deterministically in Python before prompting the LLM. The LLM's sole task is **linguistic phrasing and tone synthesis** using the supplied facts.
- **Resilience & Graceful Degradation**:
  If Ollama is busy, offline, or slow, `generate_fallback_summary` guarantees that the user receives an accurate, human-readable summary in < 1ms without seeing an error message.
- **3s Audit Compliance**:
  The summary generation step is instrumented with `time.time()` and logged as `[3s Audit] Conversational summary generation took {elapsed:.2f} seconds`.

### Previous Story Intelligence (Stories 3.1, 3.2, 3.3 Learnings)

- **Double-Checked Locking Singleton**: `QueryService` uses thread-safe singleton initialization.
- **Thread Isolation for DB Operations**: Synchronous SQLModel queries and encryption routines are offloaded via `asyncio.to_thread()`.
- **Category Aliases**: Canonical categories (`"Food/Drink"`, `"Transport"`, `"Rent/Bills"`, `"Shopping"`, `"Leisure"`, `"Other"`) are resolved via `resolve_category_alias()`.
- **Multi-Currency Safety**: `currency_totals` dictionary preserves exact amounts per currency without lossy unverified FX conversion.
- **Test Pattern**: Async tests in `tests/services/test_query_service.py` are wrapped with `import asyncio; asyncio.run(_test())` inside standard pytest test functions.

### Project Structure Notes

- **Modified Files**:
  - [MODIFY] `src/services/query_service.py` - Add `QueryResult.summary`, `_build_summary_prompt_context`, `generate_fallback_summary`, `generate_summary`, `get_spending_summary`, and update `process_query`.
  - [MODIFY] `tests/services/test_query_service.py` - Add tests for context building, fallback summary, LLM summary generation, fallback triggering, and end-to-end `process_query` summary generation.
- **Reused Components**:
  - `src/core/config.py` (`settings`, `DEFAULT_CURRENCY`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL`)
  - `src/core/encryption.py` (`EncryptionService`)
  - `src/db/models.py` (`Transaction`, `User`, `Family`)
  - `src/db/session.py` (`engine`)

### References

- [Architecture: Inference Engine & Ollama](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/architecture.md#L100)
- [Architecture: Conversational Query Logic](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/architecture.md#L26)
- [Architecture: 3s Rule Audit](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/architecture.md#L182)
- [Epics: Story 3.4](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/epics.md#L263)
- [PRD: Conversational Summaries FR9](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/prd.md#L29)
- [Previous Story: Story 3.3](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/implementation-artifacts/3-3-category-based-spending-filters.md#L1)

## Dev Agent Record

### Agent Model Used

Gemini 3.7 Flash (High)

### Debug Log References

### Completion Notes List

- ✅ Resolved task: Data Model Extension: Added `summary` field to `QueryResult`
- ✅ Resolved task: Context Assembly & Prompt Design: Implemented `_build_summary_prompt_context` with deterministic context formatting
- ✅ Resolved task: Deterministic Fallback Summary Generator: Implemented `generate_fallback_summary` handling edge cases (0.0 total, comparisons)
- ✅ Resolved task: Summary Generation Engine Implementation: Added `generate_summary` and `get_spending_summary` direct methods
- ✅ Resolved task: `QueryService.process_query()` Integration: Updated `process_query` signature and integrated with LLM generation logic
- ✅ Resolved task: Comprehensive Unit & Integration Testing: All tests are passing

### File List

- src/services/query_service.py
- tests/services/test_query_service.py
