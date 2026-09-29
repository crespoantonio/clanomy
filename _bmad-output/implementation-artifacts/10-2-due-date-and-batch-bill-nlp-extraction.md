---
story_id: "10.2"
epic_id: "10"
title: "Due Date & Batch Bill NLP Extraction"
status: "done"
priority: "high"
---

# Story 10.2: Due Date & Batch Bill NLP Extraction

## User Story
As a User,
I want to record single or multiple upcoming bills with due dates in a single message,
So that I can register our monthly commitments quickly.

## Acceptance Criteria
- [x] Extend `UnifiedResult` and extraction models to detect `bills: List[Dict]` and `due_date`.
- [x] Extract multi-bill statements (e.g., *"El 10 vence la luz 45000 y el 15 el gas 12000"* or *"Rent 1500 due on the 1st"*).
- [x] Support relative days and numeric calendar days in Spanish and English.
- [x] Persist extracted bills into `ScheduledBill` table with `status="pending"`.
- [x] Format an immediate conversational confirmation detailing all registered obligations.

## Tasks / Subtasks
- [x] **Extraction Schema & Prompts** (AC: 1, 2, 3)
  - [x] Update prompts and parsing in `src/services/extraction/prompts.py` and `fallback.py`.
- [x] **Orchestration** (AC: 4, 5)
  - [x] In `src/services/ai_orchestrator.py`, handle batch bill persistence and response formatting.
- [x] **Testing**
  - [x] Automated tests in `tests/services/test_scheduled_bills.py`.
