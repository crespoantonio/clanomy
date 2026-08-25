---
story_id: "8.2"
epic_id: "8"
title: "Dual-Intent Natural Language Extraction (Income vs Expense)"
status: "ready-for-dev"
priority: "high"
---

# Story 8.2: Dual-Intent Natural Language Extraction (Income vs Expense)

## User Story
As a Developer,
I want the Ollama extraction service to classify transaction intent as either income or expense,
So that incoming voice and text notes are accurately categorized with amount, currency, concept, and category.

## Acceptance Criteria
- [ ] Update `src/services/extraction_service.py` to upgrade Ollama extraction prompt for dual-intent classification (`"type": "expense" | "income"`).
- [ ] Ensure extraction JSON format returns:
  ```json
  {
    "type": "expense" | "income",
    "amount": 3500.0,
    "currency": "USD",
    "category": "Salary",
    "concept": "Acme Corp"
  }
  ```
- [ ] Correctly classify earnings keywords: *"salary"*, *"earned"*, *"got paid"*, *"sold"*, *"bonus"*, *"freelance payment"*, *"dividend"*, *"invoice paid"*, *"received"* $\rightarrow$ `"type": "income"`.
- [ ] Correctly classify spending keywords: *"spent"*, *"bought"*, *"paid for"*, *"coffee"*, *"lunch"*, *"rent"* $\rightarrow$ `"type": "expense"`.
- [ ] Default safely to `"expense"` when intent is ambiguous.
- [ ] Add accuracy benchmark test suite in `tests/services/test_extraction_service.py` testing both income and expense phrases across multiple currencies.

## Technical Notes
- Ollama model is run locally using JSON format mode.
- System prompt must explicitly instruct the LLM to output valid JSON conforming to the schema and never include extra markdown or commentary outside the JSON object.
