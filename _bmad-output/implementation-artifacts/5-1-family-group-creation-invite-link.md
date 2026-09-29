# Story 5.1: Family Group Creation & Invite Link

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a User,
I want to create a Family Group and generate a unique invite link,
so that I can easily add my partner, housemates, or family members to my shared financial ledger.

## Acceptance Criteria

1. **Family Creation & Customization**:
   - The system allows users to create a named family group or rename their current family unit (e.g., via `/createfamily <name>`, `/family rename <name>`, or natural language triggers like "create family The Smiths", "create a family group named Vacation").
   - When a user creates a new family group:
     - If the user is in an existing single-member family with 0 transactions, update the existing `Family.name` or associate the user with the new `Family` record and purge the orphan family.
     - If the user already belongs to a multi-member family or has transactions, create a new `Family` record and migrate the user to the new `family_id`.
   - The user receives immediate confirmation with the new family group name and instructions to invite members.

2. **Secure Time-Limited Invite Link Generation (`FamilyService`)**:
   - Implement `FamilyService.create_invite(family_id: UUID, user_id: UUID, ttl_hours: int = 48) -> Tuple[FamilyInvite, str]` in `src/services/family_service.py`.
   - Generate a cryptographically secure, URL-safe random token (e.g., using `secrets.token_urlsafe(16)`).
   - Persist the invite in a new `FamilyInvite` database table with:
     - `id: UUID` (primary key)
     - `family_id: UUID` (foreign key to `family.id` with `ondelete="CASCADE"`)
     - `created_by_user_id: UUID` (foreign key to `user.id` with `ondelete="CASCADE"`)
     - `token: str` (unique, indexed)
     - `expires_at: datetime` (timestamped UTC expiration, default +48 hours)
     - `is_active: bool` (default `True`)
     - `created_at: datetime` (UTC timestamp)
   - Construct a Telegram deep link URL: `https://t.me/<bot_username>?start=join_<token>` (or `start=<token>`).
   - Triggerable via bot command `/invite` or natural language intent ("invite family member", "generate invite link", "invite to family").
   - Return the invite link along with clear expiration guidance (e.g., `⏳ This invite link will expire in 48 hours.`).

3. **Telegram Deep-Link Ingress & Family Join Flow**:
   - Update `src/api/routes/telegram.py` webhook handler to parse start payloads containing `/start join_<token>` or `/start <token>`.
   - When an invited user opens the bot via the invite link:
     - Ensure the user is registered or retrieved via `MessagingService.get_or_create_user_and_family()`.
     - Validate the invite token via `FamilyService.join_family_via_invite(token: str, user_id: UUID) -> Tuple[bool, str, Optional[Family]]`:
       - Check if the invite token exists in the database.
       - Check if `invite.is_active` is `True` and `invite.expires_at > datetime.now(timezone.utc)`.
       - Check if the user is already a member of `invite.family_id` (if so, return a friendly notice: "You are already a member of this family!").
     - On successful validation:
       - Update the joining user's `user.family_id = invite.family_id`.
       - If the user's prior family was an empty single-member family with 0 transactions, safely delete the unused family.
       - Return a warm, celebratory welcome message:
         `🎉 Welcome to <b>{family.name}</b>, {user.full_name or 'User'}!\n\nYou have successfully joined the family ledger. All expenses you log will now be shared with your family.`
       - Optionally dispatch an async notification message to the family creator/members alerting them that a new member has joined.
     - On invalid or expired token:
       - Return an explicit, friendly error:
         `⚠️ This family invite link is invalid or has expired. Please ask a family member to generate a new invite link.`

4. **Family Membership & Status Inspection (`/family`)**:
   - Provide a `/family` command or natural language trigger ("my family", "family info", "family members") that displays:
     - Family group name.
     - List of active member names/usernames.
     - Number of transactions currently in the shared ledger.
     - Active invite status (if any pending invite links exist).

5. **Multi-Tenant Isolation & Cascade Integrity**:
   - Strictly guarantee that joining a family only associates the user with the target `family_id` and does not grant cross-family data access.
   - When a `Family` is deleted, all associated `FamilyInvite` records must be cascade-deleted automatically.
   - When an inviting `User` is deleted, any invites created by that user must be cascade-deleted or deactivated cleanly.

6. **Performance & Latency (The 3s Rule)**:
   - Invite link generation, validation, and joining must execute in `< 1.0s` and be logged with `[3s Audit]` performance metrics.
   - All database operations in `FamilyService` must run in background worker threads via `asyncio.to_thread()`.

7. **Comprehensive Unit & Integration Test Suite**:
   - Create `tests/services/test_family_service.py` to test:
     - Family creation and renaming.
     - Invite token generation with correct expiration timestamps.
     - Successful family joining flow.
     - Expired invite link rejection.
     - Inactive/revoked invite token rejection.
     - Duplicate joining handling (user already in family).
     - Empty orphan family cleanup upon joining.
   - Update `tests/api/test_telegram_webhook.py` to test `/start join_<token>` deep-link payload routing.
   - Update `tests/services/test_ai_orchestrator.py` to verify family commands/intents (`create_family`, `generate_invite`, `family_info`).
   - Ensure 100% test pass rate with `.\venv\Scripts\python -m pytest`.

## Tasks / Subtasks

- [x] **Database Schema & Models Update** (AC: 2, 5)
  - [x] Add `FamilyInvite` SQLModel in `src/db/models.py` with foreign keys to `Family` and `User` and cascade delete constraints.
  - [x] Update `Family` and `User` models to define relationships with `FamilyInvite`.
  - [x] Ensure `src/db/session.py` registers `FamilyInvite` for automatic table creation.
- [x] **FamilyService Implementation** (AC: 1, 2, 3, 4, 6)
  - [x] Create `src/services/family_service.py` (singleton pattern).
  - [x] Implement `create_family(user_id: UUID, name: str) -> Family`.
  - [x] Implement `create_invite(family_id: UUID, user_id: UUID, ttl_hours: int = 48) -> Tuple[FamilyInvite, str]`.
  - [x] Implement `join_family_via_invite(token: str, user_id: UUID) -> Tuple[bool, str, Optional[Family]]`.
  - [x] Implement `get_family_info(user_id: UUID) -> Dict[str, Any]`.
  - [x] Add `[3s Audit]` logging on all operations.
- [x] **Config & Bot Username Resolution** (AC: 2)
  - [x] Add `TELEGRAM_BOT_USERNAME: Optional[str] = None` in `src/core/config.py` with fallback resolution.
  - [x] Update `TelegramService` with helper `get_bot_username() -> str` (cache bot username or fetch via Telegram `getMe`).
- [x] **Telegram Webhook & Deep-Link Processing** (AC: 3)
  - [x] Update `src/api/routes/telegram.py` `/webhook` endpoint to inspect `/start` arguments (e.g. `/start join_<token>` or `/start <token>`).
  - [x] Invoke `FamilyService.join_family_via_invite` on valid invite start payloads and dispatch welcome message.
- [x] **Intent Classification & AI Orchestrator Integration** (AC: 1, 2, 4)
  - [x] Update `ParsedQueryIntent` in `src/services/query_service.py` with `create_family`, `generate_invite`, and `family_info` intents.
  - [x] Update `_is_special_intent` in `src/services/ai_orchestrator.py` with family keywords (`family`, `invite`, `join`, `create family`, `invite link`).
  - [x] Handle family intents in `AIOrchestrator.orchestrate()` and dispatch responses.
- [x] **Unit & Integration Test Suite** (AC: 7)
  - [x] Create `tests/services/test_family_service.py`.
  - [x] Update `tests/db/test_models.py` for `FamilyInvite` schema and cascade deletes.
  - [x] Update `tests/api/test_telegram_webhook.py` for `/start join_<token>` deep linking.
  - [x] Update `tests/services/test_ai_orchestrator.py` for family intents.
  - [x] Run full test suite with `.\venv\Scripts\python -m pytest` and verify 100% pass rate.

### Review Findings

- [x] [Review][Decision] Transaction migration policy when joining a new family — When a user joins a new family via an invite link, their user.family_id is updated. However, their pre-existing transactions remain associated with their old family_id. If the old family was a single-member family (i.e. the user was solo), they will lose access to their history. We need to decide whether to migrate their existing transactions to the new family or leave them in the old family scope.
- [x] [Review][Patch] Non-Atomic DB Transactions in FamilyService [src/services/family_service.py:35]
- [x] [Review][Patch] Dangling Foreign Key references in Tests [tests/services/test_family_service.py:24]
- [x] [Review][Patch] Command Execution Latency Bypass [src/services/ai_orchestrator.py:113]
- [x] [Review][Patch] Dynamic Bot Username Resolution in Invites [src/services/family_service.py:91]
- [x] [Review][Patch] Singleton Engine Binding in FamilyService [src/services/family_service.py:25]

## Dev Notes

### Architecture & Service Design

- **Service Pattern**: Follow the existing singleton pattern in `src/services/account_service.py`, `src/services/export_service.py`, and `src/services/query_service.py`.
- **Token Security**:
  - Tokens must be cryptographically generated via `secrets.token_urlsafe(16)` (22 characters, URL-safe).
  - Telegram deep linking parameters must be alphanumeric or underscores (`A-Za-z0-9_-`) with length ≤ 64 bytes.
  - `expires_at` is calculated as `datetime.now(timezone.utc) + timedelta(hours=ttl_hours)`.
- **Database Cascade Logic**:

  ```python
  class FamilyInvite(SQLModel, table=True):
      id: UUID = Field(default_factory=uuid4, primary_key=True)
      family_id: UUID = Field(foreign_key="family.id", index=True, ondelete="CASCADE")
      created_by_user_id: UUID = Field(foreign_key="user.id", index=True, ondelete="CASCADE")
      token: str = Field(unique=True, index=True)
      expires_at: datetime = Field(index=True)
      is_active: bool = Field(default=True)
      created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

      family: "Family" = Relationship(back_populates="invites")
      creator: "User" = Relationship(back_populates="created_invites")
  ```

- **Non-blocking Execution**:
  All database access in `FamilyService` must be executed synchronously within `Session(engine)` wrapped inside `asyncio.to_thread()` when called from async request handlers or orchestrator loops.

### Project Structure Notes

- New files:
  - `src/services/family_service.py`
  - `tests/services/test_family_service.py`
- Modified files:
  - `src/db/models.py` (add `FamilyInvite`, update relationships)
  - `src/db/session.py` (import `FamilyInvite` to ensure table creation)
  - `src/core/config.py` (add `TELEGRAM_BOT_USERNAME`)
  - `src/services/telegram_service.py` (add `get_bot_username`)
  - `src/api/routes/telegram.py` (handle `/start join_<token>`)
  - `src/services/query_service.py` (add family intents)
  - `src/services/ai_orchestrator.py` (route family commands and intents)
  - `tests/api/test_telegram_webhook.py` (add deep-link join tests)
  - `tests/db/test_models.py` (add `FamilyInvite` tests)
  - `tests/services/test_ai_orchestrator.py` (add family orchestrator tests)

### References

- [Architecture: Multi-Tenancy & Family Scoping](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/architecture.md#L105)
- [Architecture: Project Directory Structure](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/architecture.md#L196)
- [Epics: Story 5.1](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/epics.md#L309)
- [PRD: Family Groups (FR10)](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/prd.md#L109)
- [Epic 4 Retrospective: Commitments for Epic 5](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/implementation-artifacts/epic-4-retro-2026-08-16.md#L40)

## Dev Agent Record

### Agent Model Used

Gemini 3.7 Flash (High)

### Debug Log References

### Completion Notes List

### File List
