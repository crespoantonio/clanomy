# Story 14.3: Multi-Currency Ledger Aggregation per Member

**Epic:** Epic 14 - Pre-Built Fast-Path Commands & Hybrid Quota Model
**Status:** Completed
**Author:** Amelia & Winston
**Date:** 2026-09-01

---

## 1. Overview & Context

Expats and international households often manage transactions in multiple currencies (e.g. USD savings and ARS or EUR local expenses). Mixing un-converted currencies into a single total corrupts financial reporting. Clanomy enforces strict currency segregation for both household totals and member-specific breakdowns.

---

## 2. Technical Implementation

### 2.1 Model Expansion
- In `src/services/query/models.py`:
  - Expanded `MemberSpending`:
    ```python
    income_currency_totals: Dict[str, float] = Field(default_factory=dict)
    expense_currency_totals: Dict[str, float] = Field(default_factory=dict)
    ```

### 2.2 Aggregation & Segregation
- In `src/services/query/aggregator.py`:
  - `aggregate_transactions()` and `aggregate_by_member()` maintain independent currency accumulators.
  - Transactions in distinct currencies are indexed by 3-letter ISO code (e.g. `USD`, `ARS`, `EUR`).

### 2.3 Output Formatting
- In `src/services/query/formatters.py`:
  - `format_currency_dict()` converts currency dictionaries into clean multi-currency strings (e.g. `$3,500.00 USD · $450.00 EUR`).
  - Zero-conversion guarantee: different currencies are never added together.

---

## 3. Verification & Acceptance

- Validated via `tests/services/test_command_handlers.py`.
- Verified multi-currency segregation across `/month`, `/me`, `/today`, and `/balance`.
