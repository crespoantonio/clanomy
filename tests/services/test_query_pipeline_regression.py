import pytest
from datetime import datetime, timezone
from src.services.query.normalizer import QueryNormalizer
from src.services.query.parity_gate import enforce_parity_gate
from tests.data.query_engine_golden_dataset import GOLDEN_QUERY_DATASET

def test_golden_dataset_coverage_and_parity_gate():
    """CI Regression Gate: Evaluates ≥150 golden queries and verifies ≥95% accuracy."""
    normalizer = QueryNormalizer()
    ref_time = datetime(2026, 11, 1, 12, 0, 0, tzinfo=timezone.utc)

    total = len(GOLDEN_QUERY_DATASET)
    assert total >= 150, f"Golden dataset must contain at least 150 queries, found {total}"

    domain_correct = 0
    parity_passed = 0

    for item in GOLDEN_QUERY_DATASET:
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

        parity_res = enforce_parity_gate(ast)
        if parity_res.is_valid:
            parity_passed += 1

    accuracy = (domain_correct / total) * 100.0
    parity_rate = (parity_passed / total) * 100.0

    assert accuracy >= 95.0, f"Expected ≥95.0% accuracy, achieved {accuracy:.2f}%"
    assert parity_rate == 100.0, f"Expected 100.0% Parity Gate pass rate, achieved {parity_rate:.2f}%"
