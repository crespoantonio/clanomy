# Story 1.4: Telegram Gateway & Registration Flow

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **User**,
I want to **register and authenticate by simply starting a chat with the bot**,
so that **I have a zero-friction onboarding experience**.

## Acceptance Criteria

1. **Webhook Security**: The system verifies the `X-Telegram-Bot-Api-Secret-Token` header for all incoming requests (as defined in the architecture's "HMAC signature" requirement, adapted to Telegram's standard secret token mechanism).
2. **Onboarding Flow**: When a user sends `/start` (or any first message), the system detects if they are a new user.
3. **Automatic Registration**: For new users, the system automatically creates:
    - A new `Family` record (as the primary isolation unit).
    - A new `User` record linked to that `Family`, using their `telegram_id`, `username`, and `full_name`.
4. **Immediate Feedback**: The bot responds with a welcoming message confirming the account is ready and explaining how to log the first expense.
5. **Persistence**: User and Family records are correctly saved to the PostgreSQL database via SQLModel.

## Tasks / Subtasks

- [x] **Config & Security Foundation** (AC: 1)
  - [x] Add `TELEGRAM_WEBHOOK_SECRET` to `src/core/config.py`.
  - [x] Implement `verify_telegram_secret` in `src/core/security.py`.
- [x] **Registration Service** (AC: 2, 3)
  - [x] Create `src/services/telegram_service.py`.
  - [x] Implement `get_or_create_user_and_family(telegram_user_data)` logic.
  - [x] Ensure `telegram_id` is handled as `BigInt` (as established in Story 1.3).
- [x] **Webhook API Route** (AC: 1, 2, 4)
  - [x] Create `src/api/routes/telegram.py`.
  - [x] Implement `@router.post("/webhook")` endpoint.
  - [x] Use `python-telegram-bot` (`Update.de_json`) to parse the payload.
  - [x] Integrate the registration service.
- [x] **Main Integration** (AC: 5)
  - [x] Include `telegram` router in `src/main.py`.
- [x] **Unit & Integration Testing** (AC: 1, 3, 5)
  - [x] Create `tests/api/test_telegram_webhook.py`.
  - [x] Mock Telegram payload and verify database record creation.
  - [x] Test with invalid secret token to ensure 403 Forbidden.

## Dev Notes

- **Telegram Library**: We use `python-telegram-bot` v20+. Use the `Application` or `Bot` classes as needed, but since we are in a FastAPI webhook, you primarily need to parse the `Update` object.
- **Security**: The PRD mentions HMAC, but Telegram webhooks use `X-Telegram-Bot-Api-Secret-Token`. Verify this header against `settings.TELEGRAM_WEBHOOK_SECRET`.
- **Database Consistency**: Use the `get_session` dependency to interact with the DB.
- **Onboarding Logic**: For the MVP, every new user gets a fresh `Family`. In Phase 2, we will add invite links.

### Project Structure Notes

- **Gateway Route**: Place the webhook in `src/api/routes/telegram.py` for clarity, even if the architecture tree suggested `logging.py`. This separates routing/registration from the AI pipeline.
- **Security Logic**: Implement the header check in `src/core/security.py` as a FastAPI dependency or a utility function.

### References

- [Architecture: Authentication & Security](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/architecture.md#L118)
- [Architecture: Project Structure](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/architecture.md#L192)
- [Epics: Story 1.4](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/epics.md#L150)
- [SQLModel Models](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/src/db/models.py)

## Dev Agent Record

### Agent Model Used

Gemini 3 Flash

### Debug Log References

### Completion Notes List
- Successfully implemented the Telegram Gateway with robust secret token verification.
- Created a registration service that handles multi-tenant data isolation by creating a new Family for every new user.
- Fixed a critical type mapping bug in the User model (`BigInteger`).
- Verified all components with a suite of 7 unit and integration tests, ensuring 100% success on security and registration flows.
- Updated project configuration and environment templates to include the new webhook secret.
- **Post-Review Patches:** Hardened secret verification with `compare_digest`, implemented atomic DB registration, added non-text message guards, and enabled active Bot welcome messages.

### File List
- `src/core/config.py`
- `src/core/security.py`
- `src/services/telegram_service.py`
- `src/api/routes/telegram.py`
- `src/main.py`
- `src/db/models.py` (Fix)
- `tests/core/test_security.py`
- `tests/services/test_telegram_service.py`
- `tests/api/test_telegram_webhook.py`
- `.env`
- `.env.example`
### Change Log
- Implemented Telegram Webhook with secret token verification (2026-05-09).
- Implemented automatic User and Family registration service (2026-05-09).
- Fixed SQLModel BigInt type definition in User model (2026-05-09).
- Integrated Telegram router into main FastAPI app (2026-05-09).
- Added comprehensive unit and integration tests for security, registration, and webhooks (2026-05-09).
- Applied 8 architectural and security patches based on adversarial code review (2026-05-09).
