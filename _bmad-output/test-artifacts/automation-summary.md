---
stepsCompleted:
  - step-01-preflight-and-context
  - step-02-identify-targets
  - step-03c-aggregate
  - step-04-production-suite-expansion
lastStep: 'step-04-production-suite-expansion'
lastSaved: '2026-09-01'
inputDocuments:
  - 'docs/manual-testing-guide.md'
  - 'tests/postman/Clanomy_Postman_Collection.json'
  - 'tests/'
---

# Step 1: Preflight & Context Loading

## Stack Detection & Verify Framework
- **Detected Stack**: `backend` (Python/Pytest)
- **Framework Status**: Verified (`tests/` directory, `.pytest_cache`, and automated GitHub Actions CI exist)

## Execution Mode
- **Mode**: Automated Continuous Integration & Local Verification Harness

## Load Context
- Loaded `config.yaml`
- Expanded test structure in `tests/` across `api/`, `db/`, `services/`, and `unit/` directories.
- Core Knowledge Fragments Applied: `test-levels-framework.md`, `test-priorities-matrix.md`, `data-factories.md`, `selective-testing.md`, `ci-burn-in.md`, `test-quality.md`.

All preflight checks pass.

# Step 2: Identify Automation Targets & Test Mapping

The test suite maps 100% of functional requirements (FR1-FR35) and non-functional requirements (NFR1-NFR13) across the testing pyramid:
- Unit tests: Data models, encryption, prompt sanitization, normalization, and date resolvers.
- Service tests: Orchestrator, extraction engine, query engine, scheduled bills, subscription lifecycles, and Notion mirroring.
- API/Webhook tests: Telegram webhook ingestion, Cloudflare Origin Shielding, payment webhooks, and rate limiting.
- Security & Hardening audit tests: SEC-01 through SEC-06 forensic audit remediations.

# Step 3: Production Automated Test Suite Metrics

## Output Summary
✅ Comprehensive Test Suite Verified (347 Automated Tests)

📊 Current Summary (as of 2026-09-01):
- **Stack Type**: backend (Python / Pytest / FastAPI / SQLModel / AsyncIO)
- **Total Passing Tests**: **347** (100% pass rate)
- **Code Coverage**: Enforced at **≥ 85%** via CI gate (`.github/workflows/test.yml`)
- **Execution Speed**: ~1.10s collection time, high-speed execution with mocked external dependencies.

### Detailed Test Inventory:

#### 1. API & Webhook Layer (`tests/api/`)
- `tests/api/test_telegram_webhook_core.py`: Webhook secret verification, registration, voice note handling, text logs.
- `tests/api/test_telegram_webhook_queries.py`: Natural language query endpoints, conversational summaries.
- `tests/api/test_telegram_webhook_family.py`: Family group creation, invite links, member join flows.
- `tests/api/test_telegram_webhook_notion.py`: Notion connection, database selection, manual sync.
- `tests/api/test_telegram_webhook_payment.py`: Pre-checkout queries, successful Telegram Stars payment events.
- `tests/api/conftest.py`: Shared FastAPI TestClient, mocked Telegram bot and database fixtures.

#### 2. Database Models & Schema Layer (`tests/db/`)
- `tests/db/test_models.py`: SQLModel CRUD, AES-256 encrypted fields, cascade delete invariants, multi-tenant isolation.

#### 3. Core Services Layer (`tests/services/`)
- `tests/services/test_account_service.py`: GDPR account deletion and data scrubbing.
- `tests/services/test_ai_orchestrator.py`: End-to-end 3s orchestrator loop, per-user async locking, intent routing.
- `tests/services/test_corrections_and_undo.py`: Conversational transaction correction and undo capabilities.
- `tests/services/test_export_service.py`: GDPR data portability (CSV/JSON generation, temp file cleanup).
- `tests/services/test_extraction_service.py`: Dual-intent extraction (expense vs income), Spanish/English NLP, dynamic default currencies, regex fallback engine.
- `tests/services/test_family_service.py`: Family member management, invites, currency configuration (`/currency`).
- `tests/services/test_notification_scheduler.py`: 50-day and 60-day trial lifecycle scheduler execution.
- `tests/services/test_notion_service.py`: Real-time log mirroring, retry with exponential backoff.
- `tests/services/test_query_service.py`: Natural language date range resolution, time aggregations, category filters, multi-currency segregation, empty-state localization, net cash flow.
- `tests/services/test_scheduled_bills.py`: Scheduled bill models, batch NLP extraction, conversational zero-amount settlement (*"Pagué la visa"*), proactive due alerts.
- `tests/services/test_security_audit_remediation.py`: Prompt injection sanitization, rate limiting, anti-leakage defenses, thread safety.
- `tests/services/test_subscription_service.py`: Quota gating (30-message Free limit), Telegram Stars invoice generation, payment lifecycle, lifetime Pro protection.
- `tests/services/test_telegram_service.py`: HTML entity sanitization, plain-text delivery fallback on 400 error.
- `tests/services/test_whisper_service.py`: Faster-Whisper audio transcription, Groq Cloud Whisper integration.

#### 4. Unit & Security Audit Suites (`tests/unit/`)
- `tests/unit/test_security_audit_hardening.py`: SEC-01 tenant isolation on leave, SEC-02 HTML fallback, SEC-03 prompt boundary sanitization, SEC-04 user concurrency lock, SEC-05 global semaphore, SEC-06 bounded query decryption.
- `tests/unit/test_coverage_boost.py`: Edge cases across normalizers, date resolvers, messaging service, and cloud inference.
- `tests/unit/test_subscription_schema.py`: Subscription model invariants and monthly quota resets.

# Step 4: Quality Guardrails & CI/CD Pipeline

- **GitHub Actions Test Pipeline (`.github/workflows/test.yml`)**:
  - Runs automatically on every push and pull request targeting `master`.
  - Executes entire 347-test suite in an isolated environment.
  - Fails build if test coverage drops below 85%.
- **PR Guardrail Workflow (`.github/workflows/pr-guardrail.yml`)**:
  - Guards critical monetization, configuration, and workflow files against unauthorized modification.
