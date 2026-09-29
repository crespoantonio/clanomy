---
story_id: "9.2"
epic_id: "9"
title: "Family Currency Configuration & Chat Command"
status: "done"
priority: "high"
---

# Story 9.2: Family Currency Configuration & Chat Command

## User Story
As a Household Admin,
I want to set or inspect our family's currency using `/currency <ISO>` or natural language,
So that our family records are denominated in our local currency.

## Acceptance Criteria
- [x] Create `src/services/handlers/currency_handler.py` to process `/currency` and `/currency <ISO>` commands.
- [x] Implement `set_family_default_currency()` and `get_family_default_currency()` in `src/services/family_service.py`.
- [x] Validate currency codes against ISO 4217 standard 3-letter uppercase codes.
- [x] Integrate natural language routing in `AIOrchestrator` for currency phrases (*"set default currency to EUR"*, *"cambiar moneda a ARS"*).
- [x] Update `/start` welcome message to proactively recommend currency configuration on onboarding.

## Tasks / Subtasks
- [x] **FamilyService Methods** (AC: 2, 3)
  - [x] Implement getter and setter with session persistence in `src/services/family_service.py`.
- [x] **Currency Handler** (AC: 1, 3)
  - [x] Create `src/services/handlers/currency_handler.py` with validation and error cards.
- [x] **Orchestrator & Telegram Ingress** (AC: 4, 5)
  - [x] Route `/currency` command in `src/api/routes/telegram.py` and `ai_orchestrator.py`.
  - [x] Update `/start` prompt tips and `/help` menu.
- [x] **Testing**
  - [x] Unit tests in `tests/services/test_family_service.py` and `tests/services/test_ai_orchestrator.py`.
