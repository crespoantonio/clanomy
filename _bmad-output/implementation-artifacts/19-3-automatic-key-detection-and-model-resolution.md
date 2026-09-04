# Story 19.3: Automatic Key Detection & Model Resolution

**Epic:** Epic 19 - Native Google Gemini Multimodal Provider & Direct Audio Engine
**Status:** Completed
**Author:** Amelia & Winston
**Date:** 2026-09-03

---

## 1. Overview & Context

To simplify onboarding for self-hosters and SaaS operations, the system should intelligently detect the AI provider based on API key prefixes and automatically apply production-grade defaults (such as resolving Google Gemini keys to `gemini-2.5-flash-lite`) without requiring manual URL overrides.

---

## 2. Technical Implementation

### 2.1 Pydantic Model Validator
- In `src/core/config.py`:
  - Added `@model_validator(mode="after")` `resolve_ai_defaults(self)` to `Settings`:
    - Keys starting with `AIzaSy` automatically set effective provider to `"gemini"`.
    - Keys starting with `gsk_` set effective provider to `"groq"`.
    - Keys starting with `sk-` set effective provider to `"openai"`.
  - For Gemini: automatically sets `AI_BASE_URL` to `https://generativelanguage.googleapis.com/v1beta/openai` (if unset or legacy) and defaults `AI_MODEL` and `AI_WHISPER_MODEL` to `gemini-2.5-flash-lite`.
  - Seamlessly migrates legacy configurations pointing to Groq or older models when switching API keys.

---

## 3. Verification & Acceptance

- Validated via `tests/unit/test_gemini_migration_and_prompts.py`.
- Verified auto-detection with `AIzaSy` keys and model resolution to `gemini-2.5-flash-lite`.
- Verified backward-compatibility with explicit provider overrides.
