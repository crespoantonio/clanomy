---
story_id: "8.5"
epic_id: "8"
title: "Notion Mirroring & Export Updates for Income Records"
status: "ready-for-dev"
priority: "medium"
---

# Story 8.5: Notion Mirroring & Export Updates for Income Records

## User Story
As a User,
I want income records to be synced to my Notion database and included in my GDPR exports,
So that my external dashboards and data backups have a complete, accurate record of my finances.

## Acceptance Criteria
- [ ] Update `src/services/notion_mirror.py` to push `Type` property (`Income` vs `Expense`) to Notion database pages.
- [ ] Ensure Notion mirroring handles both positive income amounts and expenses gracefully.
- [ ] Update CSV and JSON export routines in `src/services/export_service.py` or API routes to include `Type` column:
  - Header: `["Date", "Type", "Amount", "Currency", "Concept", "Category"]`
  - Values: `"expense"` or `"income"`
- [ ] Add unit tests in `tests/services/test_notion_mirror.py` and `tests/services/test_export.py`.

## Technical Notes
- For Notion databases, if the `Type` select column doesn't exist, log a non-fatal warning or create it if API schema permissions allow, falling back to writing to page properties without breaking execution.
