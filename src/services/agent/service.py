import logging
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime, timezone

from src.core.config import settings
from src.core.llm.providers.gemini_provider import GeminiProvider
from src.services.query.service import QueryService
from src.services.agent.tools import (
    CLANOMY_TOOLS_DECLARATIONS,
    AgentContext,
    execute_agent_tool
)

logger = logging.getLogger("clanomy.agent")

AGENT_SYSTEM_PROMPT = """You are Clanomy's intelligent financial assistant.
You help households and individuals track expenses, incomes, cash flow, and savings with clarity, accuracy, and empathy.

CRITICAL INSTRUCTIONS:
1. Always base financial figures strictly on data returned by your tools. NEVER invent or hallucinate amounts, balances, or transactions.
2. Tool Selection:
   - If the user asks about overall/cumulative savings, all-time balance, net worth, or how much money they have in total (e.g. "¿cuántos USD tengo en total?", "cuánto tengo ahorrado", "total balance"), call `query_savings`. If a specific currency was mentioned (e.g. USD, ARS, EUR), pass it in `currency`.
   - If the user asks about spending, incomes, or cash flow for a period (e.g. "este mes", "hoy", "esta semana", "last month"), call `query_cash_flow`.
   - If the user asks about bills, dues, or upcoming payments (e.g. "¿qué vence?", "facturas pendientes"), call `query_bills`.
   - If the user asks for a monthly comparison, 3-month trend, or recent history, call `query_history`.
3. Bilingual Support:
   - Respond in the language used by the user (Spanish or English).
4. Formatting:
   - Be concise, friendly, and direct. Keep answers between 2 and 4 sentences.
   - Use tasteful financial emojis (💰, 🏦, 📈, 💸, ⏰).
   - Format currencies clearly (e.g. "$450.00 USD", "$15,000.00 ARS").
"""


class AgentService:
    """
    Agentic Conversational Orchestrator.
    Combines native Gemini tool calling with in-memory zero-knowledge AES-GCM data access.
    """

    def __init__(self, provider: Optional[GeminiProvider] = None, query_service: Optional[QueryService] = None):
        self.provider = provider or GeminiProvider()
        self.query_service = query_service or QueryService()

    async def run(
        self,
        text: str,
        user_id: UUID,
        family_id: Optional[UUID] = None,
        user_name: Optional[str] = "You",
        family_name: Optional[str] = "Family",
        default_currency: Optional[str] = None,
        timezone_name: Optional[str] = None,
        is_spanish: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Executes an agentic interaction turn for the given user message.
        """
        if not text or not text.strip():
            return {"response": "Please provide a valid question or message.", "tools_used": []}

        eff_curr = default_currency or settings.DEFAULT_CURRENCY or "USD"
        eff_tz = timezone_name or settings.DEFAULT_TIMEZONE or "America/Argentina/Buenos_Aires"

        if is_spanish is None:
            from src.templates.telegram_messages import is_spanish_text
            is_spanish = is_spanish_text(text)

        context = AgentContext(
            user_id=user_id,
            family_id=family_id,
            user_name=user_name,
            family_name=family_name,
            default_currency=eff_curr,
            timezone_name=eff_tz,
            is_spanish=is_spanish
        )

        ref_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        dynamic_system_prompt = (
            f"{AGENT_SYSTEM_PROMPT}\n\n"
            f"<system_context>\n"
            f"User: {user_name}\n"
            f"Household/Family: {family_name}\n"
            f"Default Workspace Currency: {eff_curr}\n"
            f"Active Timezone: {eff_tz}\n"
            f"Current Timestamp: {ref_time}\n"
            f"</system_context>"
        )

        async def _tool_executor(fn_name: str, fn_args: dict) -> dict:
            return await execute_agent_tool(
                tool_name=fn_name,
                args=fn_args,
                context=context,
                query_service=self.query_service
            )

        logger.info(f"[AgentService] Running agent turn for user {user_id} with prompt: {text!r}")

        final_text, tools_used = await self.provider.complete_chat_with_tools(
            system_prompt=dynamic_system_prompt,
            user_prompt=text,
            tool_declarations=CLANOMY_TOOLS_DECLARATIONS,
            tool_executor=_tool_executor,
            temperature=0.2,
            timeout=30.0
        )

        return {
            "response": final_text,
            "tools_used": tools_used
        }
