---
story_id: "11.2"
epic_id: "11"
title: "Telegram Message Escaping & Delivery Resilience"
status: "done"
priority: "high"
---

# Story 11.2: Telegram Message Escaping & Delivery Resilience

## User Story
As a Developer,
I want outbound Telegram HTML messages to be sanitized and backed by automatic plain-text retry,
So that invalid entities never result in silent message delivery failures.

## Acceptance Criteria
- [x] Apply `html.escape()` to all dynamic user-provided strings in `AIOrchestrator` responses (SEC-02).
- [x] In `TelegramService.send_message()`, catch `httpx.HTTPStatusError` (status 400 + entity parse errors).
- [x] Automatically retry failed HTML messages in safe plain-text mode (`parse_mode=None`).
- [x] Add automated unit tests in `tests/unit/test_security_audit_hardening.py` (`test_sec02_telegram_service_parse_error_fallback` and `test_sec02_html_escaping_in_orchestrator`).

## Tasks / Subtasks
- [x] **HTML Sanitization** (AC: 1)
  - [x] Sanitize concept, category, and names in `src/services/ai_orchestrator.py`.
- [x] **TelegramService Retry Catch** (AC: 2, 3)
  - [x] Implement error handling and plain-text fallback in `src/services/telegram_service.py`.
- [x] **Automated Testing** (AC: 4)
  - [x] Verify fallback behavior on malformed tags.
