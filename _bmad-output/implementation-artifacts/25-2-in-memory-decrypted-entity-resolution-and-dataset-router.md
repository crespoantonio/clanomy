---
story_id: "25.2"
epic_id: "25"
title: "In-Memory Decrypted Entity Resolution & Cross-Domain Dataset Router"
status: "done"
priority: "high"
author: "Winston, Amelia & John"
date: "2026-11-01"
---

# Story 25.2: In-Memory Decrypted Entity Resolution & Cross-Domain Dataset Router

## 1. Overview & Context

Clanomy's security model mandates AES-256 (Fernet/AES-GCM) encryption at rest for sensitive transaction data (`amount`, `concept`). Because of this, traditional SQL queries cannot perform semantic filtering or `ILIKE '%bill%'` directly in Postgres. Furthermore, queries involving "bills" have historically collided between `ScheduledBill` (recurring templates and pending/paid status) and `Transaction` (historical payments classified under utility/bill categories).

This story implements Stage 2:
1. **Cross-Domain Dataset Router:** Based on `TemporalScope.is_historical` vs `TemporalScope.is_projected`, automatically routes queries across `Transaction`, `ScheduledBill`, or a hybrid union.
2. **In-Memory Decrypted Entity Resolution:** Pulls active family bill templates and categories in memory, decrypts their labels, and uses deterministic fuzzy matching (RapidFuzz token sort ratio) to resolve requested entity hints without exposing ciphertext or sending data out to external LLMs.

---

## 2. User Story & Acceptance Criteria

### User Story
As a Household Administrator,  
I want my query to automatically target the correct records (whether historical transactions or recurring bill definitions) based on time polarity and entity hints,  
So that asking for past bills checks settled payments while asking for future bills checks pending commitments.

### Acceptance Criteria
- [x] **AC 25.2.1 (Temporal Polarity Dataset Routing):**
  - If `is_historical=True` and domain targets `bills`: Query both `ScheduledBill` (`status IN ('paid', 'pending')`) and `Transaction` (categories `Rent/Bills`, `utilities`).
  - If `is_projected=True` and domain targets `bills`: Query strictly `ScheduledBill` (`status = 'pending'`, `due_date >= now`).
  - If spanning both: Fetch both datasets concurrently using `asyncio.gather`.
- [x] **AC 25.2.2 (In-Memory Entity Resolution with RapidFuzz):**
  - Candidate entity matching against concept names (e.g., "electricity", "Iberdrola", "Netflix") executes in Python memory against decrypted family templates.
  - Matches with score ≥80 are classified as `EXACT`; score between 60-79 as `ALTERNATIVE`; below 60 as `NOT_FOUND`.
- [x] **AC 25.2.3 (Zero Privacy Leakage):** Decrypted text remains strictly in local memory and is never passed to unauthenticated logs or secondary LLM prompts.

---

## 3. Tasks / Subtasks
- [x] **Task 1: Dataset Router Implementation** (AC: 25.2.1)
  - [x] Implement `DatasetRouter` in `src/services/query/dataset_router.py`.
  - [x] Support concurrent fetching of transactions and scheduled bills based on temporal bounds.
- [x] **Task 2: In-Memory Entity Resolver** (AC: 25.2.2, 25.2.3)
  - [x] Implement `InMemoryEntityResolver` using `rapidfuzz.fuzz.token_sort_ratio`.
  - [x] Cache decrypted family templates during request lifecycle.
- [x] **Task 3: Unit Testing** (AC: All)
  - [x] Test cross-domain retrieval in `tests/services/test_dataset_router.py`.
  - [x] Test entity fuzzy matching across Spanish/English synonyms.
