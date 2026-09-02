# Story 14.4: 20-Log Free Tier Quota & Context-Aware Pro-Tips

**Epic:** Epic 14 - Pre-Built Fast-Path Commands & Hybrid Quota Model
**Status:** Completed
**Author:** Amelia & John
**Date:** 2026-09-01

---

## 1. Overview & Context

To keep cloud AI costs predictable while providing a generous free tier for users, Clanomy enforces a 20-operation/month quota on free-tier natural language AI interactions, while keeping all deterministic fast-path slash commands (`/month`, `/me`, `/today`, `/bills`, `/balance`, `/undo`, `/help`) 100% free and unlimited.

---

## 2. Technical Implementation

### 2.1 Quota Configuration
- In `src/core/subscription_config.py`:
  - `FREE_TIER_MONTHLY_LIMIT = 20`.

### 2.2 Quota Enforcement & Pro-Tip Appendage
- In `src/services/ai_orchestrator.py`:
  - Enforces `can_log_transaction()` checks before invoking AI transcription or extraction.
  - Appends contextual pro-tips on query responses:
    - Free tier: *"💡 Pro-tip: Type /month or /me anytime for an instant response that doesn't use your monthly AI quota!"*
    - Pro tier: *"💡 Pro-tip: Type /month or /me anytime for an instant response!"*

### 2.3 Status Reporting
- In `src/services/handlers/family_handler.py`:
  - `/family` displays `Monthly AI Logs: {used} / 20 (⚡ Commands are 100% free & unlimited)`.

---

## 3. Verification & Acceptance

- Validated via `tests/services/test_command_handlers.py` and `tests/services/test_render_groq_hardening.py`.
- Verified quota blocks natural text when limit reached while all slash commands remain fully functional.
