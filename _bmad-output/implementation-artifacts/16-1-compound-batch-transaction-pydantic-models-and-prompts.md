# Story 16.1: Compound Batch Transaction Pydantic Models & Prompts

**Epic:** Epic 16 - Compound Batch Transaction Extraction & Multi-Item Undo
**Status:** Completed
**Author:** Amelia & Winston
**Date:** 2026-09-02

---

## 1. Overview & Context

Users frequently report multiple expenses or incomes in a single voice note or text message (*"Spent 15 on lunch and 40 on petrol"*). The extraction pipeline requires structured models and tailored prompt engineering to extract compound intents into individual structured transactions.

---

## 2. Technical Implementation

### 2.1 Pydantic Models
- In `src/services/extraction/models.py`:
  - `TransactionExtractionResult`: Single transaction entity (`type`, `amount`, `currency`, `category`, `concept`, `date`).
  - `BatchTransactionExtractionResult`: Container holding `items: List[TransactionExtractionResult]`.

### 2.2 Extraction Prompts
- In `src/services/extraction/prompts.py`:
  - Enriched system prompts to identify multi-item clauses.
  - Generates structured JSON matching `BatchTransactionExtractionResult.model_json_schema()`.

---

## 3. Verification & Acceptance

- Validated via `tests/unit/test_batch_extraction_and_undo.py`.
- Verified extraction of multiple items from compound sentences in English and Spanish.
