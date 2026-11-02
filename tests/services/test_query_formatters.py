from decimal import Decimal
from dataclasses import dataclass
from src.services.query.formatters import format_decoupled_query_card
from src.services.query.math_engine import AggregatedFinancialMetrics

def test_format_decoupled_query_card_with_assumption():
    metrics = {
        "USD": AggregatedFinancialMetrics(
            currency="USD",
            total_amount=Decimal("180.00"),
            paid_amount=Decimal("120.00"),
            pending_amount=Decimal("60.00"),
            count=2
        )
    }
    items = [
        "<b>Electricidad</b>: $120.00 USD (paid)",
        "<b>Internet</b>: $60.00 USD (pending)"
    ]
    card = format_decoupled_query_card(
        title="Bills & Utilities",
        timeframe_label="last 3 months",
        metrics_by_currency=metrics,
        items_breakdown=items,
        assumption_note="Showing settled bill transactions and paid obligations for the past period.",
        is_spanish=False
    )

    assert "Bills &amp; Utilities (last 3 months)" in card
    assert "ℹ️ Showing settled bill transactions" in card
    assert "Electricidad" in card
    assert "180.00 USD" in card
    assert "120.00 paid, 60.00 pending" in card

def test_format_decoupled_query_card_empty():
    card = format_decoupled_query_card(
        title="Bills",
        timeframe_label="last 3 months",
        metrics_by_currency={},
        items_breakdown=[],
        is_spanish=True
    )
    assert "Sin registros encontrados para este período" in card
