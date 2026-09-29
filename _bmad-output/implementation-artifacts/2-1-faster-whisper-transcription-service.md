# Story 2.1: Faster-Whisper Transcription Service

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a User,
I want to log expenses via voice notes,
so that I can log expenses without typing.

## Acceptance Criteria

1. **Transcription Accuracy**: The `WhisperService` must transcribe speech to text with high accuracy.
2. **Flexible Input Handling**: The service must accept both a media URL (to download) and a raw binary stream/file-like object.
3. **Audio Validation & Error Handling**: The service must validate input audio payloads. Empty or corrupted files must raise a custom exception (e.g., `InferenceError` or `ValueError`) rather than failing silently or causing crashes.
4. **Temporary File Lifecycle**: Any temporary files created during download or transcription must be strictly cleaned up (deleted) under all execution paths (e.g., in a `finally` block).
5. **Non-Blocking Execution (Async Event Loop)**: Transcription is CPU-bound and must not block the FastAPI main event loop. It must run in a separate thread pool using `asyncio.to_thread`.
6. **Optional Language Configuration**: The service must accept an optional `language` parameter to optimize transcription accuracy and reduce processing time.
7. **3s Audit Logging**: The service must measure and log the execution time of the transcription process to audit the "3-second rule".
8. **Configurability**: Whisper settings (model size, device, compute type) must be configurable via environment variables and `src/core/config.py`.
9. **Unit Tests**: The implementation must include unit/integration tests with mocked inference to ensure correctness without requiring large model downloads in CI.

## Tasks / Subtasks

- [x] **Configuration Updates** (AC: 8)
  - [x] Add `WHISPER_MODEL_SIZE`, `WHISPER_DEVICE`, and `WHISPER_COMPUTE_TYPE` settings to `src/core/config.py` with safe defaults (e.g., `"base"`, `"cpu"`, `"int8"`).
  - [x] Update `.env.example` with the new environment variables.
- [x] **Whisper Service Implementation** (AC: 1, 2, 3, 4, 5, 6, 7, 8)
  - [x] Create `src/services/whisper_service.py`.
  - [x] Implement thread-safe lazy-initialization (singleton pattern) of `WhisperModel` using configured settings so the model is not re-loaded on every request.
  - [x] Implement `transcribe` function accepting `audio_url: Optional[str] = None`, `audio_bytes: Optional[bytes] = None`, and `language: Optional[str] = None`.
  - [x] Add input validation to ensure either `audio_url` or `audio_bytes` is provided and is not empty.
  - [x] Implement audio downloading via `httpx.AsyncClient` if `audio_url` is provided.
  - [x] Implement temporary file handling with automatic cleanup (using a `try...finally` block) to store and process the media safely.
  - [x] Wrap the CPU-bound inference in `asyncio.to_thread`.
  - [x] Measure execution time and log it under the "[3s Audit]" prefix with details (duration, model, device).
- [x] **Testing Suite** (AC: 9)
  - [x] Create `tests/services/test_whisper_service.py`.
  - [x] Test download behavior with mocked HTTP responses.
  - [x] Test validation logic (e.g., empty bytes payload).
  - [x] Test cleanup behavior to verify temporary files are deleted after execution.
  - [x] Test transcription using a mocked `WhisperModel` to verify successful path and audit logging.

### Review Findings

- [x] [Review][Decision] 3s Audit Timing coverage — Resolved: Logged both separately. [src/services/whisper_service.py]
- [x] [Review][Patch] Lazy initialization of WhisperModel blocks FastAPI event loop [src/services/whisper_service.py:97]
- [x] [Review][Patch] Temporary file leak on write/flush exception [src/services/whisper_service.py:90-95]
- [x] [Review][Patch] HTTP download from remote server lacks timeout [src/services/whisper_service.py:73-77]
- [x] [Review][Patch] Lack of configuration validation on Whisper settings [src/core/config.py:19-22]
- [x] [Review][Patch] Missing support for raw binary streams or file-like objects (AC 2) [src/services/whisper_service.py:55]
- [x] [Review][Patch] Whisper instantiation failure not cached [src/services/whisper_service.py:30-50]
- [x] [Review][Patch] Ambiguous input parameters override silently [src/services/whisper_service.py:66-71]
- [x] [Review][Patch] Download payload size check missing [src/services/whisper_service.py:73-81]
- [x] [Review][Patch] Brittle default settings assertions in unit tests [tests/core/test_config.py:3-7]
- [x] [Review][Patch] Unit tests mutate global singleton state of WhisperService [tests/services/test_whisper_service.py]
- [x] [Review][Defer] Hardcoded transcription settings (e.g. beam_size=5) [src/services/whisper_service.py:105] — deferred, pre-existing
- [x] [Review][Defer] Lack of concurrency limits on thread pool executions [src/services/whisper_service.py:109] — deferred, pre-existing

## Dev Notes

- **Model Loading Pattern**: `WhisperModel` loading is slow and memory-intensive. It MUST be loaded as a singleton or lazily on first request. Ensure initialization is thread-safe using a lock if needed to prevent concurrent incoming webhooks from initializing multiple instances.
- **Temporary Files & Cleanup**: Since Telegram and WhatsApp use `.ogg` (Opus) and `.m4a` / `.mp4`, PyAV under the hood needs to decode them. To avoid issues with PyAV read buffers, write downloaded bytes or input bytes to a temporary file using `tempfile.NamedTemporaryFile` and pass the file path to `WhisperModel.transcribe`. Ensure the file is deleted in a `finally` block to prevent disk leaks.
- **Prevent Event Loop Starvation**: Transcription is CPU-bound. If called directly, it blocks FastAPI's event loop, causing requests to hang. Run the transcription execution block using `asyncio.to_thread` or standard pool execution.
- **3s Audit Logging format**: Use standard Python logger to log in format: `[3s Audit] Whisper transcription took X.XX seconds (model: {model_size}, device: {device})`.

### Project Structure Notes

- **Service Location**: `src/services/whisper_service.py` is the service file.
- **Config Location**: `src/core/config.py` holds settings class.
- **Tests Location**: `tests/services/test_whisper_service.py`.

### References

- [Architecture: Inference Engine](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/architecture.md#L100)
- [Architecture: Project Directory Structure](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/architecture.md#L196)
- [Epics: Story 2.1](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/epics.md#L168)
- [PRD: Latency & Local Processing](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/prd.md#L121)

## Dev Agent Record

### Agent Model Used

Gemini 3.5 Flash (High)

### Debug Log References

- None (all local test runs completed successfully)

### Completion Notes List

- Implemented `WhisperService` with thread-safe lazy-loading of `WhisperModel` to protect memory/performance.
- Implemented `transcribe` function supporting both direct URL download (via `httpx.AsyncClient`) and binary bytes buffer.
- Added input validation for missing or empty payloads.
- Implemented robust NamedTemporaryFile writing and cleanup (in `finally` block) to ensure zero disk leaks.
- Wrapped CPU-bound Whisper calculations in `asyncio.to_thread` to prevent event loop starvation.
- Added support for optional `language` parameter to focus search space and save execution time.
- Integrated timing logs for the "[3s Audit]" metrics.
- Added 6 unit tests in `tests/services/test_whisper_service.py` verifying all success paths, validation logic, and cleanup mechanisms.
- Verified 100% success on all 22 tests in the repository.

### File List

- `src/core/config.py`
- `.env.example`
- `src/services/whisper_service.py`
- `tests/core/test_config.py`
- `tests/services/test_whisper_service.py`

