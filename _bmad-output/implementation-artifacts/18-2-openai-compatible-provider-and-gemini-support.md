# Story 18.2: OpenAI-Compatible Provider & Gemini Support

**Epic:** Epic 18 - Multi-Provider AI Inference Resilience, Prompt Caching & Speech-to-Text Fallbacks
**Status:** Completed
**Author:** Amelia & Winston
**Date:** 2026-09-02

---

## 1. Overview & Context

To maximize flexibility and avoid vendor lock-in, Clanomy consolidates all cloud LLM interactions into a single `OpenAICompatibleProvider` capable of connecting to Groq Cloud, OpenAI, Together AI, and Google Gemini via standard OpenAI-compatible endpoints.

---

## 2. Technical Implementation

### 2.1 Provider Factory
- In `src/core/llm/factory.py`:
  - Instantiates `OpenAICompatibleProvider` when `AI_API_KEY` is provided.
  - Automatically configures base URL, model name, and client options.

### 2.2 Provider Implementation
- In `src/core/llm/providers/openai_provider.py`:
  - Handles chat completions and structured JSON schema outputs (`response_format={"type": "json_object"}`).
  - Supports Google Gemini through standard OpenAI-compatible endpoint compatibility.

---

## 3. Verification & Acceptance

- Validated via `tests/unit/test_gemini_migration_and_prompts.py` and `tests/unit/test_groq_resilience.py`.
- Verified structured extraction schemas against mock OpenAI/Groq/Gemini responses.
