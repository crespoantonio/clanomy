# Story 22.2: Authorized Message Simulation Route

**Epic:** Epic 22 - Landing Page Web App, Simulation Endpoint & E2E LLM Evaluation Suite
**Status:** Completed
**Author:** Amelia & Murat
**Date:** 2026-09-03

---

## 1. Overview & Context

Testing end-to-end AI transaction extraction typically required sending live messages through Telegram webhooks. To facilitate automated regression testing, prompt optimization, and self-hoster verification without external network setup, Clanomy exposes an authorized `/simulate/message` endpoint.

---

## 2. Technical Implementation

### 2.1 Simulation Endpoint Architecture
- In `src/api/routes/simulate.py`:
  - Implemented `POST /simulate/message` accepting `SimulateMessageRequest` (`text`, `default_currency`, `model`).
  - Protected via `X-Simulation-Secret` header verified with constant-time comparison against `settings.SIMULATION_SECRET`.
  - Supports optional custom headers (`X-AI-Provider`, `X-AI-Api-Key`, `X-AI-Model`) to test alternate models on-the-fly.
  - Passes input to `ExtractionService` and `AIOrchestrator` to generate the exact structured JSON and formatted Telegram response without persisting fake records to the primary database.
  - Returns `SimulateMessageResponse` containing status, action, extracted items, provider name, and execution duration.

---

## 3. Verification & Acceptance

- Validated via `tests/unit/test_batch_extraction_and_undo.py` and direct curl integration tests.
- Verified constant-time rejection (HTTP 403) when secret is invalid or missing.
- Verified accurate JSON output matching production extraction logic.
