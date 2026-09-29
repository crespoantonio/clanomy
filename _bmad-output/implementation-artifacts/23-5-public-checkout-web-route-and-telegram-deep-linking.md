# Story 23.5: Public Checkout Web Route & Telegram Deep Linking

**Epic:** Epic 23 - Paddle Merchant of Record Billing Integration & Household Governance
**Status:** Completed
**Author:** Amelia & Sally
**Date:** 2026-09-11

---

## 1. Overview & Context

Users directed from Telegram or promotional landing pages need a dedicated web checkout interface (`/pay`) to complete Paddle transactions via overlay or inline checkout with a smooth return loop back to the Telegram bot.

---

## 2. Technical Implementation

### 2.1 Checkout Web Interface (`landing/pay.html`)
- Semantic dark-mode card interface featuring:
  - Paddle.js v2 SDK integration (`https://cdn.paddle.com/paddle/v2/paddle.js`).
  - Loading spinner, active checkout, success confirmation with deep link to `@ClanomyBot`, and paused/closed states with reopen actions.
  - Responsive design matching the master brand typography and tokens (`Inter`, `Outfit`).

### 2.2 FastAPI `/pay` Route & Gating
- In `src/main.py`:
  - Added `@app.get("/pay")` route.
  - Dynamically injects `PADDLE_CLIENT_SIDE_TOKEN`, `PADDLE_ENVIRONMENT`, and sanitized/escaped `BOT_USERNAME`.
  - Strictly gated behind `settings.ENABLE_SUBSCRIPTIONS`: returns HTTP 404 in self-hosted mode.
  - Whitelisted in `CLOUDFLARE_ORIGIN_EXEMPT_PATHS` to permit direct user access.

### 2.3 Telegram `/start` Deep Linking
- In `src/api/routes/telegram.py`:
  - Deep links formatted as `/start upgrade` or `/start upgrade_<tier>` automatically route directly to `billing_service.handle_upgrade_command`.

---

## 3. Verification & Acceptance

- Validated via `tests/api/test_telegram_webhook_core.py` (`test_webhook_start_upgrade_deep_link_routes_to_billing`).
- Verified HTTP 404 returned when `ENABLE_SUBSCRIPTIONS=false`.
