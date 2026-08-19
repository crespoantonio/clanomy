---
story_id: "7.4"
epic_id: "7"
title: "Payment Verification Webhook Handler"
status: "pending"
priority: "high"
---

# Story 7.4: Payment Verification Webhook Handler

## User Story
As a System,
I want to securely verify and process successful payments,
So that users are automatically granted their Pro tier.

## Acceptance Criteria
- [ ] Update `telegram_webhook` in `src/api/routes/telegram.py` to stop fast-exiting when `"message"` is not present, specifically to capture `pre_checkout_query`.
- [ ] Implement handler for `pre_checkout_query`. It MUST respond within 10 seconds via `answerPreCheckoutQuery` with `ok=True`.
- [ ] Implement handler for `successful_payment` (which arrives inside the `message` object).
- [ ] Extract the `invoice_payload` and validate it against a strict whitelist of paid SKUs (`sub_solo_pro` -> `"solo_pro"`, `sub_family_pro` -> `"family_pro"`).
- [ ] Reject or ignore any unauthorized payload (specifically ensuring `"lifetime_pro"` cannot be triggered via webhooks).
- [ ] Preserve existing `"lifetime_pro"` accounts from being downgraded/overwritten if an external webhook update is received.
- [ ] Update the user's `Family` record in the database: set `plan_type` to the purchased tier, `subscription_status` to `"active"`.
- [ ] Send a success/welcome message to the user acknowledging their upgrade.

## Technical Notes
- The webhook currently says:
  ```python
  if "message" not in payload:
      return {"status": "ok"}
  ```
  This must be changed to allow `"pre_checkout_query"` to be processed.
- Strict payload validation table:
  ```python
  ALLOWED_PAID_PLANS = {
      "sub_solo_pro": "solo_pro",
      "sub_family_pro": "family_pro",
  }
  ```
- Telegram uses the Bot API to confirm payments natively, so verifying the initial webhook secret and strict SKU whitelisting guarantees security.
