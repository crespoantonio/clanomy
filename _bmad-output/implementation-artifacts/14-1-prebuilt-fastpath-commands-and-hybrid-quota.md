# Story 14.1: Pre-Built Fast-Path Commands & Hybrid Quota Model

**Epic:** Epic 14 - Pre-Built Fast-Path Commands & Hybrid Quota Model
**Status:** Completed
**Author:** Amelia & Winston
**Date:** 2026-09-01

---

## 1. Overview & Context

To eliminate latency, avoid AI token consumption for routine dashboards, and remove "quota anxiety" for free users, Clanomy implements a **Hybrid Execution Architecture**:
- **Deterministic Commands (`/month`, `/me`, `/today`, `/bills`, `/balance`, `/undo`, `/help`):** Execute directly in Python & SQL in <40ms, cost $0 in AI tokens, and are 100% free and unlimited.
- **Natural Language AI Engine:** Free-form text and voice inputs execute via `AIOrchestrator` and consume from a 20 AI operation/month allowance in the Free Tier.
- **Family Member Segregation:** `/month` shows household totals alongside per-member earnings, expenses, and net balance.
- **Personal Isolation:** `/me` isolates the caller's individual cash flow and top categories even in a shared family workspace.
- **Multi-Currency Segregation:** Distinct currencies are tracked and reported separately without cross-currency addition.

---

## 2. Technical Changes

### 2.1 Configuration
- `src/core/subscription_config.py`: Updated `FREE_TIER_MONTHLY_LIMIT = 20`.

### 2.2 Models & Aggregation
- `src/services/query/models.py`: Added `income_currency_totals: Dict[str, float]` and `expense_currency_totals: Dict[str, float]` to `MemberSpending`.
- `src/services/query/aggregator.py`: Updated `aggregate_by_member()` to populate multi-currency dictionaries for each member.

### 2.3 Deterministic Formatters
- `src/services/query/formatters.py`: Implemented:
  - `format_month_summary`: Household overview with per-member segregation.
  - `format_me_summary`: Personal monthly overview with top 4 categories.
  - `format_today_summary`: Today's logged transactions.
  - `format_bills_summary`: Upcoming scheduled bills.
  - `format_balance_summary`: Cash flow and net balance.
  - `format_currency_dict`: Multi-currency string helper.

### 2.4 Command Handler & Routing
- `src/services/handlers/command_handler.py`: Implemented `CommandHandler` with fast-path execution methods.
- `src/api/routes/telegram.py`: Intercepted slash commands at the webhook entry point, routing directly to `CommandHandler` without touching quota counters.
- `src/services/ai_orchestrator.py`: Appended plan-aware Pro-Tips (*💡 Pro-tip: Type /month or /me...*) on natural language query responses.
- `src/services/handlers/family_handler.py`: Updated `/family` status to show `{used} / 20 (⚡ Commands are 100% free & unlimited)`.

---

## 3. Verification & Acceptance

- Unit tests created in `tests/services/test_command_handlers.py` validating:
  - Multi-currency aggregation per member.
  - `/month` output with member breakdown.
  - `/me` personal isolation.
  - `/today`, `/bills`, `/balance` formatting.
- Integration tests created in `tests/api/test_telegram_webhook_queries.py` validating webhook fast-path routing.
- All tests passing with 100% success rate.
