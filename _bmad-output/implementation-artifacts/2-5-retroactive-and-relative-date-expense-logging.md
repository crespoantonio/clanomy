# Story 2.5: Retroactive & Relative Date Expense Logging

Status: done

## Story

As a User,
I want to log expenses with relative or explicit past dates (e.g. "yesterday", "last week", "August 10th"),
So that my financial summaries remain accurate even if I forget to log an expense immediately.

## Acceptance Criteria

1. **Relative Date Extraction**: The extraction system must parse terms like "yesterday", "last week", "3 days ago" and translate them into a valid `YYYY-MM-DD` string based on the current date provided in the prompt.
2. **Absolute Date Extraction**: Explicit dates like "August 10th" or "2026-08-10" must be extracted correctly as `YYYY-MM-DD`.
3. **Context-Aware Anchor**: The extraction service must feed the current system date and time to the Ollama extraction prompt so it can anchor relative terms.
4. **Custom Timestamp Persistence**: The extracted date must be used as the `timestamp` for database insertion and Notion mirroring. If no date is extracted, or it explicitly maps to "today", default to the exact moment of execution (`datetime.now()`).
5. **Clear Confirmation Message**: If a custom date is parsed, the confirmation message back to the user must explicitly acknowledge the retroactive log (e.g., `(logged for Aug 11, 2026)`).
6. **Automated Tests**: Unit tests and integration tests must cover the new relative and absolute parsing flows and fallback logic.

## Tasks / Subtasks

- [ ] Add `transaction_date` to `ExtractionResult` and `to_datetime()` method.
- [ ] Add current date context to the extraction prompt.
- [ ] Update `ai_orchestrator.py` to allow custom timestamp persistence.
- [ ] Append parsed date to confirmation response.
- [ ] Update automated tests in `test_extraction_service.py` and `test_ai_orchestrator.py`.
