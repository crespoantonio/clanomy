---
story_id: "7.3"
epic_id: "7"
title: "Telegram Stars Invoice Generation"
status: "pending"
priority: "high"
---

# Story 7.3: Telegram Stars Invoice Generation

## User Story
As a User,
I want to trigger an upgrade invoice directly in chat,
So that I can pay seamlessly using Telegram Stars (Apple/Google Pay).

## Acceptance Criteria
- [ ] Add support for the `/upgrade` command in `src/api/routes/telegram.py` webhook router.
- [ ] Implement `send_subscription_invoice` logic (likely in `TelegramService`).
- [ ] When `/upgrade` is received, send the Telegram invoice payload using the Telegram `sendInvoice` API.
- [ ] Currency must be `XTR` (Telegram Stars).
- [ ] Include two options/buttons or separate invoices for:
  - Solo Pro (150 Stars)
  - Family Pro (300 Stars)
- [ ] The `payload` field in the invoice should uniquely identify the user and the plan (e.g., `sub_solo_pro_{chat_id}`).

## Technical Notes
- We may need an inline keyboard to let them pick between Solo Pro and Family Pro before sending the invoice, or just send two invoices directly.
- The `sendInvoice` API requires specific fields: `title`, `description`, `payload`, `currency`, and `prices`.
