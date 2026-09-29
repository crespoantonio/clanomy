# Story 19.2: Direct Native Audio Transcription

**Epic:** Epic 19 - Native Google Gemini Multimodal Provider & Direct Audio Engine
**Status:** Completed
**Author:** Amelia & Winston
**Date:** 2026-09-03

---

## 1. Overview & Context

Self-hosting users on budget VPS servers (<500MB RAM) or zero-GPU instances typically struggle to run local Faster-Whisper models. By leveraging Google Gemini's native multimodal audio ingestion capabilities, Clanomy can send incoming voice notes directly to Gemini for simultaneous transcription and financial transaction extraction, cutting total container RAM to <150MB and latency to <300ms.

---

## 2. Technical Implementation

### 2.1 Multimodal Ingestion Pipeline
- In `src/services/whisper_service.py` & `src/core/llm/providers/gemini_provider.py`:
  - Added support for passing raw audio bytes (base64-encoded `audio/ogg` or `audio/wav`) directly in Gemini `inline_data` content parts.
  - Formulates unified system instructions to transcribe speech and extract structured financial entries (`BatchTransactionExtractionResult`) in a single multimodal inference turn.
  - Eliminates intermediate temporary disk serialization when audio size is within safe bounds (<3MB).

### 2.2 Ingress Optimization
- Bypasses external Whisper container invocation when `AI_PROVIDER=gemini` and direct audio processing is enabled.
- Preserves audio validation guardrails (`MAX_VOICE_DURATION_SECONDS` = 35s, `MAX_AUDIO_SIZE_BYTES` = 3MB).

---

## 3. Verification & Acceptance

- Validated via `tests/unit/test_gemini_migration_and_prompts.py` and `tests/services/test_whisper_service.py`.
- Verified single-pass audio extraction on sample voice notes in English and Spanish.
- Confirmed zero orphaned audio files and low memory footprint.
