---
story_id: "7.3"
epic_id: "7"
title: "Telegram Stars Auto-Renewing Invoice Generation (/upgrade)"
status: "ready-for-dev"
priority: "high"
---

# Story 7.3: Telegram Stars Auto-Renewing Invoice Generation (/upgrade)

Status: ready-for-dev

## User Story

As a User,  
I want to trigger an upgrade invoice directly in chat with auto-renewing billing,  
So that I can pay seamlessly using Telegram Stars (Apple/Google Pay) for my chosen tier.

## Acceptance Criteria

- [ ] Add `/upgrade` command handling in `src/api/routes/telegram.py` / `TelegramService`.
- [ ] Implement `send_subscription_invoice` using Telegram's `sendInvoice` Bot API:
  - Currency: `XTR` (Telegram Stars).
  - Auto-renewal: Set `subscription_period = 2592000` (30 days in seconds).
  - Payload identifier: `sub_solo_pro_{family_id}` or `sub_family_pro_{family_id}`.
- [ ] Support tier selection:
  - **Solo Pro** (150 Stars / month): Unlimited logs for 1 individual user.
  - **Family Pro** (300 Stars / month): Unlimited logs for up to 5 family members.
- [ ] If a Solo Pro subscriber attempts to generate an invite link via `/invite`, inform them that Family Pro is required to add family members.
- [ ] Add unit and mock integration tests in `tests/services/test_telegram_service.py` and `tests/api/test_telegram_webhook_core.py`.
