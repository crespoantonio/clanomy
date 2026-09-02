# Story 18.1: Multi-Provider Whisper Speech-to-Text Engine

**Epic:** Epic 18 - Multi-Provider AI Inference Resilience, Prompt Caching & Speech-to-Text Fallbacks
**Status:** Completed
**Author:** Amelia & Winston
**Date:** 2026-09-02

---

## 1. Overview & Context

To support running on modest VPS servers (<500MB RAM) without local GPU overhead, as well as 100% offline local deployments, Clanomy provides a unified Speech-to-Text engine supporting local Faster-Whisper, Groq Cloud Whisper, and OpenAI Whisper.

---

## 2. Technical Implementation

### 2.1 Whisper Service Multi-Provider Architecture
- In `src/services/whisper_service.py`:
  - Defined `WhisperProvider` enum: `LOCAL`, `GROQ`, `OPENAI`.
  - Routes transcription based on `WHISPER_PROVIDER` setting.
  - For cloud providers, uses `AI_API_KEY` with Groq (`whisper-large-v3`) or OpenAI (`whisper-1`).
  - Enforces payload size validation (<25MB limit) and audio duration limits.
  - Implements secure temp file cleanup using `tempfile.NamedTemporaryFile` inside `try...finally` blocks.

---

## 3. Verification & Acceptance

- Validated via `tests/services/test_whisper_service.py`.
- Verified audio temp file deletion and multi-provider selection.
