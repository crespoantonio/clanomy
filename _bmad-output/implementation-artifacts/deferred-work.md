# Deferred Work

## Open Items

### Deferred from: code review of 1-1-project-initialization-containerized-environment.md (2026-05-09)

- **Performance/Permission issues with Windows volume bind**: `volumes: - .:/app` on Windows can be slow or cause file lock issues in some Podman/Docker setups. This is a known environmental quirk for local development on Windows.

### Deferred from: code review of 1-3-multi-tenant-database-schema-sqlmodel.md (2026-05-09)

- **Lack of Alembic/Migrations**: `create_all` is used for dev but no migration strategy (Alembic) is introduced for production readiness.

---

## Resolved Items

### Resolved from: code review of 2-1-faster-whisper-transcription-service.md (2026-06-06)

- **Hardcoded transcription settings**: The parameters for transcription (e.g. beam_size=5) are hardcoded, preventing runtime custom configuration or tuning of transcription settings like temperature, VAD, or timestamp generation. *(Resolved: Added configuration variables in config.py and passed to whisper_service)*
- **Lack of concurrency limits**: Running CPU-bound transcription in threads using `asyncio.to_thread` without task queues or concurrent worker limits exposes the host system to CPU thrashing under concurrent load. *(Resolved: Added asyncio.Semaphore to whisper_service)*

### Resolved from: code review of 2-2-ollama-json-extraction-service.md (2026-06-06)

- **Missing LLM request retry/fallback mechanisms**: In case of transient connection timeouts or LLM hallucination failures, the service raises an immediate ExtractionError instead of utilizing automated request retry (with backoff) or attempting secondary local models. *(Resolved: Integrated tenacity retry with exponential backoff)*
- **Lack of secondary parsing fallback on Pydantic validation failure**: If Pydantic validation of the LLM response fails, the raw LLM output is discarded instead of attempting regex extraction or secondary prompts to recover the values. *(Resolved: Implemented fallback regex extractor on validation errors)*

### Resolved from: code review of 2-3-the-3-second-rule-orchestrator.md (2026-06-06)

- **Missing Concurrency Lock on WhisperModel Transcription**: Multiple concurrent voice notes might call `model.transcribe` concurrently on the singleton `WhisperModel` which is not thread-safe. *(Resolved: Added threading.Lock around model.transcribe in WhisperService)*
- **Resource Inefficiency: Single-use AsyncClient**: A new `httpx.AsyncClient` is created for every orchestration task instead of using a shared client. *(Resolved: Created HTTPClientManager singleton connection pool and refactored services)*

### Resolved from: code review of 2-4-transaction-persistence-with-encryption.md (2026-06-06)

- **Logging raw exception exposes potential database context details**: Logging raw `e` directly in `logger.error` might expose internal database error details if database connection parameters or SQL statement details are embedded in the exception object. *(Resolved: Sanitized exception logs in AIOrchestrator and AccountService)*
