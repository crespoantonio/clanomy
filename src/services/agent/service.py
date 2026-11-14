import logging
import asyncio
from collections import OrderedDict
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


class _BoundedAgentSessionStore:
    """
    LRU-bounded conversation history store for multi-turn agent interactions (Story 26.2).
    Stores up to `max_turns` (default 6 messages = 3 user + 3 assistant turns) per session.
    Evicts oldest sessions when exceeding `max_sessions` (default 1,000) to guarantee bounded memory.
    Enforces a strict inactivity TTL (`ttl_seconds`, default 900s = 15 minutes) to ensure stale
    historical context decays and never pollutes subsequent independent conversation sessions.
    """
    def __init__(self, max_sessions: int = 1000, max_turns: int = 6, ttl_seconds: int = 900):
        self._sessions: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._max_sessions = max_sessions
        self._max_turns = max_turns
        self._ttl_seconds = ttl_seconds
        self._lock = asyncio.Lock()

    def _get_key(self, user_id: UUID, family_id: Optional[UUID]) -> str:
        return f"{family_id or 'none'}:{user_id}"

    async def get_history(self, user_id: UUID, family_id: Optional[UUID]) -> List[Dict[str, Any]]:
        async with self._lock:
            key = self._get_key(user_id, family_id)
            if key in self._sessions:
                session = self._sessions[key]
                last_active = session.get("last_activity")
                now = datetime.now(timezone.utc)
                if last_active and (now - last_active).total_seconds() > self._ttl_seconds:
                    logger.info(
                        f"[_BoundedAgentSessionStore] Session {key} expired after {self._ttl_seconds}s of inactivity. Flushing stale context."
                    )
                    del self._sessions[key]
                    return []
                self._sessions.move_to_end(key)
                return list(session.get("history", []))
            return []

    async def append_turn(self, user_id: UUID, family_id: Optional[UUID], user_text: str, assistant_text: str) -> None:
        async with self._lock:
            key = self._get_key(user_id, family_id)
            now = datetime.now(timezone.utc)
            if key not in self._sessions:
                if len(self._sessions) >= self._max_sessions:
                    self._sessions.popitem(last=False)
                self._sessions[key] = {
                    "history": [],
                    "last_activity": now
                }
            else:
                self._sessions.move_to_end(key)

            history = self._sessions[key]["history"]
            history.append({"role": "user", "parts": [{"text": user_text}]})
            history.append({"role": "model", "parts": [{"text": assistant_text}]})

            # Bounded sliding window
            if len(history) > self._max_turns:
                self._sessions[key]["history"] = history[-self._max_turns:]
            self._sessions[key]["last_activity"] = now

    async def clear_session(self, user_id: UUID, family_id: Optional[UUID] = None) -> None:
        async with self._lock:
            key = self._get_key(user_id, family_id)
            self._sessions.pop(key, None)


class AgentService:
    """
    Agentic Conversational Orchestrator.
    Combines native Gemini tool calling with in-memory zero-knowledge AES-GCM data access
    and bounded multi-turn conversation memory with session inactivity TTL.
    """

    def __init__(
        self,
        provider: Optional[GeminiProvider] = None,
        query_service: Optional[QueryService] = None,
        session_store: Optional[_BoundedAgentSessionStore] = None,
        ttl_seconds: int = 900
    ):
        self.provider = provider or GeminiProvider()
        self.query_service = query_service or QueryService()
        self.session_store = session_store or _BoundedAgentSessionStore(ttl_seconds=ttl_seconds)

    async def clear_session(self, user_id: UUID, family_id: Optional[UUID] = None) -> None:
        """Clears active conversation session history for the given user/family."""
        await self.session_store.clear_session(user_id, family_id)

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
        Executes an agentic interaction turn for the given user message with bounded multi-turn context.
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

        # Retrieve bounded multi-turn conversation history
        chat_history = await self.session_store.get_history(user_id, family_id)

        logger.info(
            f"[AgentService] Running agent turn for user {user_id} with prompt: {text!r} (history turns: {len(chat_history) // 2})"
        )

        try:
            final_text, tools_used = await self.provider.complete_chat_with_tools(
                system_prompt=dynamic_system_prompt,
                user_prompt=text,
                tool_declarations=CLANOMY_TOOLS_DECLARATIONS,
                tool_executor=_tool_executor,
                chat_history=chat_history if chat_history else None,
                temperature=0.2,
                timeout=30.0
            )
        except Exception as e:
            logger.warning(
                f"[AgentService] complete_chat_with_tools failed for user {user_id}: {e}. Tripping Fallback Circuit Breaker.",
                exc_info=True
            )
            final_text = ""
            tools_used = []

        # Fallback Circuit Breaker: If AI response is empty, whitespace, or aborted due to provider error
        if not final_text or not final_text.strip():
            logger.info(
                f"[AgentService] Fallback Circuit Breaker active for user {user_id}. Executing DecoupledQueryPipeline."
            )
            try:
                from src.services.query.pipeline import DecoupledQueryPipeline
                pipeline = DecoupledQueryPipeline()
                final_text = await pipeline.execute(
                    text=text,
                    family_id=family_id or user_id,
                    user_id=user_id,
                    user_name=user_name or "You",
                    default_currency=eff_curr,
                    tz_name=eff_tz,
                    reference_time=datetime.now(timezone.utc),
                    is_spanish=is_spanish
                )
            except Exception as pipe_err:
                logger.error(f"[AgentService] Fallback pipeline failed for user {user_id}: {pipe_err}")
                final_text = (
                    "No pude procesar tu consulta en este momento. Por favor, intenta nuevamente."
                    if is_spanish
                    else "I could not process your query at this moment. Please try again."
                )

        # Record successful turn into bounded session history
        if final_text:
            await self.session_store.append_turn(user_id, family_id, text, final_text)

        return {
            "response": final_text,
            "tools_used": tools_used
        }
