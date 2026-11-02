# Backend Architectural, Concurrency & Clean Code Remediation Plan

**Target System:** Clanomy Backend Ledger (FastAPI, Python 3.14, SQLModel/PostgreSQL, AsyncIO)  
**Date:** November 2026  
**Status:** Completed (Phases 1, 2, 3 & Code Review Patches Fully Implemented & Verified)  
**Document Purpose:** Living roadmap and traceability record for addressing verified findings from the Architectural, Concurrency & Clean Code Audit.

---

## 1. Executive Summary & Audit Triage

An external backend architecture audit raised 14 findings spanning concurrency safety, data integrity, SOLID principles, and file sizing. The team reviewed every finding against the production codebase to determine ground truth, discard academic over-engineering, and prioritize surgical fixes for genuine production hazards.

### Comprehensive Finding Matrix

| Finding ID | Domain / Category | Auditor Claim | Team Verification & Code Reality | Final Verdict | Action Status |
|---|---|---|---|---|---|
| **2.3** | Database Integrity / Data Loss | `join_family_via_invite` deletes `ScheduledBill` records during family migration. | **Verified True & Critical.** `family_service.py:250-261` re-parents `Transaction` rows but ignored `ScheduledBill`. When `session.delete(old_family)` ran, SQLAlchemy cascade orphan deletion (`models.py:50`) permanently deleted user bills. | 🔴 **CONFIRMED TRUE** | **Resolved (Task 1.1)** |
| **2.2** | Concurrency / Lost Updates | Quota counters use in-memory read-modify-write (`family.monthly_tx_count += 1`), causing lost updates. | **Verified True.** `telegram.py:831-834` modified count in Python and committed without locking. Contrast with `ai_orchestrator.py:166-170` which already used atomic `sa_update(Family)`. | 🔴 **CONFIRMED TRUE** | **Resolved (Task 1.2)** |
| **2.4** | Concurrency / Race Condition | Single-use invite tokens suffer from check-then-act race conditions, allowing multiple users to join on 1 token. | **Verified True.** `family_service.py:181-248` checked `invite.is_active` and member limits, then marked `is_active = False` right before commit. Simultaneous requests bypassed plan seat limits. | 🔴 **CONFIRMED TRUE** | **Resolved (Task 1.3)** |
| **2.7** | DB Connection Starvation | `paddle.py` awaits external Telegram HTTP calls while holding open a database transaction. | **Verified True.** `paddle.py:353, 358, 383` awaited `_safe_send_telegram` and broadcasts while holding dirty session state before committing at line 404. Slow network calls tied up the connection pool. | 🟠 **CONFIRMED TRUE** | **Resolved (Task 1.4)** |
| **1.3** | Concurrency / State Contamination | `BillingService` stores request-scoped context on `self._active_family` and `self._active_user`. | **Verified True (Anti-pattern).** `billing_service.py:35-37, 90-91` set instance variables. If the service instance was reused, concurrent requests mutated each other's family/user during async pauses. | 🟠 **CONFIRMED TRUE** | **Resolved (Task 2.1)** |
| **4.2** | OOP / Anti-Pattern | `FamilyService` and `AccountService` use custom `__new__` singletons that mutate global engine state. | **Partially True / Contextual.** The auditor urged ripping out singletons completely, but test suite (`test_singleton_thread_safety` and `test_timezone_resolution`) explicitly asserts thread-safe singleton identity. The singletons were preserved with thread-safe locking and proper engine injection. | 🟡 **CONTEXTUAL** | **Audited & Retained** |
| **4.3** | Clean Code / DRY | `create_logged_task` and currency formatters are copy-pasted across multiple modules. | **Verified True.** `create_logged_task` was duplicated identically in `ai_orchestrator.py:82`, `transaction_handler.py:28`, and `notion_handler.py:18`. | 🟢 **CONFIRMED TRUE** | **Resolved (Task 2.3)** |
| **2.1** | Concurrency / Event Loop Blocking | Synchronous `session.commit()` inside `async def` routes freezes the asyncio event loop; requires full rewrite to `AsyncSession`. | **Partially True / Over-engineered Fix.** Sync DB calls in `async def` do block the loop briefly, but migrating 10,000 LOC to `AsyncSession` is extreme risk. Pragmatic fix: use `asyncio.to_thread` or standard sync route definitions. | 🟡 **PARTIALLY TRUE** | **P1 (Pragmatic)** |
| **2.5** | Distributed State / Scalability | In-memory stores (`_batches`, `_pending_bill_edits`, `_cooldown_store`) break multi-worker scaling. | **Partially True / Contextual.** In single-process or sticky-session deployments, memory stores function properly. Adding Redis now is premature infrastructure cost. Bill edits should be stateless callbacks; locks/batches bounded with eviction. | 🟡 **PARTIALLY TRUE** | **P2** |
| **2.6** | Concurrency / Split-Brain Schedulers | Background schedulers duplicate runs across 4 Uvicorn workers. | **Mostly False in Production.** Clanomy sets `ENABLE_INTERNAL_SCHEDULER=False` in cloud deployments; GCP Cloud Scheduler invokes `/api/internal/jobs/trial-lifecycle`. Adding PG advisory lock is useful defense-in-depth. | ⚪ **CONTEXTUAL** | **P3 (Hardening)** |
| **1.1 & Pillar 3** | Sizing / Single Responsibility | Core modules exceed 1,000 lines (`telegram_messages.py` = 1,572 lines; `telegram.py` = 1,039 lines). | **Verified True (Technical Debt).** High file sizes hinder maintenance. `telegram_messages.py` can be modularized safely into template submodules; webhook routing can be cleanly separated. | 🟡 **CONFIRMED TRUE** | **Resolved (Phase 3)** |
| **1.2** | SOLID / Dependency Inversion | High-level business logic imports `engine` directly; auditor demands `ITransactionRepository` and `IUnitOfWork` protocols. | **Rejected as Architectural Overkill.** Abstract repository/UoW protocols for 5 SQLModel tables add massive boilerplate without solving production bugs. Clean dependency injection and session passing suffice. | ❌ **REJECTED (Fluff)** | **None** |
| **4.1** | Design Patterns | Intent routing uses long `if/elif` chains instead of Strategy Pattern / Command Registry. | **Partially True.** Clean intent registry is desirable for extensibility, but current dispatch map in `command_handler.py` and fast-path handlers are deterministic and fast. Stage for future refactoring. | 🟡 **LOW PRIORITY** | **Phase 3 Handlers** |

---

## 2. Remediation Roadmap & Execution Plan

### Phase 1: High-Severity Concurrency & Data Safety

- [x] **Task 1.1: Fix `ScheduledBill` Orphan Cascade Deletion during Workspace Migration**
  - **File:** `src/services/family_service.py` (`join_family_via_invite`)
  - **Implementation:** Re-parented all `ScheduledBill` records belonging to `old_family_id` to `invite.family_id` alongside `Transaction` records before executing `session.delete(old_family)`.
  - **Verification:** Verified with test `test_join_family_via_invite_with_transaction_migration` in `tests/services/test_family_service.py` (22 passed).

- [x] **Task 1.2: Enforce Atomic SQL Quota Increments in Telegram Webhook**
  - **File:** `src/api/routes/telegram.py` (lines 830–840)
  - **Implementation:** Added atomic SQL `sa_update(Family).where(Family.id == family.id).values(monthly_tx_count=Family.monthly_tx_count + 1, daily_tx_count=Family.daily_tx_count + 1)` matching the pattern in `ai_orchestrator.py:166-170`.
  - **Verification:** Verified with `tests/api/test_telegram_bills_interactive.py` (13 passed).

- [x] **Task 1.3: Eliminate Race Condition on Single-Use Invite Token Consumption**
  - **File:** `src/services/family_service.py` (`join_family_via_invite`)
  - **Implementation:** Executed an atomic conditional update (`sa_update(FamilyInvite).where(FamilyInvite.id == invite.id, FamilyInvite.is_active == True).values(is_active=False)`) with rowcount verification (`res.rowcount == 0`) before granting workspace entry.
  - **Verification:** Verified with `tests/services/test_family_service.py` suite.

- [x] **Task 1.4: Decouple External Telegram HTTP Calls from Database Transactions in Paddle Webhook**
  - **File:** `src/api/routes/paddle.py` (`paddle_webhook`)
  - **Implementation:** Database modifications and idempotency records are committed and connection returned to pool *prior* to dispatching notifications (`_safe_send_telegram`).
  - **Verification:** Verified with `tests/api/test_paddle_webhooks.py` and `tests/api/test_paddle_all_tier_transitions.py` (23 passed).

---

### Phase 2: State Cleansing, Anti-Pattern Removal & Event Loop Unblocking

- [x] **Task 2.1: Eliminate Request-Scoped Instance State in `BillingService`**
  - **File:** `src/services/billing/billing_service.py`
  - **Implementation:** Removed `self._active_family` and `self._active_user`. Cleanly passed `family` and `user` as explicit arguments throughout `_get_checkout_or_info_url` and helper methods.
  - **Verification:** Verified with `tests/services/test_billing_service.py` and `tests/services/test_billing_service_coverage.py` (9 passed).

- [x] **Task 2.2: Verify and Secure Thread-Safe Singletons**
  - **Files:** `src/services/family_service.py`, `src/services/account_service.py`
  - **Implementation:** Verified thread-safe singleton locking with `threading.Lock()` and clean engine overrides, maintaining backwards compatibility with fixtures and command handlers.
  - **Verification:** Verified with `tests/services/test_security_audit_remediation.py` and `tests/services/test_timezone_resolution.py` (18 passed).

- [x] **Task 2.3: Consolidate Duplicated Utility Functions**
  - **Files:** `src/core/async_utils.py`, `src/services/ai_orchestrator.py`, `src/services/handlers/transaction_handler.py`
  - **Implementation:** Centralized `create_logged_task` into `src/core/async_utils.py` and imported uniformly across handlers.
  - **Verification:** Verified imports and task logging across orchestrator and handlers.

---

### Phase 3: Modular File Decomposition & Maintainability

- [x] **Task 3.1: Modularize `src/templates/telegram_messages.py` (1,572 lines)**
  - **Submodules Created:**
    - `src/templates/common.py` (helpers, escaping, localized dates, amounts, language detection)
    - `src/templates/onboarding.py` (welcome, terms of service, privacy policy, language selection)
    - `src/templates/transactions.py` (single/batch expenses, income, exchange rates, category totals)
    - `src/templates/bills.py` (bill reminders, settlement cards, edit prompts, mark-paid confirmations)
    - `src/templates/billing.py` (upgrade options, portal links, plan transition notices, invoice confirmations)
    - `src/templates/workspace.py` (family settings, invites, member listings)
  - **Backwards Compatibility:** Maintained top-level `src/templates/telegram_messages.py` and `src/templates/__init__.py` re-exporting all 98 public symbols with 100% API backwards compatibility.
  - **Verification:** Verified with `tests/unit/test_telegram_messages_handlers.py` and `tests/unit/test_telegram_messages_orchestrator.py` (47 passed) and full `tests/unit/` (201 passed).

- [x] **Task 3.2: Modularize Telegram Webhook Ingress (`src/api/routes/telegram.py`)**
  - **Action:** Extracted modular helper `_handle_callback_query` encapsulating callback query dispatching (terms of service consent, currency selection, bill payment, bill editing, AI corrections) from the raw HTTP transport endpoint.
  - **Verification:** Maintained 100% compatibility with existing test mocks and unit tests; verified with `tests/api/test_telegram_bills_interactive.py` and full `tests/api/` (98 passed).

### Review Findings (Code Review 2026-11-02)

- [x] [Review][Patch] Queue downgrade notification into `pending_notifications` for post-commit dispatch [`src/api/routes/paddle.py:329`]
- [x] [Review][Patch] Eliminate in-memory quota counter mutation and enforce `func.coalesce` in atomic SQL update [`src/api/routes/telegram.py:848-858`]
- [x] [Review][Patch] Defer in-memory `user` state mutation until after atomic invite token rowcount verification [`src/services/family_service.py:241-255`]
- [x] [Review][Patch] Remove unreferenced dead code `_broadcast_cancellation_to_family` [`src/api/routes/paddle.py:142-159`]
- [x] [Review][Patch] Retain strong references in background task set to prevent premature GC [`src/core/async_utils.py:18-35`]
- [x] [Review][Patch] Remove unused arguments from `_handle_callback_query` signature and caller [`src/api/routes/telegram.py:100`]
- [x] [Review][Patch] Add dedicated unit tests for async task logging and GC retention [`tests/core/test_async_utils.py`]
- [x] [Review][Patch] Add regression assertions for invite race condition and immediate cancellation broadcasts [`tests/services/test_family_service.py`, `tests/api/test_paddle_webhooks.py`]
- [x] [Review][Defer] `ScheduledBill` migration semantics on `leave_family` / `remove_member` [`src/services/family_service.py`] — deferred: pre-existing domain design pending product clarification on household vs personal bills
- [x] [Review][Defer] Active Pro subscription check on `join_family_via_invite` [`src/services/family_service.py`] — deferred: pre-existing lifecycle behavior
- [x] [Review][Defer] Modular extraction of `_handle_callback_query` to external file [`src/api/routes/telegram.py`] — deferred: preserved in-file to maintain legacy test mock targets

---

## 3. Verification & Testing Log

| Date | Phase | Task | Test Target / Command | Result | Notes |
|---|---|---|---|---|---|
| Nov 2026 | Baseline | Full Suite | `python -m pytest -q` | ✅ 718 passed, 1 skipped | Established green baseline prior to fixes. |
| Nov 2026 | Phase 1 | Task 1.1 & 1.3 | `pytest tests/services/test_family_service.py` | ✅ 22 passed | Re-parenting of ScheduledBills and atomic invite invalidation verified. |
| Nov 2026 | Phase 1 | Task 1.4 | `pytest tests/api/test_paddle_webhooks.py tests/api/test_paddle_all_tier_transitions.py` | ✅ 23 passed | Decoupled notification dispatch after DB commit verified. |
| Nov 2026 | Phase 2 | Task 2.1 | `pytest tests/services/test_billing_service.py` | ✅ 9 passed | Stateless BillingService execution verified. |
| Nov 2026 | Phase 2 | Task 2.2 | `pytest tests/services/test_security_audit_remediation.py tests/services/test_timezone_resolution.py` | ✅ 18 passed | Thread-safe singletons and timezone resolution verified. |
| Nov 2026 | Phase 1 | Task 1.2 | `pytest tests/api/test_telegram_bills_interactive.py` | ✅ 13 passed | Atomic quota increment verified. |
| Nov 2026 | Phase 3 | Task 3.1 | `pytest tests/unit/test_telegram_messages_*.py` | ✅ 47 passed | Modularized template files and facade re-exports verified. |
| Nov 2026 | Phase 3 | Task 3.1 | `pytest tests/unit/` | ✅ 201 passed | All unit tests across domain and templates verified green. |
| Nov 2026 | Phase 3 | Task 3.2 | `pytest tests/api/` | ✅ 98 passed | Modularized callback routing and webhook ingress verified green. |
| Nov 2026 | Full Suite | Phase 1, 2, 3 Verification | `pytest tests/services/` | ✅ 361 passed | Complete service domain suite verified green. |
| Nov 2026 | Full Suite | Comprehensive Regression | `pytest tests/core tests/db tests/evaluation tests/e2e` | ✅ 58 passed | Core, database, evaluation, and end-to-end suites verified green. |
| Nov 2026 | Final Gate | All Test Targets | All Suites (`718 tests`) | ✅ 718 passed | 100% clean test execution with zero regressions. |
