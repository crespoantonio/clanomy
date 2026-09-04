# Story 20.2: Paginated Currency Inline Keyboard

**Epic:** Epic 20 - Interactive Telegram Currency Selection & Callback Query Pipeline
**Status:** Completed
**Author:** Amelia & Sally
**Date:** 2026-09-04

---

## 1. Overview & Context

Previously, setting a family default currency required typing an exact 3-letter ISO 4217 code (e.g. `/currency ARS`). To make currency configuration effortless and mobile-friendly, Clanomy introduces a paginated interactive inline keyboard triggered by `/currency` without arguments, allowing users to browse and select currencies in one tap.

---

## 2. Technical Implementation

### 2.1 Currency Handler & Pagination Logic
- In `src/services/handlers/currency_handler.py`:
  - Maintained a curated registry of major world currencies with flags and full names (USD, EUR, ARS, GBP, BRL, MXN, CAD, AUD, CLP, COP, etc.).
  - Implemented pagination logic with dynamic `◀️ Prev` and `Next ▶️` navigation buttons.
  - Attached callback data in the format `curr_page_<page_index>` for navigation and `curr_set_<iso_code>` for selection.
  - On selection: updates `Family.default_currency` in PostgreSQL, confirms the update, and edits the message in place via `TelegramService.edit_message_text`.
  - Direct invocations with arguments (e.g. `/currency EUR`) remain available for power users as fast-path commands.

---

## 3. Verification & Acceptance

- Validated via `tests/unit/test_currency_interactive.py`.
- Verified forward and backward pagination through all currency pages.
- Confirmed database persistence of updated currency and atomic message editing.
