---
story_id: "11.5"
epic_id: "11"
title: "Origin Shielding, Security Headers & Rate Limiting"
status: "done"
priority: "high"
---

# Story 11.5: Origin Shielding, Security Headers & Rate Limiting

## User Story
As an Operations Engineer,
I want webhook traffic to be verified against Cloudflare Origin Shield and protected by security headers,
So that untrusted network traffic is rejected at the HTTP boundary.

## Acceptance Criteria
- [x] Implement Cloudflare Origin Shield verification middleware in `src/main.py` and `src/core/security.py`.
- [x] Add enterprise security headers (`Strict-Transport-Security`, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`) to all HTTP responses.
- [x] Implement rate limiting / spam throttling on `/api/v1/telegram/webhook`.
- [x] Verify secret token header (`X-Telegram-Bot-Api-Secret-Token`) for every incoming webhook payload.
- [x] Automated tests in `tests/services/test_security_audit_remediation.py` verifying rate limiting and security headers.

## Tasks / Subtasks
- [x] **FastAPI Middleware** (AC: 1, 2)
  - [x] Add origin shield check and security headers in `src/main.py`.
- [x] **Rate Limiting** (AC: 3, 4)
  - [x] Implement spam throttling in webhook route `src/api/routes/telegram.py`.
- [x] **Testing** (AC: 5)
  - [x] Integration tests verifying rejection of unauthorized origins.
