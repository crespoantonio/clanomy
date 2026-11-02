import pytest
from datetime import datetime, timezone
from src.services.query.models import (
    NormalizedQueryAST,
    TemporalScope,
    EntityFilters,
    QueryOperation
)
from src.services.query.normalizer import QueryNormalizer

def test_ast_models_instantiation():
    ast = NormalizedQueryAST(
        raw_query="Can you show me the details of my bills last 3 months",
        temporal=TemporalScope(
            timeframe="last_90_days",
            start_date="2026-08-01",
            end_date="2026-11-01",
            is_historical=True,
            is_projected=False
        ),
        filters=EntityFilters(
            domains=["bills"],
            scope="personal"
        ),
        operation=QueryOperation(
            op="list"
        )
    )
    assert ast.raw_query.startswith("Can you show")
    assert ast.temporal.is_historical is True
    assert ast.temporal.is_projected is False
    assert ast.filters.domains == ["bills"]
    assert ast.operation.op == "list"

def test_ast_to_legacy_intent_adapter_historical_bills():
    ast = NormalizedQueryAST(
        raw_query="bills last 3 months",
        temporal=TemporalScope(
            timeframe="last_90_days",
            is_historical=True,
            is_projected=False
        ),
        filters=EntityFilters(domains=["bills"]),
        operation=QueryOperation(op="list")
    )
    legacy = ast.to_legacy_parsed_intent()
    assert legacy.intent == "query_spending"
    assert legacy.category == "Rent/Bills"

def test_ast_to_legacy_intent_adapter_upcoming_bills():
    ast = NormalizedQueryAST(
        raw_query="upcoming bills",
        temporal=TemporalScope(
            timeframe="this_month",
            is_historical=False,
            is_projected=True
        ),
        filters=EntityFilters(domains=["bills"]),
        operation=QueryOperation(op="list")
    )
    legacy = ast.to_legacy_parsed_intent()
    assert legacy.intent == "upcoming_bills"

def test_deterministic_fallback_ast():
    qn = QueryNormalizer()
    ref = datetime(2026, 11, 1, 12, 0, 0, tzinfo=timezone.utc)
    ast = qn._deterministic_fallback_ast("Can you show me the details of my bills last 3 months", ref)
    assert ast.filters.domains == ["bills"]
    assert ast.temporal.is_historical is True
    assert ast.temporal.is_projected is False
    assert ast.temporal.start_date == "2026-08-03"
    assert ast.operation.op == "list"
