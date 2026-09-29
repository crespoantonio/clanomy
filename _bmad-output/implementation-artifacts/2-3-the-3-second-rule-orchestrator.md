# Story 2.3: The "3-Second Rule" Orchestrator

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a User,
I want to receive an immediate confirmation of my log,
so that I don't have to wait for the bot to finish processing.

## Acceptance Criteria

1. **Webhook Payload Extension**: The webhook payload received by the FastAPI `/api/v1/messages` endpoint must be extended to support an optional `audio_url` field in `MessagePayload` (representing the voice note URL from the messaging platform).
2. **Immediate API Response**: For any transaction logging request (i.e. message text is not `/start`), the endpoint must immediately enqueue the AI orchestration pipeline in FastAPI's `BackgroundTasks` queue and return a `200 OK` response with `{"status": "processing"}` to n8n within milliseconds.
3. **Synchronous Welcome Route Preservation**: The `/start` command response must remain synchronous (returning the welcome text directly in the API response), as implemented in Story 1.4.
4. **AI Orchestrator Pipeline Flow**: A new service class `AIOrchestrator` must coordinate the end-to-end processing pipeline in the background:
   - **Audio Processing**: If `audio_url` is provided, invoke `WhisperService().transcribe(audio_url=audio_url)`. If transcription fails or is empty, log the error and trigger an error callback to n8n.
   - **Data Extraction**: If `text` is provided (or successfully transcribed from audio), invoke `ExtractionService().extract(text=text)` to extract transaction details (`amount`, `category`, `concept`, `currency`).
   - **n8n Callback Execution**: Regardless of whether processing succeeds or fails, invoke the callback webhook in n8n with the final response.
5. **n8n Callback Integration**: The callback HTTP POST request must be sent asynchronously to `N8N_CALLBACK_URL` and include:
   - Header `X-FamFin-Token` matching `MESSAGING_WEBHOOK_SECRET` for secure authentication.
   - JSON payload structure:
     ```json
     {
       "chat_id": 12345,
       "user_id": "user-uuid-string",
       "status": "success" | "error",
       "text": "User-friendly confirmation or error message",
       "extracted_data": {
         "amount": 15.0,
         "category": "Food/Drink",
         "concept": "Starbucks",
         "currency": "USD"
       } | null
     }
     ```
6. **Robust Error & Timeout Handling**: The orchestrator must handle service exceptions (transcription failures, extraction timeouts, network failures on callback) gracefully, log details, and send an appropriate error/clarification callback to the user instead of failing silently.
7. **3s Audit Logging**: The service must measure and log the total execution duration under the `[3s Audit]` prefix (e.g., `[3s Audit] Total pipeline orchestration took X.XX seconds (user_id: {user_id}, text: '{text}')`).
8. **Configurability**: Define `N8N_CALLBACK_URL` in `src/core/config.py` with standard Pydantic URL validation, defaulting to `http://localhost:5678/webhook/famfin-callback`. Update `.env.example` accordingly.
9. **Unit & Integration Testing**: Include comprehensive unit tests mocking external API calls (Ollama, Whisper, httpx.AsyncClient) to verify all execution branches (text success, audio success, transcription failure, extraction timeout, callback failure).

## Tasks / Subtasks

- [x] **Configuration Updates** (AC: 8)
  - [x] Add `N8N_CALLBACK_URL` setting to `src/core/config.py`.
  - [x] Add Pydantic field validators to ensure `N8N_CALLBACK_URL` starts with `http://` or `https://` and has a valid host.
  - [x] Update `.env.example` with the new environment variable.
- [x] **API Endpoint Update** (AC: 1, 2, 3)
  - [x] Update `MessagePayload` schema in `src/api/routes/messages.py` to include `audio_url: Optional[str] = None`.
  - [x] Inject FastAPI's `BackgroundTasks` into the `receive_message` route.
  - [x] For non-`/start` messages, trigger `AIOrchestrator().orchestrate` in background tasks.
  - [x] Return `{"status": "processing"}` with a `200 OK` response.
- [x] **AI Orchestrator Implementation** (AC: 4, 5, 6, 7, 8)
  - [x] Create `src/services/ai_orchestrator.py` containing the `AIOrchestrator` singleton class.
  - [x] Implement `orchestrate` method accepting the `User` object, `text: Optional[str]`, `audio_url: Optional[str]`, and `chat_id: int`.
  - [x] Instantiate `WhisperService` and `ExtractionService` dynamically.
  - [x] Measure total processing time from start to completion.
  - [x] Construct friendly confirmation texts:
    - Success: `f"Saved {result.amount} {result.currency} for '{result.concept}' under category '{result.category}'."` (Note: database persistence will be implemented in Story 2.4; mock or skip DB write in this story).
    - Error/Failure: Clear message requesting clarification or indicating what failed.
  - [x] Implement async HTTP POST using `httpx.AsyncClient` targeting `N8N_CALLBACK_URL` with `X-FamFin-Token` header.
  - [x] Log performance metric under the format: `[3s Audit] Total pipeline orchestration took X.XX seconds (user_id: {user_id}, text: '{text}')`.
- [x] **Testing Suite** (AC: 9)
  - [x] Create `tests/services/test_ai_orchestrator.py` to test all logical flows.
  - [x] Mock `WhisperService.transcribe` and `ExtractionService.extract` responses.
  - [x] Mock the HTTP POST callback to `N8N_CALLBACK_URL` using `pytest-mock` or `unittest.mock`.
  - [x] Update `tests/api/test_messaging.py` to assert that background task is enqueued and API returns `{"status": "processing"}` for logging attempts.

### Review Findings

- [x] [Review][Decision] Logical Overwriting of Text Input by Audio Note — If a payload contains both 'text' and 'audio_url', the orchestrator will overwrite the original 'text' input with the transcribed text, or ignore it if transcription fails. We need to decide on the precedence or merge behavior.
- [x] [Review][Patch] Unawaited Async Whisper Call [src/services/ai_orchestrator.py:23]
- [x] [Review][Patch] Unpacked Transcription Return Tuple [src/services/ai_orchestrator.py:23]
- [x] [Review][Patch] DetachedInstanceError Risk in Background Task [src/api/routes/messages.py:65]
- [x] [Review][Patch] Flawed Whisper Mock in Orchestrator Tests [tests/services/test_ai_orchestrator.py:68]
- [x] [Review][Patch] Mock descriptor binding issue in tests [tests/services/test_ai_orchestrator.py:44]
- [x] [Review][Patch] Silent n8n Callback Failures [src/services/ai_orchestrator.py:64]
- [x] [Review][Patch] Unused Imports in Orchestrator Tests [tests/services/test_ai_orchestrator.py:2]
- [x] [Review][Patch] PEP 8 Violation: Mid-file Imports [tests/core/test_config.py:12]
- [x] [Review][Patch] Missing Branch Coverage in Orchestrator Tests [tests/services/test_ai_orchestrator.py:101]
- [x] [Review][Defer] Missing Concurrency Lock on WhisperModel Transcription [src/services/whisper_service.py:128] — deferred, pre-existing
- [x] [Review][Defer] Resource Inefficiency: Single-use AsyncClient [src/services/ai_orchestrator.py:63] — deferred, pre-existing

## Dev Notes

- **Background Tasks Pattern**: Use FastAPI's `BackgroundTasks` which runs tasks after returning the response. This is built-in and sufficient for Phase 1. Do not introduce Celery or external queues as they are deferred to Phase 2.
- **Client Reuse**: For the HTTP callback, use `httpx.AsyncClient` inside a context manager or share a client to optimize connections.
- **Whisper & Ollama Services**: Since these are singletons, import them and call `WhisperService()` / `ExtractionService()` respectively.
- **3s Audit Logging format**: Log with `[3s Audit]` prefix: `[3s Audit] Total pipeline orchestration took X.XX seconds (user_id: {user_id}, text: '{text}')`.
- **Database Association**: The background task should have access to the user's details (`user.id`, `user.family_id`) passed from the route.
- **Error Response Resilience**: If transcription or extraction fails, the orchestrator should still attempt to send a callback to n8n with `status: "error"` and the error details so n8n can message the user.

### Project Structure Notes

- **Orchestrator Location**: `src/services/ai_orchestrator.py`
- **Route Location**: `src/api/routes/messages.py`
- **Config Location**: `src/core/config.py`
- **Tests Location**: `tests/services/test_ai_orchestrator.py`

### References

- [Architecture: API & Communication Patterns](file:///C:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/architecture.md#L125)
- [Architecture: Project Directory Structure](file:///C:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/architecture.md#L196)
- [Epics: Story 2.3](file:///C:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/epics.md#L194)
- [PRD: The 3-Second Rule](file:///C:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/prd.md#L41)

## Dev Agent Record

### Agent Model Used

Gemini 3.5 Flash (High)

### Debug Log References

None

### Completion Notes List

- Implemented `N8N_CALLBACK_URL` configuration and validation in `src/core/config.py`.
- Updated webhook endpoint to accept `audio_url` and use `BackgroundTasks`.
- Created `AIOrchestrator` to handle transaction logic and invoke extraction and whisper services asynchronously.
- Implemented `httpx.AsyncClient` callback logic to send response to n8n webhook.
- Added comprehensive unit tests for new configuration, webhook route modifications, and `AIOrchestrator` flow logic.

### File List

- `src/core/config.py`
- `.env.example`
- `src/api/routes/messages.py`
- `src/services/ai_orchestrator.py` (New)
- `tests/core/test_config.py`
- `tests/api/test_messaging.py`
- `tests/services/test_ai_orchestrator.py` (New)
