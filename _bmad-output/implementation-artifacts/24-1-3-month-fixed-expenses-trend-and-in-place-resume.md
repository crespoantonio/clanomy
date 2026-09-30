---
story_id: "24.1"
epic_id: "24"
title: "3-Month Fixed Expenses Trend & In-Place Resume for Bills"
status: "done"
priority: "high"
author: "Mary, Sally, Amelia & Winston"
date: "2026-09-30"
---

# Story 24.1: 3-Month Fixed Expenses Trend & In-Place Resume for Bills

## 1. Overview & Context

Users frequently track their recurring "bills" or fixed spending obligations (loans, credit card installments, insurance, utilities, subscriptions) in physical paper ledgers to answer a fundamental financial question: **Is my fixed overhead growing or shrinking over time?**

Currently, Clanomy's `/bills` command is an operational triage tool: it queries `ScheduledBill` records with `status = "pending"` for the current (or next) month, displaying pending commitments with 1-tap settlement buttons. However, it lacks retrospective visibility into the fixed commitments baseline across preceding months.

This story implements **Option C**:
1. **Compact Static Badge inside `/bills`:** Directly below the pending total, displays a 1-line 3-month trailing indicator (`📈 3-Mo Fixed: [M-2] ➔ [M-1] ➔ [M] (±Δ%)`).
2. **Resilient Data State Handling:** The label `"3-Mo Fixed"` remains static and anchored. Any month without recorded scheduled bills gracefully renders as `(No info)` (or `(Sin datos)` in Spanish), with delta percentages strictly suppressed to eliminate division-by-zero errors.
3. **In-Place Interactive Deep Dive:** Adds an inline button `[ 📊 3-Mo Trend ]` (and `/bills trend` fast-path) that uses Telegram `edit_message_text` to flip into a dedicated 3-month breakdown card with paid vs. pending status, trailing average, and a `[ ↩️ Back to Bills ]` return toggle.

---

## 2. User Story & Acceptance Criteria

### User Story
As a Clanomy User,  
I want to view a 3-month summary of my fixed expenses within the `/bills` command and toggle into a dedicated historical card,  
So that I can clearly see whether my fixed overhead is growing or decreasing without cluttering daily bill payments.

### Acceptance Criteria
- [x] **AC 24.1.1 (Static Badge in `/bills`):** In `format_bills_summary()`, append a compact badge below `📌 Total Pending`:
  - English: `📈 3-Mo Fixed: <M-2> ➔ <M-1> ➔ <M> [optional Δ%]`
  - Spanish: `📈 Gastos Fijos (3M): <M-2> ➔ <M-1> ➔ <M> [optional Δ%]`
- [x] **AC 24.1.2 (Label Invariance & "No info" Fallback):** The label (`3-Mo Fixed` / `Gastos Fijos (3M)`) must remain completely static regardless of how many months have data.
  - If a calendar month has no recorded scheduled bills, it displays `<MonthAbbr> (No info)` in English or `<MonthAbbr> (Sin datos)` in Spanish.
  - If all 3 months lack data, display `📈 3-Mo Fixed: <M-2> (No info) ➔ <M-1> (No info) ➔ <M> (No info)`.
- [x] **AC 24.1.3 (Zero Division & Delta Guardrails):**
  - $\Delta\%$ between Month $A$ and Month $B$ is calculated as `((B - A) / A) * 100` **only if** both months have recorded data and $A > 0$.
  - If Month $A$ is `(No info)` or `$0.00`, delta percentage is completely omitted/suppressed (no `+∞%`, `NaN`, or exceptions).
- [x] **AC 24.1.4 (Interactive Inline Button):** In `build_bills_keyboard()`, include an inline button:
  - English: `[ 📊 3-Mo Trend ]`
  - Spanish: `[ 📊 Tendencia 3M ]`
  - Callback data: `bills_t:<tf_code>` (where `tf_code` is `this` or `next`).
- [x] **AC 24.1.5 (In-Place Trend Card & Return Navigation):**
  - Webhook callback handler in `src/api/routes/telegram.py` intercepts `bills_t:` and calls `edit_message_text`.
  - The rendered card details each of the 3 months: total amount, paid amount, pending amount, and month-over-month trend.
  - Includes a trailing monthly average across populated months.
  - Provides a return button `[ ↩️ Back to Bills ]` (`bills_p:1:<tf_code>`) that seamlessly restores the standard bills view.
- [x] **AC 24.1.6 (Fast-Path Slash Command):** Running `/bills trend` or `/bills historia` directly outputs the 3-month trend card.

---

## Tasks / Subtasks
- [x] **Task 1: Structured Data Models & Types** (AC: 24.1.1, 24.1.3)
  - [x] Add `MonthFixedCommitment` and `BillsTrendSummary` dataclasses to `src/services/query/models.py`.
- [x] **Task 2: Query Engine 3-Month Trailing Aggregation** (AC: 24.1.1, 24.1.2, 24.1.3)
  - [x] Implement `get_bills_trend_data` in `src/services/query/service.py`.
  - [x] Calculate rolling 3 calendar months with year wrap-around resilience.
  - [x] Query and decrypt `ScheduledBill` records (`status IN ('pending', 'paid')`).
  - [x] Group by month, flag `has_data`, compute safe `delta_pct` with zero-division guard, and compute trailing average.
- [x] **Task 3: Deterministic Formatters for Badge and Trend Card** (AC: 24.1.1, 24.1.2, 24.1.5)
  - [x] Implement `format_bills_trend_badge` in `src/services/query/formatters.py`.
  - [x] Implement `format_bills_trend_card` in `src/services/query/formatters.py`.
  - [x] Update `format_bills_summary` to optionally embed the trend badge below `Total Pending`.
- [x] **Task 4: Interactive Bill Handler & Fast-Path Command** (AC: 24.1.4, 24.1.5, 24.1.6)
  - [x] Update `build_bills_keyboard` in `src/services/handlers/bill_handler.py` to include `[ 📊 3-Mo Trend ]` button.
  - [x] Implement `build_bills_trend_card` in `src/services/handlers/bill_handler.py` with `[ 🔙 Back to Bills ]` markup.
  - [x] Update `handle_bills_interactive` in `src/services/handlers/bill_handler.py` and `CommandHandler.handle_bills` in `src/services/handlers/command_handler.py` to support `trend` sub-command argument.
- [x] **Task 5: Telegram Webhook Ingress & Callback Routing** (AC: 24.1.5)
  - [x] In `src/api/routes/telegram.py`, route `bills_t:` callback to `bill_handler.build_bills_trend_card`.
  - [x] In-place message edit via `telegram_service.edit_message_text`.
- [x] **Task 6: Verification & Test Suite** (AC: All)
  - [x] Write unit tests in `tests/services/test_bills_trend.py`.
  - [x] Write interactive webhook tests in `tests/api/test_telegram_bills_interactive.py`.
  - [x] Run full test suite to guarantee zero regressions.

### Review Findings
- [x] [Review][Patch] Dominant currency segregation in trend data: aggregate totals for primary/dominant currency and avoid cross-currency addition [src/services/query/service.py:883-917]
- [x] [Review][Patch] Fix non-existent `user.preferred_language` check causing bilingual mismatch in `/bills` and `/bills trend` [src/services/handlers/bill_handler.py:594, src/services/handlers/command_handler.py:205]
- [x] [Review][Patch] Wrap Telegram `edit_message_text` in try-except to handle duplicate clicks gracefully [src/api/routes/telegram.py:356-363]
- [x] [Review][Patch] Align return button emoji with AC 24.1.5 (`[ ↩️ Back to Bills ]`) [src/services/handlers/bill_handler.py:393]
- [x] [Review][Patch] Support timeframe modifier (`next` / `proximo`) in trend subcommand [src/services/handlers/bill_handler.py:596, src/services/handlers/command_handler.py:207]
- [x] [Review][Patch] Pass `family.default_currency` to `get_bills_trend_data` and reuse `EncryptionService` [src/services/handlers/bill_handler.py:378, src/services/handlers/command_handler.py:224]

---

## 3. Developer Implementation Guide

### 3.1 Architecture & Component Mapping

#### A. Data Models (`src/services/query/models.py`)
Define structured trend data types:
```python
@dataclass
class MonthFixedCommitment:
    year: int
    month: int
    month_name: str         # e.g., "Jul", "Ago", "Aug"
    total_amount: float
    paid_amount: float
    pending_amount: float
    currency: str
    has_data: bool
    delta_pct: Optional[float] = None

@dataclass
class BillsTrendSummary:
    months: List[MonthFixedCommitment]  # Exactly 3 months in chronological order [M-2, M-1, M]
    primary_currency: str
    trailing_average: Optional[float] = None
    has_any_data: bool = False
```

#### B. Query Aggregation Engine (`src/services/query/service.py`)
Add method `get_bills_trend_data`:
```python
def get_bills_trend_data(
    self,
    family_id: UUID,
    reference_time: Optional[datetime] = None,
    tz_name: Optional[str] = None,
    language: str = "auto"
) -> BillsTrendSummary:
```
- **Calendar Boundary Math:**
  - Given `ref_time` (adjusted to `tz_name`):
  - Determine Month $M$ (current month), Month $M-1$, and Month $M-2$.
  - Correctly handle year roll-overs (e.g., if $M$ is January 2027, $M-1$ is December 2026, $M-2$ is November 2026).
  - Compute start timestamp: 1st day of Month $M-2$ at 00:00:00 local time -> convert to UTC.
  - Compute end timestamp: last microsecond of Month $M$ local time -> convert to UTC.
- **Data Query & Decryption:**
  - Query `ScheduledBill` where `family_id == family_id`, `due_date >= start_time`, `due_date <= end_time`, and `status IN ('pending', 'paid')`.
  - In-memory decryption of `amount` and `concept` via `EncryptionService`.
  - Group bills by `(due_date.year, due_date.month)`.
- **Month Aggregation & Guardrails:**
  - For each of the 3 target slots:
    - If group has bills: `has_data = True`, `total_amount = sum(b.amount)`, `paid_amount = sum(...)`, `pending_amount = sum(...)`.
    - If group has 0 bills: `has_data = False`, `total_amount = 0.0`.
  - Compute `delta_pct` sequentially:
    - `if m[i].has_data and m[i-1].has_data and m[i-1].total_amount > 0:`
      `m[i].delta_pct = ((m[i].total_amount - m[i-1].total_amount) / m[i-1].total_amount) * 100`
    - `else: m[i].delta_pct = None`
  - Compute `trailing_average`: Average `total_amount` of months where `has_data == True`.

#### C. Formatters (`src/services/query/formatters.py`)
1. **`format_bills_trend_badge(trend: BillsTrendSummary, is_spanish: bool) -> str`**:
   - Renders 1-line badge:
     `📈 3-Mo Fixed: Jul (No info) ➔ Aug $1,250.00 ➔ Sep $1,420.00 (+13.6%)`
2. **`format_bills_trend_card(trend: BillsTrendSummary, is_spanish: bool, tz_name: Optional[str] = None) -> str`**:
   - Renders the full breakdown card with HTML formatting:
     ```html
     📊 <b>Fixed Expenses — 3-Month Trend</b>
     ━━━━━━━━━━━━━━━━━━━━━
     • <b>Jul:</b> <i>No info</i>
     • <b>Aug:</b> $1,250.00 USD (100% paid ✅)
     • <b>Sep:</b> $1,420.00 USD ($850.00 paid / $570.00 pending) <i>(+13.6%)</i>

     📌 <b>Trailing average:</b> $1,335.00 USD / mo
     ━━━━━━━━━━━━━━━━━━━━━
     ```
3. **Update `format_bills_summary`**:
   - Accept optional `trend_summary: Optional[BillsTrendSummary] = None` or optional pre-formatted `trend_badge: Optional[str] = None`.
   - Insert right below `📌 Total Pending: ...`.

#### D. Handler & Keyboard (`src/services/handlers/bill_handler.py`)
1. **`build_bills_keyboard`**:
   - Add trend button row: `[{"text": "📊 3-Mo Trend", "callback_data": f"bills_t:{tf_code}"}]`.
2. **`build_bills_trend_card`**:
   - Calls `QueryService.get_bills_trend_data()`.
   - Calls `format_bills_trend_card()`.
   - Returns card text and keyboard containing `[{"text": "🔙 Back to Bills", "callback_data": f"bills_p:1:{tf_code}"}]`.
3. **`handle_bills_interactive`**:
   - Fetch bills trend data alongside pending bills and pass badge to `format_bills_summary`.

#### E. Webhook Route (`src/api/routes/telegram.py`)
- In `handle_telegram_webhook`, extend callback query prefixes:
  ```python
  if cb_data.startswith(("curr_p:", "curr_set:", "bills_p:", "bills_t:", "bill_v:", "bill_pay:", "bill_edit:")):
  ```
- If `cb_data.startswith("bills_t:")`:
  - Parse `tf_code = cb_data.split(":")[1] if ":" in cb_data else "this"`.
  - Invoke `bill_handler.build_bills_trend_card(family.id, ...)`.
  - Call `telegram_service.edit_message_text(chat_id, message_id, text, reply_markup=keyboard)`.
  - Acknowledge via `answer_callback_query`.

---

## 4. Edge Cases & Defensive Guardrails

| Edge Case | Expected System Behavior |
| :--- | :--- |
| **New Family (Zero Historical Data)** | Displays `3-Mo Fixed: [M-2] (No info) ➔ [M-1] (No info) ➔ [M] (No info)`. No exception thrown. |
| **Only Current Month Has Bills** | Displays `3-Mo Fixed: [M-2] (No info) ➔ [M-1] (No info) ➔ [M] $500.00`. $\Delta\%$ is omitted. |
| **Month Has $0.00 Total** | Division by zero is avoided (`if prev_total > 0`). Delta is suppressed (`None`). |
| **Dec/Jan Year Boundary** | Rolling 3 months spanning December -> January (e.g. Nov 2026, Dec 2026, Jan 2027) resolved with correct year arithmetic. |
| **Multi-Currency Scheduled Bills** | Primary currency selected from family default currency or dominant bill currency; secondary currencies segregated cleanly. |
| **XSS / HTML Escaping** | Month names and currency symbols properly escaped via `html.escape`. |

---

## 5. Verification & Testing Standards

### Automated Tests to Implement:
1. **`tests/services/test_bills_trend.py`**:
   - `test_bills_trend_full_three_months`: Verify sum, paid/pending segregation, and delta percentages across 3 populated months.
   - `test_bills_trend_partial_data_one_month`: Verify `(No info)` fallback and delta suppression.
   - `test_bills_trend_empty_database`: Verify empty DB produces clean `(No info)` states without errors.
   - `test_bills_trend_year_boundary`: Test January reference date correctly querying November and December of previous year.
   - `test_bills_trend_zero_amount_division_guard`: Test transition from $0 to $100 does not raise `ZeroDivisionError`.
2. **`tests/api/test_telegram_bills_interactive.py`**:
   - Test callback query `bills_t:this` invokes `edit_message_text` with trend card content and return button.
   - Test return button `bills_p:1:this` successfully restores bills list.

---

## 6. Definition of Done
- [x] PRD updated with FR68, FR69, FR70.
- [x] `epics.md` updated with Epic 24 & Story 24.1.
- [x] `sprint-status.yaml` updated with `epic-24: in-progress` and `24-1-3-month-fixed-expenses-trend-and-in-place-resume: review`.
- [x] Implementation completed across `QueryService`, `formatters.py`, `bill_handler.py`, and `telegram.py`.
- [x] 100% automated test pass rate with zero regressions in existing `/bills` interactive flows.

---

## Dev Agent Record

### Implementation Plan
- **Phase 1: Models & Aggregation Engine**:
  - Add `MonthFixedCommitment` and `BillsTrendSummary` to `src/services/query/models.py`.
  - Implement `get_bills_trend_data` in `src/services/query/service.py` with rolling 3-month window arithmetic, in-memory decryption of `ScheduledBill` amounts, safe delta calculation, and zero-division protection.
- **Phase 2: Formatters**:
  - Implement `format_bills_trend_badge` and `format_bills_trend_card` in `src/services/query/formatters.py`.
  - Embed trend badge directly below `📌 Total Pending` in `format_bills_summary`.
- **Phase 3: Handlers & Webhook Routing**:
  - Add `[ 📊 3-Mo Trend ]` button to `build_bills_keyboard` in `src/services/handlers/bill_handler.py`.
  - Implement `build_bills_trend_card` in `bill_handler.py`.
  - Support `/bills trend` and `/bills historia` in `CommandHandler`.
  - Route `bills_t:` callback in `src/api/routes/telegram.py` using `edit_message_text`.
- **Phase 4: Automated Testing**:
  - Unit tests for edge cases (`tests/services/test_bills_trend.py`).
  - Integration tests for callback routing (`tests/api/test_telegram_bills_interactive.py`).

### Debug Log
- Verified calendar window math across year wrap-around boundaries (e.g. January correctly querying Nov/Dec of previous year).
- Guarded delta calculations with `prev_total > 0` condition to prevent `ZeroDivisionError`.
- Confirmed static label invariance ("3-Mo Fixed" / "Gastos Fijos (3M)") and resilient `(No info)` / `(Sin datos)` fallback text.
- Validated webhook routing for `bills_t:` prefix with `answer_callback_query` and in-place `edit_message_text`.

### Completion Notes
- All 6 acceptance criteria and 6 task groups implemented and verified.
- Unit and integration tests passing: 6/6 in `tests/services/test_bills_trend.py`, 13/13 in `tests/api/test_telegram_bills_interactive.py`.
- Existing regression test suite passing: 13/13 in `test_bill_handler.py`, `test_scheduled_bills.py`, and `test_bill_settlement_and_status.py`.

---

## File List
- `src/services/query/models.py` (Modified)
- `src/services/query/service.py` (Modified)
- `src/services/query/formatters.py` (Modified)
- `src/services/handlers/bill_handler.py` (Modified)
- `src/services/handlers/command_handler.py` (Modified)
- `src/api/routes/telegram.py` (Modified)
- `tests/services/test_bills_trend.py` (Created)
- `tests/api/test_telegram_bills_interactive.py` (Modified)
- `_bmad-output/planning-artifacts/prd.md` (Modified)
- `_bmad-output/planning-artifacts/epics.md` (Modified)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (Modified)
- `_bmad-output/implementation-artifacts/24-1-3-month-fixed-expenses-trend-and-in-place-resume.md` (Modified)

---

## Change Log
- 2026-09-30: Initial story specification created and sprint status updated to in-progress.
- 2026-09-30: Completed implementation of 3-month fixed commitments trend, badge formatters, interactive card toggle, and test suite. Moved status to review.
- 2026-09-30: Code review complete with 6 patches applied (dominant currency segregation, language detection, edit error resilience, emoji alignment, timeframe propagation). Status moved to done.

---

## Status
done


