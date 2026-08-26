---
story_id: "7.2"
epic_id: "7"
title: "60-Day Trial Provisioning, Onboarding Welcome & Quota Gating"
status: "ready-for-dev"
priority: "high"
---

# Story 7.2: 60-Day Trial Provisioning, Onboarding Welcome & Quota Gating

Status: ready-for-dev

## User Story

As a User,  
I want to be greeted with a 60-day Family Pro trial upon starting the bot, receive clear onboarding as a creator or invited member, manage my family members as an admin, and have quota limits enforced fast before AI processing with automatic monthly resets,  
So that I experience the full capabilities of Clanomy upfront and understand my account and family lifecycle.

## Acceptance Criteria

- [ ] **Creator Registration & Onboarding (`/start`)**:
  - When a new user registers via `/start`, if `user.has_used_trial == False`, provision their new family workspace with `plan_type="trial"`, `trial_ends_at = now() + 60 days`, and mark `user.has_used_trial = True`.
  - The `/start` welcome response explicitly explains all core features (voice logging, dual income/expense extraction, ASK cash flow queries, Notion mirror, family invites) and announces the **60-day Family Pro trial**.
- [ ] **Invited Member Onboarding (`/start join_<token>`)**:
  - When a user joins via an invite link, the bot greets them with a tailored welcome message explaining that their logs will be shared with the family workspace and detailing how to leave the family anytime via `/leavefamily`.
- [ ] **Anti-Abuse Sybil Defense**:
  - If a user who previously consumed a trial (`user.has_used_trial == True`) creates a new workspace or leaves a family, their space starts directly on `plan_type="free"` with a clear explanation that the trial was already consumed.
- [ ] **Lazy Monthly Reset & Early Fast-Fail Quota Check in Webhook**:
  - In `src/api/routes/telegram.py` / `subscription_service.py`, automatically reset `monthly_tx_count = 0` on the first transaction of a new calendar month (comparing `family.last_reset_month` with current UTC `YYYY-MM`).
  - Check `can_log_transaction(family)` **before** downloading voice audio files or calling Whisper / Ollama AI services.
  - For Free tier workspaces (`plan_type="free"`), if `monthly_tx_count >= 30`:
    - If user is admin $\rightarrow$ immediately respond with friendly quota limit message prompting `/upgrade`.
    - If user is an invited member $\rightarrow$ respond explaining the family's 30-message limit has been reached and advising them to ask their admin to upgrade via `/upgrade`.
    - Halt execution in `< 5ms`.
  - Pro tiers (`"solo_pro"`, `"family_pro"`, `"lifetime_pro"`, and active `"trial"`) bypass quota checks.
- [ ] **Family Management & Removal Commands**:
  - Implement `/family` command for the admin/creator listing all members in the workspace.
  - Implement `/removemember @username` (or member ID) for the family creator:
    - Detaches the member from the family into a new personal Free workspace.
    - Re-assigns the member's transactions (`Transaction.family_id = new_family.id WHERE user_id = member.id`) so the old admin can no longer query or access their expenses.
    - Sends a polite notification to the removed member informing them of their new personal workspace.
- [ ] **Self-Service Leave Command (`/leavefamily`)**:
  - Allows any member to leave independently with full personal transaction portability into a new personal Free workspace.
- [ ] Add unit and integration tests in `tests/api/test_telegram_webhook_core.py`, `tests/services/test_subscription_service.py`, and `tests/services/test_family_service.py`.

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
