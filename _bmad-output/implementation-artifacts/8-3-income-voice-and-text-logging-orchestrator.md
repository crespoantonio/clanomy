---
story_id: "8.3"
epic_id: "8"
title: "Income Voice & Text Logging Orchestrator"
status: "ready-for-dev"
priority: "high"
---

# Story 8.3: Income Voice & Text Logging Orchestrator

## User Story
As a User,
I want to log my income via voice notes and text in under 3 seconds,
So that I get an immediate, upbeat confirmation of my earnings and our household's monthly cash flow.

## Acceptance Criteria
- [ ] Update `src/services/ai_orchestrator.py` to persist `type` field on `Transaction` records during async background processing.
- [ ] Maintain field-level encryption on `amount` and `concept` for income records.
- [ ] Implement conversational income confirmation feedback in `src/services/ai_orchestrator.py` / `src/services/messaging.py`:
  - Visual indicator: 💰 / Income badge
  - Display extracted amount, currency, category, and concept/source
  - Include monthly earnings total and updated net cash flow snapshot
- [ ] Log execution timing in compliance with the "3s Audit".
- [ ] Add integration tests in `tests/services/test_ai_orchestrator.py` and `tests/api/test_telegram_webhook.py` verifying the end-to-end income flow.

## Technical Notes
- Conversational UX Template:
  ```text
  💰 Income Logged: +$3,500.00 (Salary - Acme Corp)
  📊 August Snapshot:
  • Total In: $3,500.00
  • Total Out: $1,200.00
  • Net Savings: +$2,300.00 (65%)
  ```
