---
story_id: "8.4"
epic_id: "8"
title: "Conversational Net Cash Flow & Income Queries (ASK Engine)"
status: "ready-for-dev"
priority: "high"
---

# Story 8.4: Conversational Net Cash Flow & Income Queries (ASK Engine)

## User Story
As a User,
I want to ask the bot about our earnings and net cash flow (e.g., "How much did we earn this month?", "What's our net balance?"),
So that I can understand our household financial standing without spreadsheets.

## Acceptance Criteria
- [ ] Update `src/services/query_service.py` and query resolution logic to support:
  - Income queries ("How much did we earn this week/month?")
  - Net balance queries ("What's our net balance?", "How much money do we have left over?")
  - Category earnings queries ("How much freelance income did I make?")
- [ ] Implement period aggregation math:
  - $\text{Total Income} = \sum \text{Transactions with } type = \text{"income"}$
  - $\text{Total Expenses} = \sum \text{Transactions with } type = \text{"expense"}$
  - $\text{Net Balance} = \text{Total Income} - \text{Total Expenses}$
  - $\text{Savings Rate} = (\text{Net Balance} / \text{Total Income}) \times 100$ (when $\text{Total Income} > 0$)
- [ ] Generate friendly, conversational LLM summaries conveying income, expenses, and net surplus/deficit.
- [ ] Add unit and integration tests in `tests/services/test_query_service.py` and `tests/api/test_queries.py`.

## Technical Notes
- Multi-currency: transactions are aggregated per currency or normalized to primary user currency.
- Multi-member family scoping: family queries aggregate transactions across all users with the same `family_id`.
