# Story 18.3: Static Prompt Caching & Exponential Backoff Resilience

**Epic:** Epic 18 - Multi-Provider AI Inference Resilience, Prompt Caching & Speech-to-Text Fallbacks
**Status:** Completed
**Author:** Amelia & Winston
**Date:** 2026-09-02

---

## 1. Overview & Context

To achieve sub-second response times, minimize cloud token costs, and maintain zero-downtime reliability during transient upstream outages, Clanomy implements static prompt caching optimizations and exponential backoff retry with jitter.

---

## 2. Technical Implementation

### 2.1 Static Prompt Caching
- In `src/services/extraction/prompts.py` and `src/services/query/prompts.py`:
  - Enforced prefix invariance: system prompts, schemas, and rule descriptions are fixed at the start of prompts.
  - Upstream LLM providers (e.g. Groq prompt cache, Anthropic/OpenAI prompt cache) hit existing prefix caches, cutting latency to <250ms and reducing input token costs by up to 50%.

### 2.2 Retry with Jitter
- In `src/core/llm/providers/openai_provider.py`:
  - Wrapped API requests in retry logic targeting HTTP 429 (Rate Limit) and 5xx (Server Error).
  - Uses exponential backoff with randomized jitter to prevent thundering herd problems.
  - Fails over to `src/services/extraction/fallback.py` if retries are exhausted.

---

## 3. Verification & Acceptance

- Validated via `tests/unit/test_gemini_migration_and_prompts.py` and `tests/unit/test_groq_resilience.py`.
- Verified retry behavior on rate-limit simulation and fallback activation on exhaustion.
