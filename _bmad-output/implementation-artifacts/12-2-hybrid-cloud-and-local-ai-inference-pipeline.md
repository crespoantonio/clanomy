---
story_id: "12.2"
epic_id: "12"
title: "Hybrid Cloud & Local AI Inference Pipeline"
status: "done"
priority: "high"
---

# Story 12.2: Hybrid Cloud & Local AI Inference Pipeline

## User Story
As an Operator,
I want to configure either local Ollama or Groq Cloud AI inference seamlessly,
So that Clanomy can run on both self-hosted GPUs and lightweight VPS environments.

## Acceptance Criteria
- [x] Integrate Groq Cloud AI API client in `ExtractionService` and `WhisperService`.
- [x] Support configuration settings `GROQ_API_KEY`, `GROQ_MODEL`, and `GROQ_WHISPER_MODEL`.
- [x] Route requests to Groq Cloud when key is present, defaulting smoothly to local Ollama and Faster-Whisper when omitted.
- [x] Unit test both local and cloud invocation paths in `tests/unit/test_coverage_boost.py` (`test_cloud_ai_extraction_and_query`).

## Tasks / Subtasks
- [x] **Settings & Client** (AC: 1, 2)
  - [x] Add configuration parameters in `src/core/config.py`.
- [x] **Inference Routing** (AC: 3)
  - [x] Implement cloud dispatch in `src/services/extraction/service.py` and `src/services/whisper_service.py`.
- [x] **Testing** (AC: 4)
  - [x] Add mocked tests for cloud AI extraction and queries.
