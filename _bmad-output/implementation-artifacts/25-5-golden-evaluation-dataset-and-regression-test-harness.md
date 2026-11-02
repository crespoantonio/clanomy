---
story_id: "25.5"
epic_id: "25"
title: "Golden Evaluation Dataset & Regression Test Harness"
status: "done"
priority: "high"
author: "Murat & Amelia"
date: "2026-11-01"
---

# Story 25.5: Golden Evaluation Dataset & Regression Test Harness

## 1. Overview & Context

To validate the team's commitment to achieving ≥95% query resolution accuracy across messy, natural-language Telegram inputs, we must establish an empirical evaluation dataset and a zero-token CI regression harness.

This story implements:
1. **Golden Evaluation Dataset:** 150+ realistic queries spanning clean questions, noisy mobile speech-to-text, colloquial slang in English and Spanish, boundary/out-of-scope queries, and complex comparative questions (e.g. "dining out this weekend vs last weekend", "bills last 3 months").
2. **Deterministic Evaluation Harness:** Runs in CI using recorded fixtures / mock LLM providers to verify AST parsing accuracy, Parity Gate enforcement, and math execution without burning live API tokens.

---

## 2. User Story & Acceptance Criteria

### User Story
As a Quality Engineer and Developer,  
I want an automated regression harness with 150+ messy, multilingual, real-world financial queries,  
So that we empirically verify 95%+ query resolution accuracy and prevent regressions across future model updates.

### Acceptance Criteria
- [x] **AC 25.5.1 (Golden Dataset Definition):**
  - Implement `tests/data/query_engine_golden_dataset.py` containing ≥150 categorized test queries with expected `TemporalScope`, `EntityFilters`, and `QueryOperation`.
  - Categories: Auditing, Cash Flow, Discretionary Comparisons, Complex Bills, Slang & Voice Typos, Adversarial.
- [x] **AC 25.5.2 (Automated Eval Runner):**
  - Implement `scripts/run_query_eval.py` that computes accuracy, precision, recall, and Parity Gate rejection rates.
  - Generates a markdown report summarizing pass/fail metrics.
- [x] **AC 25.5.3 (CI Regression Gate):**
  - Fast unit/regression test in `tests/test_query_pipeline_regression.py` that executes in < 3 seconds using pre-recorded fixtures.

---

## 3. Tasks / Subtasks
- [x] **Task 1: Golden Dataset Assembly** (AC: 25.5.1)
  - [x] Construct dataset with 150+ examples in `tests/data/query_engine_golden_dataset.py`.
- [x] **Task 2: Evaluation Script** (AC: 25.5.2)
  - [x] Implement `scripts/run_query_eval.py` with AST scoring metrics.
- [x] **Task 3: CI Integration & Test Suite** (AC: 25.5.3)
  - [x] Add `tests/services/test_query_pipeline_regression.py`.
