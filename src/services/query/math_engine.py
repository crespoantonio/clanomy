from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Optional, Tuple, Sequence
from dataclasses import dataclass, field
from src.services.query.models import DecryptedTransaction, DecryptedScheduledBill

def to_decimal(val: float | int | str | Decimal) -> Decimal:
    """Converts a numeric value to a strict Decimal with 2 decimal places."""
    if isinstance(val, Decimal):
        return val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return Decimal(str(val)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

@dataclass
class AggregatedFinancialMetrics:
    currency: str
    total_amount: Decimal = Decimal("0.00")
    paid_amount: Decimal = Decimal("0.00")
    pending_amount: Decimal = Decimal("0.00")
    count: int = 0
    average_amount: Decimal = Decimal("0.00")
    category_totals: Dict[str, Decimal] = field(default_factory=dict)
    concept_totals: Dict[str, Decimal] = field(default_factory=dict)

class DeterministicMathEngine:
    """
    Stage 5 Business Engine:
    Executes all financial arithmetic strictly in deterministic Python using Decimal.
    Structural invariant: The LLM is NEVER allowed to compute math or financial totals.
    """

    @staticmethod
    def aggregate_dataset(
        transactions: Sequence[DecryptedTransaction] = (),
        scheduled_bills: Sequence[DecryptedScheduledBill] = (),
        primary_currency: Optional[str] = None
    ) -> Dict[str, AggregatedFinancialMetrics]:
        """
        Aggregates financial records with 100% strict currency segregation.
        Returns a mapping of currency -> AggregatedFinancialMetrics.
        """
        metrics_by_currency: Dict[str, AggregatedFinancialMetrics] = {}

        # 1. Aggregate Transactions
        for tx in transactions:
            curr = (tx.currency or "USD").upper().strip()
            if curr not in metrics_by_currency:
                metrics_by_currency[curr] = AggregatedFinancialMetrics(currency=curr)

            amt = to_decimal(tx.amount)
            m = metrics_by_currency[curr]
            m.total_amount += amt
            m.paid_amount += amt
            m.count += 1

            cat = tx.category or "Other"
            m.category_totals[cat] = m.category_totals.get(cat, Decimal("0.00")) + amt

            conc = (tx.concept or "General").strip()
            m.concept_totals[conc] = m.concept_totals.get(conc, Decimal("0.00")) + amt

        # 2. Aggregate Scheduled Bills
        for bill in scheduled_bills:
            curr = (bill.currency or "USD").upper().strip()
            if curr not in metrics_by_currency:
                metrics_by_currency[curr] = AggregatedFinancialMetrics(currency=curr)

            amt = to_decimal(bill.amount)
            m = metrics_by_currency[curr]
            m.total_amount += amt
            m.count += 1

            if bill.status == "paid":
                m.paid_amount += amt
            else:
                m.pending_amount += amt

            cat = bill.category or "Rent/Bills"
            m.category_totals[cat] = m.category_totals.get(cat, Decimal("0.00")) + amt

            conc = (bill.concept or "General").strip()
            m.concept_totals[conc] = m.concept_totals.get(conc, Decimal("0.00")) + amt

        # 3. Compute Averages
        for m in metrics_by_currency.values():
            if m.count > 0:
                m.average_amount = (m.total_amount / Decimal(m.count)).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )

        return metrics_by_currency

    @staticmethod
    def calculate_delta(a: Decimal, b: Decimal) -> Tuple[Decimal, Optional[Decimal]]:
        """
        Calculates absolute delta (b - a) and percentage change ((b - a) / a) * 100.
        Safeguards strictly against division-by-zero.
        """
        diff = b - a
        if a <= Decimal("0.00"):
            return diff, None
        delta_pct = ((diff / a) * Decimal("100.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return diff, delta_pct
