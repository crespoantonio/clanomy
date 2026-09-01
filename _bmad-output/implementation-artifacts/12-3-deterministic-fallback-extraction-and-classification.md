---
story_id: "12.3"
epic_id: "12"
title: "Deterministic Fallback Extraction & Classification"
status: "done"
priority: "high"
---

# Story 12.3: Deterministic Fallback Extraction & Classification

## User Story
As a User,
I want standard financial logs to succeed even if the AI inference engine is temporarily down,
So that my logging habit is never disrupted by service outages.

## Acceptance Criteria
- [x] Implement `src/services/extraction/fallback.py` with:
  - `_fallback_regex_extract()`
  - `_fallback_regex_classify()`
  - Bilingual pattern dictionaries for Spanish and English financial phrases.
- [x] Automatically catch AI timeouts/connection errors and route through the fallback engine.
- [x] Accurately extract amount, currency, category, and concept for common logs.
- [x] Unit test fallback behavior in `tests/services/test_extraction_service.py`.

## Tasks / Subtasks
- [x] **Fallback Engine** (AC: 1, 3)
  - [x] Author comprehensive regex matching in `src/services/extraction/fallback.py`.
- [x] **Circuit Breaker** (AC: 2)
  - [x] Wire fallback invocation into `ExtractionService.extract()` on exception.
- [x] **Testing** (AC: 4)
  - [x] Add tests verifying successful extraction without Ollama or Groq active.
