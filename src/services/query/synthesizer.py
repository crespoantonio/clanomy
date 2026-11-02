from decimal import Decimal
from typing import Dict, Optional, List, Any
import logging
import re
import html

from src.core.llm import get_llm_provider
from src.core.llm.base import BaseLLMProvider
from src.services.query.models import (
    NormalizedQueryAST,
    DecryptedScheduledBill,
    DecryptedTransaction
)
from src.services.query.dataset_router import RoutedDataset
from src.services.query.math_engine import AggregatedFinancialMetrics

logger = logging.getLogger(__name__)

SYNTHESIZER_SYSTEM_PROMPT = """You are Clanomy's financial AI assistant.
Your job is to answer the user's financial question warmly, clearly, and concisely, using ONLY the provided deterministic ground-truth data.

CRITICAL INVARIANTS:
1. STRICT GROUND TRUTH: All totals, amounts, counts, and dates MUST match the figures in <ground_truth_metrics> verbatim. NEVER calculate, estimate, modify, or round numbers differently.
2. TRANSPARENCY:
   - If the user asks for a sum or total, state the total prominently.
   - Mention the specific matching items that contribute to that sum.
   - If no items match, politely and clearly state that no records were found for that date/period.
3. LANGUAGE: Match the user's language (Spanish or English).
4. HTML FORMATTING: Use <b>bold</b> for amounts/totals and bullet points (•) for itemization. Do not use Markdown asterisks.
"""

def format_currency_amount(amount: Decimal | float, currency: str) -> str:
    """Formats a decimal amount with comma thousands and 2 decimal places."""
    return f"${amount:,.2f} {currency.upper()}"

class QuerySynthesizer:
    """
    Stage 4 Synthesis & AI Verification Gate:
    Synthesizes natural conversational responses grounded strictly in deterministic
    math calculations and validates that numbers in the response match ground truth.
    """

    def __init__(self, provider: Optional[BaseLLMProvider] = None):
        self.provider = provider or get_llm_provider()

    def build_deterministic_fallback(
        self,
        ast: NormalizedQueryAST,
        routed: RoutedDataset,
        metrics_by_currency: Dict[str, AggregatedFinancialMetrics],
        default_currency: str = "USD",
        is_spanish: bool = True
    ) -> str:
        """Generates a 100% deterministic, formatted response without LLM."""
        domain = ast.filters.domains[0] if ast.filters.domains else "expenses"
        total_count = sum(m.count for m in metrics_by_currency.values())
        timeframe_label = ast.temporal.timeframe or "este período"

        # Case 1: No records found
        if total_count == 0:
            if domain == "bills":
                return (
                    f"✅ <b>No tienes vencimientos registrados para {timeframe_label}.</b>"
                    if is_spanish
                    else f"✅ <b>You have no bills or dues scheduled for {timeframe_label}.</b>"
                )
            elif domain == "income":
                return (
                    f"ℹ️ <b>No se encontraron ingresos registrados para {timeframe_label}.</b>"
                    if is_spanish
                    else f"ℹ️ <b>No income recorded for {timeframe_label}.</b>"
                )
            else:
                return (
                    f"ℹ️ <b>No se encontraron gastos registrados para {timeframe_label}.</b>"
                    if is_spanish
                    else f"ℹ️ <b>No expenses recorded for {timeframe_label}.</b>"
                )

        # Case 2: Bills
        if domain == "bills":
            header = (
                f"📋 <b>Vencimientos ({timeframe_label}):</b>\n"
                if is_spanish
                else f"📋 <b>Scheduled Bills ({timeframe_label}):</b>\n"
            )
            item_lines = []
            for b in routed.scheduled_bills:
                due_str = b.due_date.strftime("%d/%m/%Y") if b.due_date else "Sin fecha"
                status_icon = "⏳" if b.status == "pending" else "✅"
                concept = html.escape(b.concept or "Gasto Fijo")
                amt_str = format_currency_amount(b.amount, b.currency or default_currency)
                item_lines.append(f"  • {concept}: <b>{amt_str}</b> — Vence: {due_str} {status_icon}")

            totals_lines = []
            for curr, m in metrics_by_currency.items():
                if m.pending_amount > Decimal("0.00"):
                    lbl = "Total pendiente" if is_spanish else "Total pending"
                    totals_lines.append(f"💰 <b>{lbl} ({curr}): {format_currency_amount(m.pending_amount, curr)}</b>")
                elif m.total_amount > Decimal("0.00"):
                    lbl = "Total a pagar" if is_spanish else "Total"
                    totals_lines.append(f"💰 <b>{lbl} ({curr}): {format_currency_amount(m.total_amount, curr)}</b>")

            parts = [header] + item_lines
            if totals_lines:
                parts.append("")
                parts.extend(totals_lines)
            return "\n".join(parts)

        # Case 3: Expenses / Spending
        header = (
            f"📊 <b>Gastos ({timeframe_label}):</b>\n"
            if is_spanish
            else f"📊 <b>Expenses ({timeframe_label}):</b>\n"
        )
        totals_lines = []
        for curr, m in metrics_by_currency.items():
            lbl = "Total gastado" if is_spanish else "Total spent"
            totals_lines.append(f"💰 <b>{lbl} ({curr}): {format_currency_amount(m.total_amount, curr)}</b> ({m.count} transacciones)")

        cat_breakdown = []
        for curr, m in metrics_by_currency.items():
            if m.category_totals:
                cat_breakdown.append("<b>Por categoría:</b>" if is_spanish else "<b>By Category:</b>")
                for cat, c_amt in sorted(m.category_totals.items(), key=lambda x: x[1], reverse=True)[:5]:
                    cat_breakdown.append(f"  • {html.escape(cat)}: {format_currency_amount(c_amt, curr)}")

        parts = [header] + totals_lines
        if cat_breakdown:
            parts.append("")
            parts.extend(cat_breakdown)
        return "\n".join(parts)

    def verify_response_parity(
        self,
        response_text: str,
        metrics_by_currency: Dict[str, AggregatedFinancialMetrics]
    ) -> bool:
        """
        AI Verification Gate:
        Verifies that totals from the math engine appear in the synthesized response.
        """
        if not response_text:
            return False

        # If 0 records, response shouldn't invent positive amounts
        total_count = sum(m.count for m in metrics_by_currency.values())
        if total_count == 0:
            return True

        # Check that at least one primary currency total or pending amount is reflected
        # e.g., if total is 37000.00, check for 37000, 37,000, or 37.000
        found_any_number = False
        for curr, m in metrics_by_currency.items():
            target_amount = m.pending_amount if m.pending_amount > Decimal("0.00") else m.total_amount
            amt_int = int(target_amount)
            # Variants: 37000, 37,000, 37.000
            patterns = [
                str(amt_int),
                f"{amt_int:,}",
                f"{amt_int:,}".replace(",", ".")
            ]
            if any(p in response_text for p in patterns):
                found_any_number = True
                break

        return found_any_number

    async def synthesize(
        self,
        query_text: str,
        ast: NormalizedQueryAST,
        routed: RoutedDataset,
        metrics_by_currency: Dict[str, AggregatedFinancialMetrics],
        user_name: str = "User",
        default_currency: str = "USD",
        is_spanish: bool = True
    ) -> str:
        """Synthesizes response with LLM and validates via the Parity Gate."""
        # 1. Always build the deterministic fallback first
        deterministic_resp = self.build_deterministic_fallback(
            ast=ast,
            routed=routed,
            metrics_by_currency=metrics_by_currency,
            default_currency=default_currency,
            is_spanish=is_spanish
        )

        total_count = sum(m.count for m in metrics_by_currency.values())
        if total_count == 0:
            return deterministic_resp

        # 2. Build structured ground truth prompt context
        items_descriptions = []
        for b in routed.scheduled_bills:
            due_str = b.due_date.strftime("%Y-%m-%d") if b.due_date else "none"
            items_descriptions.append(
                f"- Concept: {b.concept}, Amount: {b.amount} {b.currency}, Due Date: {due_str}, Status: {b.status}"
            )
        for t in routed.transactions:
            items_descriptions.append(
                f"- Concept: {t.concept}, Amount: {t.amount} {t.currency}, Category: {t.category}"
            )

        currency_metrics_summary = []
        for curr, m in metrics_by_currency.items():
            currency_metrics_summary.append(
                f"Currency: {curr} | Total: {m.total_amount} | Pending: {m.pending_amount} | Paid: {m.paid_amount} | Count: {m.count}"
            )

        ground_truth_context = (
            f"User Name: {user_name}\n"
            f"Query Timeframe: {ast.temporal.timeframe}\n"
            f"Domain: {ast.filters.domains}\n"
            f"Requested Operation: {ast.operation.op}\n"
            f"Total Records Count: {total_count}\n\n"
            "Currency Aggregations:\n" + "\n".join(currency_metrics_summary) + "\n\n"
            "Individual Records:\n" + ("\n".join(items_descriptions) if items_descriptions else "None")
        )

        user_prompt = (
            f"<user_question>\n{query_text}\n</user_question>\n\n"
            f"<ground_truth_metrics>\n{ground_truth_context}\n</ground_truth_metrics>"
        )

        try:
            llm_response = await self.provider.complete(
                system_prompt=SYNTHESIZER_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                timeout=60.0
            )
            clean_llm_response = (llm_response or "").strip()

            # 3. AI Verification / Parity Gate
            if self.verify_response_parity(clean_llm_response, metrics_by_currency):
                logger.info("[QuerySynthesizer] LLM synthesis verified by parity gate.")
                return clean_llm_response
            else:
                logger.warning("[QuerySynthesizer] LLM response failed parity gate check. Falling back to deterministic response.")
                return deterministic_resp

        except Exception as e:
            logger.warning(f"[QuerySynthesizer] Synthesis failed ({e}). Returning deterministic fallback.")
            return deterministic_resp
