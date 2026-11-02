import logging
from typing import Optional
from uuid import UUID
from datetime import datetime, timezone

from src.services.query.normalizer import QueryNormalizer
from src.services.query.dataset_router import DatasetRouter
from src.services.query.math_engine import DeterministicMathEngine
from src.services.query.synthesizer import QuerySynthesizer
from src.services.query.date_resolver import resolve_date_range

logger = logging.getLogger(__name__)

class DecoupledQueryPipeline:
    """
    Decoupled Multi-Stage Query Engine Pipeline (Epic 25 - Option B Architecture):
    
    Stage 1: LLM AST Normalizer
        - Deconstructs natural language into orthogonal QueryAST (TemporalScope, EntityFilters, QueryOperation).
    Stage 1.5: Date Range Resolver
        - Resolves relative or explicit dates (e.g. '11/11', 'this_month') into exact UTC bounds.
    Stage 2: Zero-Knowledge Dataset Router
        - Routes to ScheduledBill, Transaction, or both with tenant isolation and AES-256 decryption.
    Stage 3: Deterministic Math Engine
        - Computes Decimal financial totals, pending balances, counts, and category breakdowns.
    Stage 4: Synthesis & AI Verification Gate
        - Synthesizes empathetic conversational response and asserts numeric parity against ground truth.
    """

    def __init__(
        self,
        normalizer: Optional[QueryNormalizer] = None,
        router: Optional[DatasetRouter] = None,
        synthesizer: Optional[QuerySynthesizer] = None,
        math_engine: Optional[DeterministicMathEngine] = None
    ):
        self.normalizer = normalizer or QueryNormalizer()
        self.router = router or DatasetRouter()
        self.synthesizer = synthesizer or QuerySynthesizer()
        self.math_engine = math_engine or DeterministicMathEngine()

    async def execute(
        self,
        text: str,
        family_id: UUID,
        user_id: Optional[UUID] = None,
        user_name: str = "User",
        default_currency: str = "USD",
        tz_name: str = "UTC",
        reference_time: Optional[datetime] = None,
        is_spanish: Optional[bool] = None
    ) -> str:
        ref_time = reference_time or datetime.now(timezone.utc)
        logger.info(f"[DecoupledQueryPipeline] Executing query: {text!r} for family {family_id}")

        # Stage 1: AST Normalizer
        ast = await self.normalizer.normalize(text, reference_time=ref_time, tz_name=tz_name)

        # Stage 1.5: Date Range Resolution
        tf = ast.temporal.timeframe or "this_month"
        start_time, end_time = resolve_date_range(
            tf,
            ast.temporal.start_date,
            ast.temporal.end_date,
            reference_time=ref_time,
            tz_name=tz_name,
            future_inclusive=ast.temporal.is_projected
        )

        # Stage 2: Dataset Router
        routed = self.router.route_and_fetch(
            family_id=family_id,
            ast=ast,
            start_time=start_time,
            end_time=end_time
        )

        # Stage 3: Deterministic Math Engine
        metrics_by_currency = self.math_engine.aggregate_dataset(
            transactions=routed.transactions,
            scheduled_bills=routed.scheduled_bills,
            primary_currency=default_currency
        )

        # Stage 4: Synthesis & Verification Gate
        is_es = is_spanish if is_spanish is not None else True
        response = await self.synthesizer.synthesize(
            query_text=text,
            ast=ast,
            routed=routed,
            metrics_by_currency=metrics_by_currency,
            user_name=user_name,
            default_currency=default_currency,
            is_spanish=is_es
        )

        logger.info(f"[DecoupledQueryPipeline] Successfully synthesized verified response ({len(response)} chars)")
        return response
