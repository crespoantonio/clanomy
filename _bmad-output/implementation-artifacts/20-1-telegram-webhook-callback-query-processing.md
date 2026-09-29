# Story 20.1: Telegram Webhook Callback Query Processing

**Epic:** Epic 20 - Interactive Telegram Currency Selection & Callback Query Pipeline
**Status:** Completed
**Author:** Amelia & Winston
**Date:** 2026-09-04

---

## 1. Overview & Context

To support Telegram inline buttons (such as interactive currency pickers and selection menus), the Telegram webhook receiver must handle `callback_query` update payloads, acknowledge them via `answer_callback_query` to prevent Telegram loading spinners, and route the button events to appropriate service handlers.

---

## 2. Technical Implementation

### 2.1 Webhook Router Expansion
- In `src/api/routes/telegram.py`:
  - Updated webhook route to inspect incoming JSON for `callback_query`.
  - Extracted `callback_query.id`, `callback_query.data`, `callback_query.from`, and `callback_query.message`.
  - Enforced `X-Telegram-Bot-Api-Secret-Token` authentication for callback payloads.
  - Delegated callback handling to `CurrencyHandler` or relevant service based on data prefixes (`curr_page_`, `curr_set_`).

### 2.2 Telegram Service Methods
- In `src/services/telegram_service.py`:
  - Implemented `answer_callback_query(callback_query_id: str, text: Optional[str] = None)` sending `POST /answerCallbackQuery`.
  - Implemented `edit_message_text(chat_id: int, message_id: int, text: str, reply_markup: Optional[dict] = None)` sending `POST /editMessageText` to update inline keyboards in place without sending new messages.

---

## 3. Verification & Acceptance

- Validated via `tests/unit/test_currency_interactive.py` and `tests/api/test_telegram_webhook_core.py`.
- Verified callback acknowledgment executes in <100ms.
- Confirmed `allowed_updates` in webhook setup properly receives button callbacks.
