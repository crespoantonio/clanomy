from datetime import datetime, timezone, timedelta
from typing import Optional
import json
import logging
import re
from src.core.llm import get_llm_provider
from src.core.llm.base import BaseLLMProvider
from src.core.ai_client import sanitize_prompt_input
from src.services.query.models import (
    NormalizedQueryAST,
    TemporalScope,
    EntityFilters,
    QueryOperation
)

logger = logging.getLogger(__name__)

AST_NORMALIZER_SYSTEM_PROMPT = """You are an expert bilingual (English & Spanish) financial query AST normalizer.
Your sole job is to decompose the user's natural language question into orthogonal dimensions:
1. TemporalScope (time window, start_date, end_date, is_historical, is_projected, granularity)
2. EntityFilters (domains: expenses, income, bills, savings, balance, transfers; category_hints, concept_hints, status, target_currency, target_member, scope: personal vs family)
3. QueryOperation (op: list, sum, average, comparison, trend, breakdown; group_by: none, category, member, month, day)

CRITICAL RULES:
- Do NOT confuse temporal directionality with domain.
  * "bills last 3 months" -> domain: ["bills"], is_historical: true, is_projected: false, op: list (or breakdown/sum if asking for total)
  * "upcoming bills" -> domain: ["bills"], is_historical: false, is_projected: true, op: list
  * "dining out this weekend vs last weekend" -> domain: ["expenses"], category_hints: ["Food/Drink"], op: comparison, is_compound: true
- Relative date resolution: Use the Reference Date from <system_context> to compute exact start_date and end_date (YYYY-MM-DD).
- Scope: Default to "family" unless the user explicitly asks about their personal finances ("my", "mis gastos", "tengo yo").
- Context isolation: You do not have database context. Do not invent entities not mentioned in the query.

MANDATORY OUTPUT FORMAT:
Output MUST be a single valid JSON object adhering to the NormalizedQueryAST schema."""

def _matches_any_word(words: tuple, text: str) -> bool:
    for w in words:
        pattern = r'\b' + re.escape(w) + r'\b'
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False

class QueryNormalizer:
    """Stage 1 Normalizer: Decomposes raw natural language into an orthogonal AST."""

    def __init__(self, provider: Optional[BaseLLMProvider] = None):
        self.provider = provider or get_llm_provider()

    async def normalize(
        self,
        text: str,
        reference_time: Optional[datetime] = None,
        tz_name: str = "UTC"
    ) -> NormalizedQueryAST:
        if not text or not text.strip():
            raise ValueError("Query text cannot be empty")

        ref_time = reference_time or datetime.now(timezone.utc)
        clean_text = sanitize_prompt_input(text.strip())
        current_date_str = ref_time.strftime("%Y-%m-%d")

        user_prompt = (
            "<system_context>\n"
            f"Reference Date: {current_date_str}\n"
            f"User Timezone: {tz_name}\n"
            "</system_context>\n\n"
            "Normalize this financial query into AST:\n"
            f"<user_input>\n{clean_text}\n</user_input>"
        )

        try:
            ast_json = await self.provider.complete_structured(
                system_prompt=AST_NORMALIZER_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                schema=NormalizedQueryAST,
                timeout=60.0
            )
            return NormalizedQueryAST.model_validate_json(ast_json)
        except Exception as e:
            logger.warning(f"AST Normalization failed: {e}. Falling back to deterministic AST.", exc_info=True)
            return self._deterministic_fallback_ast(text, ref_time)

    def _deterministic_fallback_ast(self, text: str, ref_time: datetime) -> NormalizedQueryAST:
        """Deterministic rule-based fallback when LLM is unavailable."""
        lower = text.lower().strip()
        is_historical = True
        is_projected = False
        domains = ["expenses"]
        op = "sum" if any(w in lower for w in ("how much", "cuanto", "cuánto", "total", "sum", "salio", "quemamos", "blow")) else "list"
        if "breakdown" in lower or "detalle" in lower:
            op = "breakdown" if "breakdown" in lower else "list"

        # 1. Balance & Cash Flow
        if _matches_any_word(("balance", "cash flow", "flujo", "quedó", "quedo", "leftover", "net", "disponible"), lower):
            domains = ["balance"]

        # 2. Savings & Wealth
        elif _matches_any_word(("saving", "savings", "ahorro", "ahorros", "patrimonio"), lower):
            domains = ["savings"]

        # 3. Income & Earnings
        elif _matches_any_word(("income", "earn", "salary", "ingreso", "ingresos", "sueldo", "cobré", "cobre", "cobrados", "cobrado", "payout", "dividend", "ventas"), lower):
            domains = ["income"]

        # 4. Bills & Fixed Commitments
        elif _matches_any_word((
            "bill", "bills", "factura", "facturas", "cuentas", "servicios",
            "electricity", "internet", "expensas", "luz", "gas", "utility", "utilities",
            "obligations", "commitments", "vencimiento", "vencimientos", "boletas", "boleta", "tarjeta"
        ), lower) or "bill detailz" in lower or "wat bills" in lower:
            domains = ["bills"]
            if _matches_any_word(("upcoming", "pending", "due", "owe", "scheduled", "por pagar", "por vencer", "vence", "próximas", "proximos", "proximas"), lower) or "r due" in lower:
                is_projected = True
                is_historical = False

        # Time window
        start_date = None
        end_date = ref_time.strftime("%Y-%m-%d")
        timeframe = "this_month"

        if "last 3 months" in lower or "ultimos 3 meses" in lower or "últimos 3 meses" in lower or "last 90 days" in lower or "three monthz" in lower:
            start_date = (ref_time - timedelta(days=90)).strftime("%Y-%m-%d")
            timeframe = "last_90_days"
        elif "last 6 months" in lower or "ultimos 6 meses" in lower or "últimos 6 meses" in lower:
            start_date = (ref_time - timedelta(days=180)).strftime("%Y-%m-%d")
            timeframe = "last_180_days"
        elif "this month" in lower or "este mes" in lower:
            start_date = ref_time.replace(day=1).strftime("%Y-%m-%d")
            timeframe = "this_month"
        elif "last month" in lower or "mes pasado" in lower:
            first_this_month = ref_time.replace(day=1)
            last_day_prev = first_this_month - timedelta(days=1)
            start_date = last_day_prev.replace(day=1).strftime("%Y-%m-%d")
            end_date = last_day_prev.strftime("%Y-%m-%d")
            timeframe = "last_month"

        scope = "personal" if any(w in lower for w in ("my", "mis", "yo", "tengo")) and not any(w in lower for w in ("we", "nuestro", "familia")) else "family"

        return NormalizedQueryAST(
            raw_query=text,
            temporal=TemporalScope(
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date,
                is_historical=is_historical,
                is_projected=is_projected
            ),
            filters=EntityFilters(
                domains=domains,
                scope=scope
            ),
            operation=QueryOperation(op=op)
        )
