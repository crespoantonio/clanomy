import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4
from datetime import datetime, timezone
from decimal import Decimal

from src.services.query.normalizer import QueryNormalizer
from src.services.query.date_resolver import resolve_date_range
from src.services.query.synthesizer import QuerySynthesizer
from src.services.query.pipeline import DecoupledQueryPipeline
from src.services.query.models import (
    NormalizedQueryAST,
    TemporalScope,
    EntityFilters,
    QueryOperation,
    DecryptedScheduledBill
)
from src.services.query.dataset_router import RoutedDataset
from src.services.query.math_engine import DeterministicMathEngine, AggregatedFinancialMetrics
from src.services.agent.tools import execute_agent_tool, AgentContext

@pytest.mark.asyncio
async def test_normalizer_and_date_resolver_for_specific_date_query():
    """Validates Tony's query: 'Me podes sumar el total de mis vencimientos del 11/11?'"""
    normalizer = QueryNormalizer()
    ref_time = datetime(2026, 11, 2, 12, 0, 0, tzinfo=timezone.utc)

    query = "Me podes sumar el total de mis vencimientos del 11/11?"
    ast = normalizer._deterministic_fallback_ast(query, ref_time)

    assert ast.filters.domains == ["bills"]
    assert ast.operation.op == "sum"
    assert ast.temporal.start_date == "2026-11-11"
    assert ast.temporal.end_date == "2026-11-11"
    assert ast.temporal.is_projected is True

    start_t, end_t = resolve_date_range(
        ast.temporal.timeframe,
        ast.temporal.start_date,
        ast.temporal.end_date,
        reference_time=ref_time,
        future_inclusive=True
    )
    assert start_t is not None and end_t is not None
    assert start_t.strftime("%Y-%m-%d") == "2026-11-11"
    assert end_t.strftime("%Y-%m-%d") == "2026-11-11"

@pytest.mark.asyncio
async def test_synthesizer_parity_gate_and_fallback():
    """Validates Stage 4 Parity Gate asserts exact numeric agreement."""
    mock_llm = MagicMock()
    # LLM outputs text with correct number
    mock_llm.complete = AsyncMock(return_value="Tus vencimientos del 11/11 suman un total de <b>$103,000.00 ARS</b>.")
    synthesizer = QuerySynthesizer(provider=mock_llm)

    ast = NormalizedQueryAST(
        raw_query="Me podes sumar el total de mis vencimientos del 11/11?",
        temporal=TemporalScope(timeframe="2026-11-11", start_date="2026-11-11", end_date="2026-11-11", is_historical=False, is_projected=True),
        filters=EntityFilters(domains=["bills"]),
        operation=QueryOperation(op="sum")
    )

    now_utc = datetime.now(timezone.utc)
    bill1 = DecryptedScheduledBill(
        id=uuid4(), family_id=uuid4(), user_id=uuid4(), user_name="Tony", user_handle="@tony",
        amount=85000.0, currency="ARS", concept="Tarjeta Visa", category="Rent/Bills",
        due_date=datetime(2026, 11, 11, 0, 0, 0, tzinfo=timezone.utc), status="pending",
        created_at=now_utc
    )
    bill2 = DecryptedScheduledBill(
        id=uuid4(), family_id=uuid4(), user_id=uuid4(), user_name="Tony", user_handle="@tony",
        amount=18000.0, currency="ARS", concept="Internet", category="Rent/Bills",
        due_date=datetime(2026, 11, 11, 0, 0, 0, tzinfo=timezone.utc), status="pending",
        created_at=now_utc
    )

    routed = RoutedDataset(
        transactions=[],
        scheduled_bills=[bill1, bill2],
        domain="bills",
        is_historical=False,
        is_projected=True
    )

    metrics = DeterministicMathEngine.aggregate_dataset(scheduled_bills=[bill1, bill2], primary_currency="ARS")

    # 1. LLM output with correct amount passes
    resp = await synthesizer.synthesize("test", ast, routed, metrics, is_spanish=True)
    assert "103,000" in resp

    # 2. LLM output with hallucinated or wrong amount triggers deterministic fallback
    mock_llm.complete = AsyncMock(return_value="Tus facturas suman $500,000.00 ARS inventados.")
    resp_fallback = await synthesizer.synthesize("test", ast, routed, metrics, is_spanish=True)
    assert "103,000.00 ARS" in resp_fallback
    assert "Tarjeta Visa" in resp_fallback

@pytest.mark.asyncio
async def test_agentic_tool_query_bills_sync_function_compatibility():
    """Asserts that execute_tool handles synchronous service functions without TypeError."""
    mock_bills = [
        DecryptedScheduledBill(
            id=uuid4(), family_id=uuid4(), user_id=uuid4(), user_name="Tony", user_handle="@tony",
            amount=37000.0, currency="ARS", concept="Luz", category="Rent/Bills",
            due_date=datetime(2026, 11, 11, 0, 0, 0, tzinfo=timezone.utc), status="pending",
            created_at=datetime.now(timezone.utc)
        )
    ]

    context = AgentContext(
        user_id=uuid4(),
        family_id=uuid4(),
        user_name="Tony",
        family_name="Familia",
        default_currency="ARS"
    )

    with patch("src.services.agent.tools.QueryService") as MockQS:
        qs_instance = MockQS.return_value
        # Real synchronous method return (NOT AsyncMock)
        qs_instance._fetch_and_decrypt_scheduled_bills = MagicMock(return_value=mock_bills)
        qs_instance._resolve_date_range = MagicMock(return_value=(
            datetime(2026, 11, 11, 0, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 11, 11, 23, 59, 59, tzinfo=timezone.utc)
        ))

        res = await execute_agent_tool("query_bills", {"timeframe": "11/11", "status": "pending"}, context)
        assert res["status"] == "success"
        assert res["count"] == 1
        assert res["total_pending_primary"] == 37000.0
