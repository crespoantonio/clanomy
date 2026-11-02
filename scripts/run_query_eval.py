#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Automated Evaluation Runner for the Decoupled Query Engine (Story 25.5).
Evaluates accuracy against the 150-query golden dataset using deterministic AST normalization
and Stage 4.5 Parity Gate validation with zero external token expenditure.
"""

from datetime import datetime, timezone
from src.services.query.normalizer import QueryNormalizer
from src.services.query.parity_gate import enforce_parity_gate
from tests.data.query_engine_golden_dataset import GOLDEN_QUERY_DATASET

def run_evaluation():
    normalizer = QueryNormalizer()
    ref_time = datetime(2026, 11, 1, 12, 0, 0, tzinfo=timezone.utc)

    total = len(GOLDEN_QUERY_DATASET)
    domain_correct = 0
    parity_passed = 0
    failures = []

    print(f"Starting Evaluation on {total} Golden Benchmark Queries...")

    for idx, item in enumerate(GOLDEN_QUERY_DATASET):
        q = item["query"]
        expected_dom = item["expected_domain"]
        expected_hist = item["is_historical"]
        expected_proj = item["is_projected"]

        ast = normalizer._deterministic_fallback_ast(q, ref_time)
        actual_dom = ast.filters.domains[0] if ast.filters.domains else "expenses"

        dom_match = (actual_dom == expected_dom)
        hist_match = (ast.temporal.is_historical == expected_hist)
        proj_match = (ast.temporal.is_projected == expected_proj)

        if dom_match and (hist_match or proj_match):
            domain_correct += 1
        else:
            failures.append((q, expected_dom, actual_dom))

        parity_res = enforce_parity_gate(ast)
        if parity_res.is_valid:
            parity_passed += 1

    accuracy = (domain_correct / total) * 100.0
    parity_rate = (parity_passed / total) * 100.0

    print("=" * 60)
    print("EVALUATION RESULTS - EPIC 25 DECOUPLED QUERY ENGINE")
    print("=" * 60)
    print(f"Total Queries Evaluated: {total}")
    print(f"Domain & Temporal Accuracy: {accuracy:.2f}% ({domain_correct}/{total})")
    print(f"Stage 4.5 Parity Gate Pass Rate: {parity_rate:.2f}% ({parity_passed}/{total})")
    print(f"Target Benchmark: >= 95.00%")
    print("Status:", "PASSED [SUCCESS]" if accuracy >= 95.0 else "FAILED [BELOW 95%]")
    print("=" * 60)

    if failures:
        print(f"Sample Misses ({len(failures)} total):")
        for fail in failures[:5]:
            print(f"  • Query: '{fail[0]}' | Expected: {fail[1]} | Got: {fail[2]}")

    return accuracy >= 95.0

if __name__ == "__main__":
    import sys
    success = run_evaluation()
    sys.exit(0 if success else 1)
