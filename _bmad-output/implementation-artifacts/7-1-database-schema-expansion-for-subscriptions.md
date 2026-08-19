---
story_id: "7.1"
epic_id: "7"
title: "Database Schema Expansion for Subscriptions"
status: "pending"
priority: "high"
---

# Story 7.1: Database Schema Expansion for Subscriptions

## User Story
As a Developer,
I want to expand the `Family` table to support subscription tracking,
So that we can manage quotas and active Pro plans.

## Acceptance Criteria
- [ ] Update `src/db/models.py`
- [ ] Add `plan_type` field (default "free") to the `Family` model (allowed values: `"free"`, `"solo_pro"`, `"family_pro"`, `"lifetime_pro"`).
- [ ] Add `subscription_status` field (default "active") to the `Family` model.
- [ ] Add `monthly_tx_count` field (default 0) to the `Family` model.
- [ ] Add `current_period_end` (optional datetime) and `telegram_payment_charge_id` (optional str) to `Family` model.
- [ ] Ensure that Alembic migrations or SQLModel schema generation successfully apply these changes.
- [ ] Explicitly enforce security rule: `lifetime_pro` is reserved exclusively for direct database administration and MUST NOT be exposed via user commands, LLM tools, or webhook activations.

## Technical Notes
- The supported values for `plan_type` are:
  - `"free"`: Default tier, limited to 30 transactions/month per family.
  - `"solo_pro"`: Paid tier for individual users, unlimited transactions.
  - `"family_pro"`: Paid tier for families (all members of the family inherit unlimited access).
  - `"lifetime_pro"`: VIP / Friends & Family lifetime access. Inherits all `family_pro` capabilities with no expiration date (`current_period_end = NULL`), bypasses quota limits.
- **Security & Integrity Rule:**
  - `lifetime_pro` can ONLY be configured via direct database update.
  - Webhooks and bot endpoints must never accept or assign `lifetime_pro`.
- **SQL Administration Template:**
  ```sql
  UPDATE family
  SET plan_type = 'lifetime_pro',
      subscription_status = 'active',
      current_period_end = NULL
  WHERE id = (
      SELECT family_id 
      FROM "user" 
      WHERE telegram_id = <TARGET_TELEGRAM_ID>
  );
  ```
- Ensure backwards compatibility with existing records (defaulting to "free" and 0 monthly transactions).
