---
story_id: "9.3"
epic_id: "9"
title: "Bilingual NLP & Dynamic Currency Extraction"
status: "done"
priority: "high"
---

# Story 9.3: Bilingual NLP & Dynamic Currency Extraction

## User Story
As a User,
I want to log expenses in Spanish or English without typing the currency symbol every time,
So that my unadorned logs automatically record in our family's currency.

## Acceptance Criteria
- [x] Update `ExtractionService.extract()` and `classify_and_extract()` to accept dynamic `default_currency: str = "USD"`.
- [x] Dynamically pass household's `default_currency` from `AIOrchestrator` into extraction prompts.
- [x] Unadorned amounts (*"1500 en café"*, *"45 lunch"*) resolve to the injected family currency.
- [x] Explicit currencies (*"20 euros"*, *"50 USD"*) safely override household default.
- [x] Support full bilingual Spanish/English extraction of concepts and normalization of categories (*"supermercado"* $\rightarrow$ *"Food/Drink"*, *"alquiler"* $\rightarrow$ *"Rent/Bills"*).

## Tasks / Subtasks
- [x] **Extraction Normalizers** (AC: 1, 5)
  - [x] Enhance `src/services/extraction/normalizers.py` with Spanish category aliases and currency symbols.
- [x] **Prompt Engineering** (AC: 2, 3, 4)
  - [x] Update `src/services/extraction/prompts.py` to inject dynamic default currency.
- [x] **Testing & Verification**
  - [x] Test suite in `tests/services/test_extraction_service.py` with Spanish and English test vectors.
