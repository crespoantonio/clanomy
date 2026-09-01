---
story_id: "11.4"
epic_id: "11"
title: "Concurrency Control & Resource Bounding"
status: "done"
priority: "high"
---

# Story 11.4: Concurrency Control & Resource Bounding

## User Story
As a System Administrator,
I want rapid sequential requests per user to be serialized and global AI calls to be throttled,
So that race conditions and server resource exhaustion are completely prevented.

## Acceptance Criteria
- [x] In `AIOrchestrator`, instantiate `_user_locks = defaultdict(asyncio.Lock)` serializing execution per `user_id` (SEC-04).
- [x] Define `GLOBAL_OLLAMA_SEMAPHORE` in `src/core/ai_client.py` using `settings.OLLAMA_MAX_CONCURRENT` (SEC-05).
- [x] Replace per-module semaphores in `ExtractionService` and `QueryService` with `GLOBAL_OLLAMA_SEMAPHORE`.
- [x] Cap in-memory transaction decryption queries at `MAX_QUERY_TRANSACTIONS_LIMIT: 500` (SEC-06).
- [x] Add automated unit tests in `tests/unit/test_security_audit_hardening.py` verifying user lock serialization and bounded limits.

## Tasks / Subtasks
- [x] **Per-User Lock** (AC: 1)
  - [x] Add user-level lock in `src/services/ai_orchestrator.py`.
- [x] **Global Semaphore & Config** (AC: 2, 3)
  - [x] Create `GLOBAL_OLLAMA_SEMAPHORE` in `src/core/ai_client.py`.
- [x] **Query Limit** (AC: 4)
  - [x] Apply limit on `_fetch_and_decrypt_transactions()` in `src/services/query/service.py`.
- [x] **Testing** (AC: 5)
  - [x] Unit test concurrent mutations and semaphore acquisition.
