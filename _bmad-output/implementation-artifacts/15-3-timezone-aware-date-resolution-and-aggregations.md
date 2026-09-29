# Story 15.3: Timezone-Aware Date Resolution & Aggregations

**Epic:** Epic 15 - Household Timezone Support & Dynamic Temporal Resolution
**Status:** Completed
**Author:** Amelia & Winston
**Date:** 2026-09-01

---

## 1. Overview & Context

Transactions logged late in the evening or early in the morning in timezones with large UTC offsets (e.g. UTC-3 in South America, UTC+9 in Asia) must never be misattributed to the wrong day or month.

---

## 2. Technical Implementation

### 2.1 Date Resolver Engine
- In `src/services/query/date_resolver.py`:
  - `resolve_date_range(query_text, user_tz)` parses relative temporal words (*"today"*, *"yesterday"*, *"this month"*, *"hoy"*, *"ayer"*, *"este mes"*).
  - Computes localized start-of-day (`00:00:00`) and end-of-day (`23:59:59.999999`) in the target timezone.
  - Converts localized boundaries into UTC datetimes for SQL querying.

### 2.2 Integration with Query Service
- In `src/services/query/service.py`:
  - `QueryService.get_spending_summary()` accepts localized boundaries and filters transactions accurately.

---

## 3. Verification & Acceptance

- Validated with unit tests in `tests/services/test_timezone_resolution.py`.
- Verified midnight boundaries and day transitions across different timezone offsets.
