---
story_id: "12.4"
epic_id: "12"
title: "Atomic User & Family Provisioning Service"
status: "done"
priority: "high"
---

# Story 12.4: Atomic User & Family Provisioning Service

## User Story
As a Developer,
I want user registration and family workspace creation encapsulated in a dedicated service,
So that webhook controllers remain thin and registration edge cases are handled atomically.

## Acceptance Criteria
- [x] Create `MessagingService` in `src/services/messaging_service.py`.
- [x] Implement `get_or_create_user_and_family()` managing atomic creation of `User` and `Family` records.
- [x] Provision 60-day trial for new users (`has_used_trial=False`) and attach default workspace settings.
- [x] Synchronize updated Telegram user metadata (`username`, `full_name`) on existing user logins.
- [x] Test edge cases in `tests/unit/test_coverage_boost.py` (`test_messaging_service_edge_cases`).

## Tasks / Subtasks
- [x] **Service Implementation** (AC: 1, 2, 3, 4)
  - [x] Author `src/services/messaging_service.py`.
- [x] **Webhook Refactoring**
  - [x] Call `MessagingService` in `src/api/routes/telegram.py`.
- [x] **Testing** (AC: 5)
  - [x] Unit test user creation, family linking, and profile updates.
