---
story_id: "25.1"
epic_id: "25"
title: "Orthogonal Query AST Models & Stage 1 LLM Normalizer"
status: "done"
priority: "high"
author: "Winston, Amelia, John & Murat"
date: "2026-11-01"
---

# Story 25.1: Orthogonal Query AST Models & Stage 1 LLM Normalizer

## 1. Overview & Context

Clanomy's current financial query processor relies on a rigid `ParsedQueryIntent` enum and regex fast-paths (e.g., `upcoming_bills_patterns`). When a user submits an inquiry like *"Can you show me the details of my bills last 3 months"*, the engine erroneously classifies it under `UPCOMING_BILLS` due to keyword pattern matching, leading to temporal collisions, empty result sets, or failed queries.

This story implements Stage 1 of the Lean Decoupled Query Engine:
1. **Orthogonal Pydantic v2 AST Models:** Replaces monolithic intent enums with composable models: `TemporalScope` (dates, temporal polarity flags), `EntityFilters` (domains, category hints, status, counterparty), and `QueryOperation` (operation, grouping).
2. **Stage 1 LLM Normalizer:** Formulates a single structured LLM prompt that decomposes unstructured inquiries into the Pydantic AST without requiring backend database dumps or catalog schemas.
3. **Deprecation of Regex Hijacking:** Removes brittle regex matchers that intercept "bill" or "bills" queries before semantic parsing.

---

## 2. User Story & Acceptance Criteria

### User Story
As a Clanomy User,  
I want the AI engine to parse my natural language question into structured dimensions (time window, domain entities, requested calculations) without rigid single-intent categorization,  
So that complex, comparative, or historical queries are understood accurately without regex hijacking.

### Acceptance Criteria
- [x] **AC 25.1.1 (Orthogonal AST Models):** Define `TemporalScope`, `EntityFilters`, `QueryOperation`, and `NormalizedQueryAST` in `src/services/query/models.py` using Pydantic v2 with strict validation and timezone awareness.
- [x] **AC 25.1.2 (Temporal Polarity & Boundary Resolution):**
  - Resolves ISO dates for relative windows ("last 3 months", "this week", "yesterday", "since January").
  - Emits boolean flags: `is_historical: bool` (period is in the past) and `is_projected: bool` (period extends into the future).
- [x] **AC 25.1.3 (Stage 1 LLM Normalization Prompt):**
  - Implement `normalize_query_ast(text: str, user_tz: str, ref_date: datetime)` in `src/services/query/normalizer.py`.
  - Context isolation: The prompt does not receive database records, preventing hallucinated entity substitutions.
- [x] **AC 25.1.4 (Regex Hijack Elimination):** Remove or bypass brittle regex patterns in `src/services/query/service.py` that intercept keywords like "bills" into fixed upcoming bill intents.
- [x] **AC 25.1.5 (Backward Compatibility Adapter):** Provide an adapter mapping `NormalizedQueryAST` to legacy handler interfaces where needed during transition.

---

## 3. Tasks / Subtasks
- [x] **Task 1: Pydantic v2 AST Definitions** (AC: 25.1.1, 25.1.2)
  - [x] Add `TemporalScope`, `EntityFilters`, `QueryOperation`, `NormalizedQueryAST` to `src/services/query/models.py`.
  - [x] Implement validator methods ensuring date validity and timezone coherence.
- [x] **Task 2: Normalization Prompt & Service** (AC: 25.1.3)
  - [x] Author structured prompt in `src/services/query/prompts.py` for AST normalization.
  - [x] Implement `normalize_query_ast` utilizing `LLMFactory` with structured output JSON schema.
- [x] **Task 3: Refactor Query Entrypoint** (AC: 25.1.4, 25.1.5)
  - [x] Refactor `QueryService.parse_intent` to invoke AST normalization.
  - [x] Eliminate regex interceptors in `src/services/query/service.py`.
- [x] **Task 4: Unit Testing** (AC: All)
  - [x] Write unit tests in `tests/services/test_query_normalizer.py` verifying AST extraction across past, future, and comparative phrasing.
