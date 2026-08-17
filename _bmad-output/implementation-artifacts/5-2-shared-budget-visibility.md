# Story 5.2: Shared Budget Visibility

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a Family Member,
I want to see the total spending for our entire family,
so that all members can stay on budget and maintain collective financial visibility together.

## Acceptance Criteria

1. **Multi-User Family Transaction Aggregation**:
   - When a query for family spending is executed (e.g. via `/familytotal`, natural language "family total", "how much did we spend this month?", "our family spending", "what did the household spend on food?"):
     - The system queries and aggregates transactions across **ALL users** who belong to the same `family_id`.
     - Transactions from User A and User B in Family 1 are summed into a single unified total and breakdown.
     - Transactions from users belonging to other families are strictly excluded (multi-tenant isolation).
   - Multi-currency transactions from different family members are aggregated appropriately with the primary currency total and secondary currency breakdowns.

2. **Shared Family Query Intents & Command Routing**:
   - The query parser (`QueryService.parse_intent`) recognizes family-wide spending queries (e.g., "family total", "our spending this week", "what did we spend on groceries?", "how much have we spent today?", "family budget", "our monthly total").
   - Support a dedicated `/familytotal` command (with optional timeframe and category arguments, e.g., `/familytotal this_week`, `/familytotal groceries`) as a quick-action bypass.
   - The `AIOrchestrator` recognizes `/familytotal` and family query phrases in `_is_special_intent` and routes them seamlessly through `QueryService`.

3. **Family-Aware Conversational Summaries**:
   - `QueryService._build_summary_prompt_context`, `generate_summary`, and `generate_fallback_summary` incorporate family context (Family Name and active member names/count) when summarizing shared family spending.
   - When generating an LLM summary for family spending:
     - The prompt instructs the assistant to frame the summary from a collective perspective (e.g., *"The Smith Family has spent $120.00 across 4 transactions this month..."* or *"Together, you and Maria have spent $85.50 on Food/Drink this week..."*).
     - Strict factual fidelity is preserved (exact sums, categories, and comparisons matching the database records).
   - In fallback mode (when LLM is unavailable or offline):
     - Generate clear, grammatically natural collective summaries (e.g., *"Your family has spent $120.00 across 4 transactions this month (Top category: Food/Drink at $85.50)."*).

4. **Shared Category Breakdown & Period Comparisons**:
   - Category breakdowns (`aggregate_by_category`) for family queries represent the combined categorical expenses of all family members.
   - Timeframe comparisons (`compute_period_comparison`) compare the current period's total family spending against the previous period's total family spending (e.g. this week's family total vs last week's family total).

5. **Performance & Latency (The 3s Rule)**:
   - End-to-end multi-member family aggregation, decryption, and summary generation must execute within `< 3.0s` and be logged with `[3s Audit]` metrics.
   - Database operations must run synchronously in worker threads via `asyncio.to_thread` to prevent event loop blocking.

6. **Comprehensive Unit & Integration Test Suite**:
   - Create tests in `tests/services/test_query_service.py` to verify:
     - Multi-member transaction aggregation within the same family.
     - Cross-tenant isolation (Family 1 multi-user totals vs Family 2 records).
     - Family-aware prompt context and fallback summary generation.
     - Multi-currency handling across different family members.
     - Category breakdown and period comparison across multiple family members.
   - Update `tests/services/test_ai_orchestrator.py` to verify:
     - Direct `/familytotal` command routing.
     - Natural language queries for collective spending ("family total", "how much did we spend?").
     - Correct multi-user sum returned in outbound Telegram reply.
   - Ensure 100% test pass rate with `.\venv\Scripts\python -m pytest`.

## Tasks / Subtasks

- [x] **Query Intent & Schema Enhancements** (AC: 1, 2)
  - [x] Update `ParsedQueryIntent` in `src/services/query_service.py` with optional `scope: Optional[str] = "family"` or `is_family_query: Optional[bool] = False`.
  - [x] Enhance system prompt in `QueryService.parse_intent` with family query examples ("family total", "how much did we spend?", "our expenses", "what did the family spend on groceries?").
  - [x] Update `AIOrchestrator._is_special_intent` to recognize `/familytotal`, "family total", "family spending", "our spending", "how much did we spend".
- [x] **Family-Aware Summary Generation** (AC: 3, 4)
  - [x] Update `_build_summary_prompt_context` in `src/services/query_service.py` to accept `family_name: Optional[str] = None` and `member_names: Optional[List[str]] = None`.
  - [x] Update `generate_fallback_summary` to format collective family phrasing when `family_name` or `is_family_query` is present.
  - [x] Update `generate_summary` system prompt with instructions on summarizing family/group spending with empathy and collective tone.
  - [x] Update `get_spending_summary` and `process_query` signatures to accept optional `family_name` and `member_names`.
- [x] **AI Orchestrator & Command Routing Integration** (AC: 2, 5)
  - [x] In `AIOrchestrator.orchestrate()`, detect `/familytotal` and family query intents.
  - [x] Retrieve family name and member list via `FamilyService.get_family_info(user_uuid)` or DB session.
  - [x] Pass family metadata into `query_service.get_spending_summary()` and return the collective summary to Telegram.
  - [x] Ensure all DB calls use `asyncio.to_thread()` and log `[3s Audit]` performance metrics.
- [x] **Test Suite Implementation & Verification** (AC: 6)
  - [x] Add unit tests in `tests/services/test_query_service.py` for multi-member family aggregation, cross-tenant isolation, and collective summaries.
  - [x] Add integration tests in `tests/services/test_ai_orchestrator.py` for `/familytotal` and natural language family spending queries.
  - [x] Run `.\venv\Scripts\python -m pytest` to verify all tests pass with zero regressions.

### Review Findings

- [x] [Review][Patch] KeyError: 'id' in AIOrchestrator.orchestrate when calling family_info["id"] [`src/services/ai_orchestrator.py:169`] — `FamilyService.get_family_info` does not include `id` key in returned dict.
- [x] [Review][Patch] Fallback summary subject phrasing for unnamed family group queries [`src/services/query_service.py:372`] — Handle unnamed family queries with collective subject phrasing.
- [x] [Review][Patch] /familytotal command argument parsing for multi-argument queries [`src/services/ai_orchestrator.py:134`] — Parse both timeframe and category when provided to `/familytotal`.

## Dev Notes

### Architecture & Service Design

- **Multi-Tenancy Foundation**:
  In FamFin-AI, multi-tenancy is scoped at the `Family` level. Every `Transaction` record has `family_id: UUID` (foreign key to `Family.id`) and `user_id: UUID` (foreign key to `User.id`).
  When User A and User B belong to the same family (`User.family_id == family.id`), all their logged transactions already share `Transaction.family_id`.
  Therefore, querying by `Transaction.family_id == family_id` naturally retrieves all records contributed by any member of the family.

- **Differentiating Individual vs Collective Scope**:
  - A solo query (e.g. "What did I spend?") vs a family query (e.g. "What did we spend?" / "Family total"):
  - For Story 5.2, any query scoped to the family or asking for family totals will aggregate all transactions under `family_id`.
  - Summary prompt context must include the family name and member names so the LLM or fallback generator produces a warm, collective summary (e.g., *"The Vacation Group has spent $240.00 this week..."*).

- **Summary Prompt Formatting**:
  ```python
  def _build_summary_prompt_context(
      query_result: QueryResult, 
      user_name: Optional[str] = None,
      family_name: Optional[str] = None,
      member_names: Optional[List[str]] = None
  ) -> str:
      ctx = []
      if family_name:
          ctx.append(f"Family Group: {family_name}")
      if member_names:
          ctx.append(f"Family Members: {', '.join(member_names)}")
      elif user_name:
          ctx.append(f"User: {user_name}")
      ctx.append(f"Timeframe: {query_result.intent.timeframe}")
      # ... rest of metrics (total spending, currency totals, transaction count, comparisons, categories)
      return "\n".join(ctx)
  ```

- **Fallback Summary Collective Phrasing**:
  ```python
  def generate_fallback_summary(
      query_result: QueryResult, 
      user_name: Optional[str] = None,
      family_name: Optional[str] = None,
      member_names: Optional[List[str]] = None
  ) -> str:
      tf = query_result.intent.timeframe.replace('_', ' ')
      subject = f"Your family ({family_name})" if family_name else (f"Hi {user_name}! You" if user_name else "You")
      # Formulate: "Your family (The Smiths) has spent $120.00 across 4 transactions this month..."
  ```

- **Non-blocking Execution & 3s Audit**:
  All database operations must continue to use `with Session(engine) as session:` inside synchronous helpers invoked via `await asyncio.to_thread(...)`.
  Measure execution time and log `[3s Audit] Family query took {elapsed:.2f} seconds (family_id: {family_id}, timeframe: {timeframe})`.

### Source Files to Touch

#### [MODIFY] [src/services/query_service.py](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/src/services/query_service.py)
- **Current State**: `ParsedQueryIntent` parses single-user spending intents. `_build_summary_prompt_context` and `generate_fallback_summary` only receive `user_name` and format "You've spent...".
- **Changes for Story 5.2**:
  - Add `scope: Optional[str] = "family"` to `ParsedQueryIntent`.
  - Update system prompt in `parse_intent` with family query examples.
  - Update `_build_summary_prompt_context`, `generate_fallback_summary`, `generate_summary`, `get_spending_summary`, and `process_query` to support `family_name` and `member_names`.
  - Update `generate_summary` LLM prompt to instruct collective summaries when `family_name` or multiple members are provided.
- **Preserve**: All existing category normalization, date range resolution, time-based aggregation, period comparison, and error handling.

#### [MODIFY] [src/services/ai_orchestrator.py](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/src/services/ai_orchestrator.py)
- **Current State**: Routes commands like `/family`, `/invite`, `/createfamily`, and generic `spending_summary`.
- **Changes for Story 5.2**:
  - Update `_is_special_intent` to match `/familytotal`, "family total", "family spending", "our spending", "how much did we spend".
  - Handle `/familytotal` command directly (e.g. `/familytotal` -> `ParsedQueryIntent(intent="spending_summary", timeframe="this_month", scope="family")`).
  - In `spending_summary` handling, fetch family name and members via `FamilyService.get_family_info(user_uuid)` or DB session, and pass to `query_service.get_spending_summary(family_id, timeframe, category, user_name, family_name, member_names)`.
- **Preserve**: Existing expense logging, audio transcription, account deletion, and export routing.

#### [MODIFY] [tests/services/test_query_service.py](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/tests/services/test_query_service.py)
- **Changes**: Add unit tests for multi-member transaction aggregation, cross-tenant isolation, family-aware context building, and fallback summary formatting.

#### [MODIFY] [tests/services/test_ai_orchestrator.py](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/tests/services/test_ai_orchestrator.py)
- **Changes**: Add tests verifying `/familytotal` and natural language family spending queries aggregate multi-user transactions and return collective summaries.

### Anti-Patterns to Prevent

- **Cross-Tenant Leaks**: Always ensure database queries filter strictly by `Transaction.family_id == family_id`.
- **Accidental User-Level Filtering**: Do NOT filter by `Transaction.user_id` when executing family-level aggregations; all members of the family must be included.
- **Hardcoding Currency**: Respect multi-currency records logged by different family members (e.g., User A logged EUR, User B logged USD).
- **Blocking Event Loop**: Never execute raw database queries directly in async orchestrator or route handlers without `asyncio.to_thread()`.
- **Inventing Facts in Summaries**: Ensure the LLM system prompt enforces strict factual fidelity to the aggregated numbers.

### References

- [Architecture: Multi-Tenancy & Family Scoping](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/architecture.md#L105)
- [Epics: Story 5.2 (Shared Budget Visibility)](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/epics.md#L322)
- [PRD: Family Groups & Shared Ledger (FR11, Journey 3.4)](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/prd.md#L66-L68)
- [Story 5.1: Family Group Creation & Invite Link](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/implementation-artifacts/5-1-family-group-creation-invite-link.md)
- [Epic 4 Retrospective](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/implementation-artifacts/epic-4-retro-2026-08-16.md)

## Dev Agent Record

### Agent Model Used

Gemini 3.1 Pro (Low)

### Debug Log References

### Completion Notes List

- Ultimate context engine analysis completed: created comprehensive developer guide with exhaustive guardrails, multi-user aggregation specifications, collective summary prompt designs, and test suites.
- Added scope: Optional[str] = "family" to ParsedQueryIntent.
- Updated _is_special_intent to recognize /familytotal and other group-based budget intents.
- Handled /familytotal specifically in orchestrator to return group summaries gracefully using get_family_info and passing metadata downwards.
- Expanded QueryService.generate_summary and generate_fallback_summary to accept member_names and family_name to alter wording to encompass plural/collective groups.
- All test suites successfully cover multi-member spending aggregation, tenant isolation, and direct prompt routing.

### Change Log

- Updated `src/services/query_service.py` and `src/services/ai_orchestrator.py` to support shared budget visibility.
- Expanded testing suite to encompass multi-tenant validations in `tests/services/test_query_service.py` and `/familytotal` command tests in `tests/services/test_ai_orchestrator.py`.

### File List

- `src/services/query_service.py` (UPDATE)
- `src/services/ai_orchestrator.py` (UPDATE)
- `tests/services/test_query_service.py` (UPDATE)
- `tests/services/test_ai_orchestrator.py` (UPDATE)
