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

## Deferred from: code review of 8-1-database-schema-extension-for-transaction-types.md (2026-08-25)
- Dangerous Defaulting for Ambiguous Input: Architecture says ambiguous inputs default to expense rather than triggering fallback.
- Incomplete Mathematical Fallback: Savings rate formula has no definition for zero/negative income.

## Deferred from: code review of 8-3-income-voice-and-text-logging-orchestrator (2026-08-25)
* Brittle Test Mocks — mock_llm_responses relies on hardcoded substring checks (e.g. "salary"), which is fragile but pre-existing.

## Deferred from: code review of 8-4-conversational-net-cash-flow-queries (2026-08-25)
- Fragile Intent Hardcoding - AIOrchestrator uses inline lists for intent routing - deferred, pre-existing
- LLM Output Brittleness - Massive Literal for intent field - deferred, pre-existing
## Deferred from: code review of 7-1-database-schema-expansion-for-subscriptions.md (2026-08-26)
- Clunky Timezone Handling and Missing Tests: Timezone awareness is band-aided in domain logic and lacks test coverage.
- Missing Indexes for Background Jobs: plan_type and 	rial_ends_at lack indexes, causing full table scans for cron jobs.

## Deferred from: code review of 7-2-quota-gating-and-upgrade-prompt (2026-08-26)
- _is_query_or_command relies on naive string matching
- _is_query_or_command bypasses quota checks for anything flagged as a command

## Deferred from: code review of 7-3-telegram-stars-invoice-generation.md (2026-08-26)
- Destructive Ledger Alteration on Member Exit [src/services/family_service.py]
- Unbounded Invite Generation [src/services/family_service.py]
