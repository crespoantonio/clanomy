---
story_id: "7.2"
epic_id: "7"
title: "Quota Gating & Upgrade Prompt"
status: "pending"
priority: "high"
---

# Story 7.2: Quota Gating & Upgrade Prompt

## User Story
As a Free User,
I want to be notified when I hit my 30-transaction limit,
So that I understand why my logs are blocked and how to upgrade.

## Acceptance Criteria
- [ ] In `MessagingService`, before processing a transaction, check the family's `plan_type` and `monthly_tx_count`.
- [ ] If `plan_type` is `"free"` and `monthly_tx_count` >= 30, block the transaction log.
- [ ] Return a friendly warning message via Telegram explaining the limit has been reached.
- [ ] The warning message must include instructions to type `/upgrade` to unlock the Pro tier.
- [ ] Ensure that active Pro users bypass this check.

## Technical Notes
- The check should happen early in the pipeline (likely before we send the audio/text to the AI orchestrator to save resources).
- Increment the `monthly_tx_count` on every successful transaction log.
