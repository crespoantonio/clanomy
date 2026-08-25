---
story_id: "8.2"
epic_id: "8"
title: "Dual-Intent Natural Language Extraction (Income vs Expense)"
status: "done"
priority: "high"
---

# Story 8.2: Dual-Intent Natural Language Extraction (Income vs Expense)

Status: done

## User Story

As a Developer,
I want the Ollama extraction service to classify transaction intent as either income or expense,
So that incoming voice and text notes are accurately categorized with amount, currency, concept, and category.

## Acceptance Criteria

- [x] Update `src/services/extraction_service.py` to upgrade Ollama extraction prompt for dual-intent classification (`"type": "expense" | "income"`).
- [x] Ensure extraction JSON format returns:
  ```json
  {
    "type": "expense" | "income",
    "amount": 3500.0,
    "currency": "USD",
    "category": "Salary",
    "concept": "Acme Corp"
  }
  ```
- [x] Correctly classify earnings keywords: *"salary"*, *"earned"*, *"got paid"*, *"sold"*, *"bonus"*, *"freelance payment"*, *"dividend"*, *"invoice paid"*, *"received"* $\rightarrow$ `"type": "income"`.
- [x] Correctly classify spending keywords: *"spent"*, *"bought"*, *"paid for"*, *"coffee"*, *"lunch"*, *"rent"* $\rightarrow$ `"type": "expense"`.
- [x] Default safely to `"expense"` when intent is ambiguous.
- [x] Add accuracy benchmark test suite in `tests/services/test_extraction_service.py` testing both income and expense phrases across multiple currencies.

## Technical Notes

- Ollama model is run locally using JSON format mode.
- System prompt must explicitly instruct the LLM to output valid JSON conforming to the schema and never include extra markdown or commentary outside the JSON object.

## Tasks / Subtasks

- [x] **Task 1: Update Pydantic Extraction Schema & Validators** (AC: 1, 2, 4, 5)
  - [x] Add `type: Literal["expense", "income"]` to `ExtractionResult` defaulting to `"expense"`.
  - [x] Add validator for `type` normalizing case and safely falling back to `"expense"`.
  - [x] Expand category validation in `ExtractionResult` to support income categories ("Salary", "Bonus", "Freelance", "Investment", "Gift", "Sale", "Other") alongside expense categories ("Food/Drink", "Transport", "Rent/Bills", "Shopping", "Leisure", "Other").
- [x] **Task 2: Upgrade Ollama System Prompt & Fallback Parser** (AC: 1, 2, 3, 4, 5)
  - [x] Update system prompt in `ExtractionService.extract` to instruct the LLM on dual-intent classification (income vs expense keywords and category guidelines).
  - [x] Update `_fallback_regex_extract` to detect income keywords and assign `type="income"` and appropriate category, defaulting to `type="expense"`.
- [x] **Task 3: Accuracy Benchmark & Unit Test Suite** (AC: 3, 4, 5, 6)
  - [x] Add unit tests in `tests/services/test_extraction_service.py` for income extractions (salary, sales, freelance, dividends, bonuses).
  - [x] Add unit tests for expense extractions (purchases, coffee, rent, bills).
  - [x] Add unit tests for ambiguous phrases verifying default to `"expense"`.
  - [x] Add unit tests for fallback regex income and expense classification.
  - [x] Test multi-currency extraction across income and expenses (USD, EUR, GBP, etc.).

## Dev Notes

- **Model Schema**: `ExtractionResult.model_json_schema()` passes the updated schema including `type` to Ollama's `format` parameter.
- **Classification Keywords**:
  - Income: "salary", "earned", "got paid", "sold", "bonus", "freelance payment", "freelance", "dividend", "invoice paid", "received".
  - Expense: "spent", "bought", "paid for", "coffee", "lunch", "rent", "bills".
  - Ambiguous: Default to "expense".
- **Category Taxonomy**:
  - Expense: "Food/Drink", "Transport", "Rent/Bills", "Shopping", "Leisure", "Other"
  - Income: "Salary", "Bonus", "Freelance", "Investment", "Gift", "Sale", "Other"

## Dev Agent Record

### Agent Model Used

Gemini 3.7 Flash (High)

### Debug Log References

- Fixed Python 3.14 SQLModel table re-definition / type inspection incompatibility in `src/db/models.py`.
- Verified regex fallback order to prevent generic keywords from masking specific category detection.
- Ran full regression suite (162 tests passed) and compileall validation.

### Completion Notes List

- Updated `ExtractionResult` Pydantic model in `src/services/extraction_service.py` with `type: Literal["expense", "income"] = Field(default="expense")`, `@field_validator("type")`, and expanded `@field_validator("category")` supporting income taxonomies.
- Upgraded Ollama system prompt to explicitly guide dual-intent classification with rules for earnings vs spending vs ambiguous inputs.
- Implemented dual-intent support in `_fallback_regex_extract` with keyword heuristics for offline/fallback scenarios.
- Authored extensive benchmark unit tests in `tests/services/test_extraction_service.py` covering income phrases, expense phrases, multi-currency values, ambiguous phrases, and fallback behavior.

### File List

- `src/services/extraction_service.py`
- `src/db/models.py`
- `tests/services/test_extraction_service.py`
- `_bmad-output/implementation-artifacts/8-2-dual-intent-natural-language-extraction.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`

### Change Log

- 2026-08-25: Implemented dual-intent natural language extraction for Story 8.2 and added comprehensive test suite.

### Review Findings
- [x] [Review][Patch] Benchmark Tests Mock LLM instead of Verifying Prompt/API — The benchmark tests mock the LLM response perfectly rather than hitting the Ollama API to test real classification accuracy. Should we update the tests to hit the local Ollama instance or add assertions on the prompt text?
- [x] [Review][Patch] Missing Explicit Markdown/Commentary Prohibition in System Prompt [src/services/extraction_service.py]
- [x] [Review][Patch] Missing Ambiguous Phrase Test for LLM Pipeline [tests/services/test_extraction_service.py]
- [x] [Review][Patch] Missing Word Boundaries in Keyword Matching [src/services/extraction_service.py]
- [x] [Review][Patch] Flawed Fallback Precedence for Ambiguous Intent [src/services/extraction_service.py]
- [x] [Review][Patch] Fragile Regex Amount Extraction [src/services/extraction_service.py]
- [x] [Review][Patch] Silent Coercion on Invalid Categories [src/services/extraction_service.py]
- [x] [Review][Patch] Shadowing Built-in Keywords (type) [src/db/models.py]
- [x] [Review][Patch] Reckless Currency Detection [src/services/extraction_service.py]
