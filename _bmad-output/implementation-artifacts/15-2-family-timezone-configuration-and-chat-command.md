# Story 15.2: Family Timezone Configuration & Chat Command

**Epic:** Epic 15 - Household Timezone Support & Dynamic Temporal Resolution
**Status:** Completed
**Author:** Amelia & Sally
**Date:** 2026-09-01

---

## 1. Overview & Context

Users need a straightforward way to view and configure their household timezone via Telegram chat commands with validation against the IANA timezone database.

---

## 2. Technical Implementation

### 2.1 Validation Logic
- In `src/services/family_service.py`:
  - `set_family_timezone(family_id, timezone_str)` validates the string using Python's standard `zoneinfo` or `pytz`.
  - Rejects unknown timezone strings with descriptive error messages.

### 2.2 Command Handling
- In `src/services/handlers/command_handler.py`:
  - `/timezone`: Displays current household timezone and local clock time.
  - `/timezone <IANA_TZ>` or `/settimezone <IANA_TZ>`: Updates household timezone.
  - Generates localized confirmation templates in `src/templates/telegram_messages.py`.

---

## 3. Verification & Acceptance

- Validated via `tests/services/test_timezone_resolution.py`.
- Verified error feedback on invalid inputs like `/timezone Foo/Bar`.
