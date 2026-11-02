---
story_id: "25.3"
epic_id: "25"
title: "Deterministic Query Builder, Code-Level Parity Gate & Math Engine"
status: "done"
priority: "high"
author: "Amelia, Winston & Murat"
date: "2026-11-01"
---

# Story 25.3: Deterministic Query Builder, Code-Level Parity Gate & Math Engine

## 1. Overview & Context

A major vulnerability in conversational financial assistants is arithmetic hallucination or silent entity starvation, where an LLM drops a requested filter (e.g. ignoring a requested month or participant) or calculates totals with subtle rounding errors.

This story implements Stage 4.5 (Code-Level Parity Gate) and Stage 5 (Deterministic Math Engine):
1. **Code-Level Parity Gate:** Programmatic invariant asserting that 100% of extracted entities and constraints in the AST are accounted for prior to query execution.
2. **Deterministic Math Engine:** Pure Python calculation engine using `Decimal` arithmetic for aggregations, currency segregation, delta calculations, and percentage shifts.

---

## 2. User Story & Acceptance Criteria

### User Story
As a User,  
I want all mathematical calculations and data filters to be executed strictly in deterministic code,  
So that the AI never invents numbers, distorts balances, or silently drops requested query constraints.

### Acceptance Criteria
- [x] **AC 25.3.1 (Code-Level Parity Gate):**
  - Implement `enforce_parity_gate(ast: NormalizedQueryAST, resolved_plan: ExecutionPlan) -> ValidationResult`.
  - Asserts that all extracted category hints, entity names, and time constraints are accounted for in the execution plan.
  - If an unaccounted entity exists, flags a structured gap rather than executing a silent partial query.
- [x] **AC 25.3.2 (Pure Python Decimal Math):**
  - All sums, averages, medians, and deltas are calculated using Python `Decimal` with 2 decimal places.
  - Strict currency isolation: totals are grouped by currency; no mixing or arbitrary cross-currency additions.
- [x] **AC 25.3.3 (SQL Predicate Pushdown for Plaintext):**
  - Pushes down `family_id`, timestamps, due dates, and statuses to SQL queries for maximum performance.

---

## 3. Tasks / Subtasks
- [x] **Task 1: Parity Gate Validator** (AC: 25.3.1)
  - [x] Implement `enforce_parity_gate` in `src/services/query/parity_gate.py`.
- [x] **Task 2: Deterministic Calculation Engine** (AC: 25.3.2)
  - [x] Implement calculation aggregators in `src/services/query/math_engine.py` using `Decimal`.
  - [x] Ensure currency-segregated totals and safe delta calculations.
- [x] **Task 3: Unit Testing** (AC: All)
  - [x] Write unit tests in `tests/services/test_parity_gate.py` and `tests/services/test_math_engine.py`.
