---
story_id: "25.4"
epic_id: "25"
title: "Conversational Fallback, Assumption Disclosure & Telegram Formatting"
status: "done"
priority: "high"
author: "John, Sally & Paige"
date: "2026-11-01"
---

# Story 25.4: Conversational Fallback, Assumption Disclosure & Telegram Formatting

## 1. Overview & Context

When ambiguity arises in user queries (e.g., whether "bills" refers to paid utilities vs scheduled commitments, or which specific family member was intended), traditional agent pipelines often block the user with interrogation questions ("Did you mean X or Y?"). In Telegram, this creates friction and frustrates users.

This story implements the Product Rule for Read-Only Ambiguity:
1. **Answer with Default & Disclose Assumption:** Execute the most probable intent immediately, state the assumption clearly in the header, and offer instant pivot buttons.
2. **Interactive Telegram Cards:** Clean HTML formatting with inline buttons for quick toggles (e.g. `[ 📅 View Upcoming Bills ]`, `[ 📊 3-Mo Trend ]`).

---

## 2. User Story & Acceptance Criteria

### User Story
As a Telegram User,  
I want immediate, actionable answers even when my query has minor ambiguity,  
So that I get the financial insight I need without annoying interrogation messages.

### Acceptance Criteria
- [x] **AC 25.4.1 (Assumption Disclosure Banner):**
  - When an assumption is made (e.g., default historical window or bills domain), prepend a brief, friendly italic banner:
    - English: *ℹ️ Showing settled bills and utilities for the last 3 months.*
    - Spanish: *ℹ️ Mostrando facturas y servicios liquidados de los últimos 3 meses.*
- [x] **AC 25.4.2 (Interactive Pivot Buttons):**
  - Under the formatted response card, render contextual inline keyboard buttons allowing the user to pivot with a single tap (e.g. switch between Historical vs Upcoming).
- [x] **AC 25.4.3 (Consistent HTML Card Formatting):**
  - Clean Telegram HTML styling (`<b>`, `<code>`, `<i>`) with proper HTML entity escaping (`html.escape`).

---

## 3. Tasks / Subtasks
- [x] **Task 1: Formatter & Assumption Generator** (AC: 25.4.1, 25.4.3)
  - [x] Add assumption badge generators and card builders in `src/services/query/formatters.py`.
- [x] **Task 2: Telegram Pivot Keyboards & Callback Handlers** (AC: 25.4.2)
  - [x] Implement callback query routing in `src/api/routes/telegram.py` for query pivot actions.
- [x] **Task 3: Unit Testing** (AC: All)
  - [x] Test formatting output and keyboard structure in `tests/services/test_query_formatters.py`.
