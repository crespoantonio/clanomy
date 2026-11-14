---
story_id: "26.1"
epic_id: "26"
title: "Query Synthesizer Dynamic Context Budgeting & Exemplar Pruning"
status: "done"
priority: "high"
author: "Winston, Amelia, Murat & Mary"
date: "2026-11-14"
---

# Story 26.1: Query Synthesizer Dynamic Context Budgeting & Exemplar Pruning

## 1. Overview & Context

During the Context Engineering audit, the engineering team identified an unbounded context growth vulnerability in `src/services/query/synthesizer.py`:
- In lines 194–219, `routed.transactions` and `routed.scheduled_bills` are serialized into strings and dumped into `<ground_truth_metrics>` without slice limits or pagination.
- When querying large datasets (e.g. 50 to 500+ items across a 6-month period), all items are formatted into the prompt verbatim.
- This creates severe context inflation, risk of context overflow or middle-truncation on local models (Ollama 2k/4k context window), latency spikes, and unnecessary token burn.

This story implements dynamic context budgeting:
1. **Exemplar Bounding:** Caps individual transaction and bill descriptions in `<ground_truth_metrics>` to a deterministic maximum (Top 5 representative records sorted by amount descending).
2. **Context Note:** Appends an explicit summary note clarifying that the displayed items are representative exemplars, while the Currency Aggregations and category totals are mathematically exact across all records.
3. **Character Budget Cap:** Enforces a maximum character volume on `ground_truth_context` as a defense-in-depth guardrail.

---

## 2. User Story & Acceptance Criteria

### User Story
As a Clanomy User and System Architect,  
I want the Stage 4 Query Synthesizer to enforce dynamic context budgeting by capping itemized transaction exemplars to the top 5 records alongside comprehensive mathematical aggregations,  
So that queries across large ledgers execute with sub-3s latency, zero context overflow, and minimized token consumption on both local and cloud models.

### Acceptance Criteria
- [x] **AC 26.1.1 (Exemplar Bounding):** In `QuerySynthesizer.synthesize`, limit individual transaction and bill item descriptions to at most 5 representative items, sorted by amount descending.
- [x] **AC 26.1.2 (Exemplar Summary Disclosure):** If total records exceed 5, append a clear structural note in `<ground_truth_metrics>` indicating the number of displayed exemplars vs total records, while affirming that aggregate metrics are exhaustive.
- [x] **AC 26.1.3 (Mathematical Aggregation Invariance):** Currency aggregations (`m.total_amount`, `m.pending_amount`, `m.count`, and `m.category_totals`) must remain comprehensive and calculated across 100% of matching dataset items.
- [x] **AC 26.1.4 (Prompt Character Cap):** Enforce a maximum character limit (`MAX_GROUND_TRUTH_CHARS = 4000`) on the ground truth context block.
- [x] **AC 26.1.5 (Backward Compatibility & Fallback):** The deterministic fallback and AI Parity Gate continue to function with 100% test pass rate.
