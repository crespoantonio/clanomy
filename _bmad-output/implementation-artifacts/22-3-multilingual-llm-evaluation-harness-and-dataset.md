# Story 22.3: Multilingual LLM Evaluation Harness & Dataset

**Epic:** Epic 22 - Landing Page Web App, Simulation Endpoint & E2E LLM Evaluation Suite
**Status:** Completed
**Author:** Amelia & Murat
**Date:** 2026-09-03

---

## 1. Overview & Context

To systematically evaluate model extraction quality, prevent prompt regressions, and measure token latency across various LLM backends (Ollama, Gemini, Groq, OpenAI), Clanomy incorporates an automated evaluation test harness and standardized bilingual dataset.

---

## 2. Technical Implementation

### 2.1 Standardized Evaluation Dataset
- In `tests/data/llm_extraction_dataset.py`:
  - Curated comprehensive test cases covering single expenses, earnings/income, compound batches, relative dates, informal slang in English and Spanish, and edge cases (commas as decimals, multi-currency mentions).

### 2.2 Evaluation Runner Script & Integration Tests
- In `scripts/run_llm_eval.py`:
  - Command-line runner supporting flags for provider, model, concurrency, and temperature.
  - Generates comprehensive pass/fail metrics, exact-match scores, and latency benchmarks.
- In `tests/evaluation/test_llm_e2e_extraction.py`:
  - Pytest integration suite evaluating extraction precision and schema compliance against active model providers.

---

## 3. Verification & Acceptance

- Validated via `python scripts/run_llm_eval.py --provider gemini` and pytest suite.
- Verified >90% extraction accuracy across baseline bilingual dataset.
- Verified prompt caching metrics and latency measurements.
