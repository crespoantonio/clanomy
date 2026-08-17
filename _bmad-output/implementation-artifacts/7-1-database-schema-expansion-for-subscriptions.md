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
- [ ] Add `plan_type` field (default "free") to the `Family` model.
- [ ] Add `subscription_status` field (default "active") to the `Family` model.
- [ ] Add `monthly_tx_count` field (default 0) to the `Family` model.
- [ ] Ensure that Alembic migrations or SQLModel schema generation successfully apply these changes.

## Technical Notes
- The possible values for `plan_type` are `"free"`, `"solo_pro"`, and `"family_pro"`.
- We will need to reset `monthly_tx_count` periodically, but for this story, just adding the fields is enough.
- Ensure backwards compatibility with existing records (they should default to "free" and 0).
