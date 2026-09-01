---
story_id: "11.3"
epic_id: "11"
title: "Prompt Injection Defense & Input Sanitization"
status: "done"
priority: "high"
---

# Story 11.3: Prompt Injection Defense & Input Sanitization

## User Story
As a Security Engineer,
I want untrusted inputs to be stripped of markdown formatting and isolated inside XML tags,
So that malicious prompts cannot break out of their instruction context.

## Acceptance Criteria
- [x] Create `sanitize_prompt_input()` in `src/core/ai_client.py` stripping markdown fences and control characters (SEC-03).
- [x] Enclose all user inputs inside explicit `<user_input>` XML tags in both Cloud AI and Ollama prompts.
- [x] Add anti-leakage defenses preventing disclosure of system prompts or API keys.
- [x] Add unit tests in `tests/services/test_security_audit_remediation.py` and `tests/unit/test_security_audit_hardening.py` verifying fence neutralizing.

## Tasks / Subtasks
- [x] **Sanitization Utility** (AC: 1)
  - [x] Implement `sanitize_prompt_input` in `src/core/ai_client.py`.
- [x] **Prompt Updates** (AC: 2, 3)
  - [x] Update prompts in `src/services/extraction/prompts.py` and `src/services/query/formatters.py`.
- [x] **Testing** (AC: 4)
  - [x] Test boundary escaping against malicious payloads.
