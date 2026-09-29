---
story_id: "7.2"
epic_id: "7"
title: "60-Day Trial Provisioning, Onboarding Welcome & Quota Gating"
status: "done"
priority: "high"
---

# Story 7.2: 60-Day Trial Provisioning, Onboarding Welcome & Quota Gating

Status: done

## User Story

As a User,  
I want to be greeted with a 60-day Family Pro trial upon starting the bot, receive clear onboarding as a creator or invited member, manage my family members as an admin, and have quota limits enforced fast before AI processing with automatic monthly resets,  
So that I experience the full capabilities of Clanomy upfront and understand my account and family lifecycle.

## Acceptance Criteria

- [x] **Creator Registration & Onboarding (`/start`)**:
  - When a new user registers via `/start`, if `user.has_used_trial == False`, provision their new family workspace with `plan_type="trial"`, `trial_ends_at = now() + 60 days`, and mark `user.has_used_trial = True`.
  - The `/start` welcome response explicitly explains all core features (voice logging, dual income/expense extraction, ASK cash flow queries, Notion mirror, family invites) and announces the **60-day Family Pro trial**.
- [x] **Invited Member Onboarding (`/start join_<token>`)**:
  - When a user joins via an invite link, the bot greets them with a tailored welcome message explaining that their logs will be shared with the family workspace and detailing how to leave the family anytime via `/leavefamily`.
- [x] **Anti-Abuse Sybil Defense**:
  - If a user who previously consumed a trial (`user.has_used_trial == True`) creates a new workspace or leaves a family, their space starts directly on `plan_type="free"` with a clear explanation that the trial was already consumed.
- [x] **Lazy Monthly Reset & Early Fast-Fail Quota Check in Webhook**:
  - In `src/api/routes/telegram.py` / `subscription_service.py`, automatically reset `monthly_tx_count = 0` on the first transaction of a new calendar month (comparing `family.last_reset_month` with current UTC `YYYY-MM`).
  - Check `can_log_transaction(family)` **before** downloading voice audio files or calling Whisper / Ollama AI services.
  - For Free tier workspaces (`plan_type="free"`), if `monthly_tx_count >= 30`:
    - If user is admin $\rightarrow$ immediately respond with friendly quota limit message prompting `/upgrade`.
    - If user is an invited member $\rightarrow$ respond explaining the family's 30-message limit has been reached and advising them to ask their admin to upgrade via `/upgrade`.
    - Halt execution in `< 5ms`.
  - Pro tiers (`"solo_pro"`, `"family_pro"`, `"lifetime_pro"`, and active `"trial"`) bypass quota checks.
- [x] **Family Management & Removal Commands**:
  - Implement `/family` command for the admin/creator listing all members in the workspace.
  - Implement `/removemember @username` (or member ID) for the family creator:
    - Detaches the member from the family into a new personal Free workspace.
    - Re-assigns the member's transactions (`Transaction.family_id = new_family.id WHERE user_id = member.id`) so the old admin can no longer query or access their expenses.
    - Sends a polite notification to the removed member informing them of their new personal workspace.
- [x] **Self-Service Leave Command (`/leavefamily`)**:
  - Allows any member to leave independently with full personal transaction portability into a new personal Free workspace.
- [x] Add unit and integration tests in `tests/api/test_telegram_webhook_core.py`, `tests/services/test_subscription_service.py`, and `tests/services/test_family_service.py`.

## Tasks / Subtasks

- [x] **Task 1: Trial Provisioning & Sybil Defense** (AC: 1, 3)
  - [x] Update `MessagingService.get_or_create_user_and_family` to provision 60-day trial for new users (`plan_type="trial"`, `trial_ends_at=now()+60d`, `has_used_trial=True`).
  - [x] Update `FamilyService.create_family` to check `user.has_used_trial` (provisions trial if False, free if True).
- [x] **Task 2: Family Management, Admin Identification & Member Removal** (AC: 5, 6)
  - [x] Implement `FamilyService.is_family_admin(family_id, user_id)` to identify the workspace admin/creator.
  - [x] Implement `FamilyService.remove_member(admin_user_id, target_identifier)` to detach member to personal workspace and migrate transactions.
  - [x] Implement `FamilyService.leave_family(user_id)` for self-service member departure with transaction portability.
  - [x] Update `FamilyService.get_family_info` to include admin status and plan metadata.
- [x] **Task 3: Onboarding Welcome Messages** (AC: 1, 2)
  - [x] Update `/start` welcome message in `telegram.py` explaining voice logging, dual tracking, cash flow queries, Notion sync, family invites, and 60-day trial.
  - [x] Update `/start join_<token>` invited member welcome message detailing shared logs and `/leavefamily` portability option.
- [x] **Task 4: Fast-Fail Quota Gating & Monthly Resets** (AC: 4)
  - [x] Add early quota check in `telegram.py` webhook (< 5ms) before downloading audio or invoking LLM/Whisper.
  - [x] Commit lazy monthly counter reset in webhook when month changes.
  - [x] Return tailored upgrade guidance for admin vs invited members on free limit breach.
  - [x] Increment `family.monthly_tx_count += 1` upon transaction persistence in `ai_orchestrator.py`.
- [x] **Task 5: Comprehensive Testing** (AC: 7)
  - [x] Author unit tests for quota limits and monthly reset in `tests/services/test_subscription_service.py`.
  - [x] Author family management, removal, leave, and anti-abuse tests in `tests/services/test_family_service.py`.
  - [x] Author onboarding and quota limit webhook tests in `tests/api/test_telegram_webhook_core.py` and `tests/api/test_telegram_webhook_family.py`.
  - [x] Run full regression test suite (221/221 tests passing).

## File List

- `src/services/messaging_service.py` (Modified)
- `src/services/family_service.py` (Modified)
- `src/services/query_service.py` (Modified)
- `src/services/ai_orchestrator.py` (Modified)
- `src/api/routes/telegram.py` (Modified)
- `tests/services/test_subscription_service.py` (Created)
- `tests/services/test_family_service.py` (Modified)
- `tests/services/test_messaging_service.py` (Modified)
- `tests/services/test_ai_orchestrator.py` (Modified)
- `tests/api/conftest.py` (Modified)
- `tests/api/test_telegram_webhook_core.py` (Modified)
- `tests/api/test_telegram_webhook_family.py` (Modified)

## Dev Agent Record

### Implementation Plan
1. Update `MessagingService` to provision 60-day Family Pro trials (`plan_type="trial"`, `trial_ends_at = now() + 60 days`) for new user registrations and set `has_used_trial = True`.
2. Update `FamilyService.create_family` to enforce Sybil defense: if `user.has_used_trial` is True, new workspaces start on `free`.
3. Implement `FamilyService.is_family_admin`, `remove_member`, and `leave_family` with full transaction portability (updating `Transaction.family_id`).
4. Update `/start` and `/start join_<token>` onboarding welcome messages in `telegram.py` and `FamilyService`.
5. Add early fast-fail quota check in `telegram.py` webhook with lazy monthly reset commit and admin vs member prompt branching.
6. Increment `family.monthly_tx_count` on transaction persistence in `AIOrchestrator._persist_transaction`.
7. Author comprehensive unit and integration tests across services and webhook routes.
8. Execute regression tests and verify 100% pass rate.

### Completion Notes
- ✅ Provisioned 60-day Family Pro trial on initial user registration and enforced Sybil defense preventing trial duplicate reuse.
- ✅ Implemented `/family`, `/removemember @username`, and `/leavefamily` with full transaction portability and isolated multi-tenant data ownership.
- ✅ Implemented early fast-fail quota gating (< 5ms) in Telegram webhook before Whisper/LLM audio processing, with zero-cron lazy monthly counter resets.
- ✅ Added tailored `/start` creator onboarding and invited member join welcome messages with `/leavefamily` portability guidance.
- ✅ 100% test pass rate across unit, DB, service, and API integration test suites (221/221 passing).

## Change Log

- **2026-08-26**: Implemented 60-day trial provisioning, rich creator & invited member onboarding, Sybil defense, early fast-fail quota check (<5ms), lazy monthly quota resets, and family management commands (`/family`, `/removemember`, `/leavefamily`). Added comprehensive test suites with 221 passing tests.

## Technical Notes

- **Lazy Reset & Early Webhook Interception Flow**:
  ```python
  # Reset monthly counter lazily if month changed
  current_month = datetime.now(timezone.utc).strftime("%Y-%m")
  if family.last_reset_month != current_month:
      family.monthly_tx_count = 0
      family.last_reset_month = current_month
      session.add(family)
      session.commit()

  # Check quota before downloading audio or invoking LLM
  if not can_log_transaction(family):
      await telegram_service.send_message(
          chat_id=chat_id,
          text="⛔ Monthly Free Limit Reached (30/30 logs)\n\nYour family has reached the 30 free transaction logs for this month. Type /upgrade to unlock unlimited logs for your household."
      )
      return {"status": "ok"}
  ```

### Review Findings
- [x] [Review][Decision] Identify Admin by created_at — Flawed if users leave/rejoin. Needs dedicated role column or handle collisions.
- [x] [Review][Decision] Personal Family created on leave/remove — Blindly creates new workspace instead of checking for existing personal space, leading to DB bloat.
- [x] [Review][Patch] Missing clear explanation of consumed trial on Sybil Defense triggers
- [x] [Review][Patch] Unrestricted access to /family command (does not check is_family_admin)
- [x] [Review][Patch] Quota limit race condition (can_log_transaction check vs monthly_tx_count increment)
- [x] [Review][Patch] Transaction migration loads every transaction into memory instead of bulk SQL update
- [x] [Review][Patch] Intent parsing logic in ai_orchestrator.py redundant code (/removemember)
- [x] [Review][Patch] remove_member fetches all members into Python memory instead of DB filtering
- [x] [Review][Patch] Standard imports inexplicably buried inside function in messaging_service.py
- [x] [Review][Patch] User without prior trial removed/leaves family gets trial without flag set properly
- [x] [Review][Patch] Admin runs /removemember None matches user with no telegram_id
- [x] [Review][Defer] _is_query_or_command relies on naive string matching — deferred, pre-existing
- [x] [Review][Defer] _is_query_or_command bypasses quota checks for anything flagged as a command — deferred, pre-existing
