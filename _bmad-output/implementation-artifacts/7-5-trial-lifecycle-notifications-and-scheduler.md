---
story_id: "7.5"
epic_id: "7"
title: "Proactive Trial Lifecycle Notifications Scheduler (Day 50 & Day 60)"
status: "ready-for-dev"
priority: "medium"
---

# Story 7.5: Proactive Trial Lifecycle Notifications Scheduler (Day 50 & Day 60)

Status: ready-for-dev

## User Story

As a User,  
I want to be proactively notified 10 days before my trial ends and when my trial completes,  
So that I understand my transition to the Free tier, know that my past data is safe, and have a clear option to subscribe.

## Acceptance Criteria

- [ ] Implement a daily trial notification task/service in `src/services/notification_scheduler.py`:
  - Queries active trial families where `trial_ends_at <= now() + 10 days` and `notified_day_50 == False`.
  - Queries expired trial families where `trial_ends_at <= now()` and `notified_day_60 == False` with no active paid plan.
- [ ] Format and send the **Day 50 Nudge Message**:
  - Summarizes value delivered (transactions tracked by family during the trial).
  - Warns that the 60-day trial will finish in 10 days.
  - Presents available tiers (**Family Pro** 300 Stars/mo, **Solo Pro** 150 Stars/mo) and `/upgrade` CTA.
  - Sets `Family.notified_day_50 = True`.
- [ ] Format and send the **Day 60 Transition Message**:
  - Automatically transitions `Family.plan_type` to `"free"`.
  - Reassures user that all historical data, past Ask queries, and Notion sync remain 100% safe and intact.
  - Clearly explains the Free tier limits: 30 transaction logs/month shared across the family workspace.
  - Provides a friendly `/upgrade` CTA.
  - Sets `Family.notified_day_60 = True`.
- [ ] Add unit and mock integration tests in `tests/services/test_notification_scheduler.py`.
