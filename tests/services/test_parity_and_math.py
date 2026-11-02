from decimal import Decimal
from uuid import uuid4
from datetime import datetime, timezone
from src.services.query.models import (
    NormalizedQueryAST,
    TemporalScope,
    EntityFilters,
    QueryOperation,
    DecryptedTransaction,
    DecryptedScheduledBill
)
from src.services.query.parity_gate import enforce_parity_gate
from src.services.query.math_engine import DeterministicMathEngine, to_decimal

def test_to_decimal_precision():
    d1 = to_decimal(19.999)
    assert d1 == Decimal("20.00")
    d2 = to_decimal("150.50")
    assert d2 == Decimal("150.50")

def test_parity_gate_success():
    ast = NormalizedQueryAST(
        raw_query="bills for electricity",
        temporal=TemporalScope(),
        filters=EntityFilters(
            domains=["bills"],
            category_hints=["Rent/Bills"],
            concept_hints=["electricity"]
        ),
        operation=QueryOperation()
    )
    result = enforce_parity_gate(
        ast=ast,
        resolved_category="Rent/Bills",
        resolved_concepts=["Electricidad Edesur"]
    )
    assert result.is_valid is True
    assert len(result.gaps) == 0

def test_parity_gate_unmatched_member_gap():
    ast = NormalizedQueryAST(
        raw_query="spending by unknown_person",
        temporal=TemporalScope(),
        filters=EntityFilters(
            domains=["expenses"],
            target_member="unknown_person"
        ),
        operation=QueryOperation()
    )
    result = enforce_parity_gate(
        ast=ast,
        resolved_member=None
    )
    assert result.is_valid is False
    assert len(result.gaps) == 1
    assert result.gaps[0].reason == "UNMATCHED_MEMBER"

def test_deterministic_math_engine_aggregation():
    family_id = uuid4()
    user_id = uuid4()
    now = datetime.now(timezone.utc)

    transactions = [
        DecryptedTransaction(
            id=uuid4(),
            family_id=family_id,
            user_id=user_id,
            amount=100.0,
            currency="USD",
            concept="Electricidad",
            category="Rent/Bills",
            type="expense",
            timestamp=now
        ),
        DecryptedTransaction(
            id=uuid4(),
            family_id=family_id,
            user_id=user_id,
            amount=50.0,
            currency="USD",
            concept="Internet",
            category="Rent/Bills",
            type="expense",
            timestamp=now
        ),
        DecryptedTransaction(
            id=uuid4(),
            family_id=family_id,
            user_id=user_id,
            amount=15000.0,
            currency="ARS",
            concept="Supermercado",
            category="Food/Drink",
            type="expense",
            timestamp=now
        )
    ]

    scheduled_bills = [
        DecryptedScheduledBill(
            id=uuid4(),
            family_id=family_id,
            user_id=user_id,
            amount=60.0,
            currency="USD",
            concept="Gas",
            category="Rent/Bills",
            due_date=now,
            status="pending",
            created_at=now
        )
    ]

    metrics = DeterministicMathEngine.aggregate_dataset(transactions, scheduled_bills)
    
    # Currency segregation check
    assert "USD" in metrics
    assert "ARS" in metrics
    assert len(metrics) == 2

    usd = metrics["USD"]
    # Total = 100 + 50 + 60 = 210
    assert usd.total_amount == Decimal("210.00")
    assert usd.paid_amount == Decimal("150.00")
    assert usd.pending_amount == Decimal("60.00")
    assert usd.count == 3
    assert usd.average_amount == Decimal("70.00")

    ars = metrics["ARS"]
    assert ars.total_amount == Decimal("15000.00")
    assert ars.count == 1

def test_deterministic_delta_calculation():
    diff, pct = DeterministicMathEngine.calculate_delta(Decimal("100.00"), Decimal("125.00"))
    assert diff == Decimal("25.00")
    assert pct == Decimal("25.00")

    # Zero-division guard
    diff0, pct0 = DeterministicMathEngine.calculate_delta(Decimal("0.00"), Decimal("50.00"))
    assert diff0 == Decimal("50.00")
    assert pct0 is None
