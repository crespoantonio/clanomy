import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.pool import StaticPool

from src.core.config import settings
from src.core.encryption import EncryptionService
from src.db.models import User, Family
from src.services.extraction.models import UnifiedResult
from src.services.ai_orchestrator import AIOrchestrator


@pytest.fixture
def agentic_orchestrator_db(monkeypatch):
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    SQLModel.metadata.create_all(test_engine)

    monkeypatch.setattr("src.db.session.engine", test_engine)
    monkeypatch.setattr("src.services.ai_orchestrator.engine", test_engine)

    family_id = uuid4()
    user_id = uuid4()

    with Session(test_engine) as session:
        family = Family(id=family_id, name="Tony Family", plan_type="free", default_currency="USD")
        user = User(id=user_id, telegram_id=12345678, username="tony", full_name="Tony Crespo", family_id=family_id)
        session.add(family)
        session.add(user)
        session.commit()

    return {"family_id": family_id, "user_id": user_id, "engine": test_engine}


@pytest.mark.asyncio
async def test_orchestrator_routes_query_to_agent_service(agentic_orchestrator_db, monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_AGENTIC_CORE", True)

    user_id = str(agentic_orchestrator_db["user_id"])
    query_text = "cuantos USD tengo en este momento en total?"

    mock_unified = UnifiedResult(
        action="query",
        concept="balance query"
    )

    mock_agent_response = {
        "response": "En este momento tienes un total acumulado de $1,250.00 USD en ahorros familiares 💰.",
        "tools_used": [{"tool": "query_savings", "args": {"currency": "USD"}}]
    }

    with patch("src.services.ai_orchestrator.ExtractionService") as mock_extract_cls, \
         patch("src.services.agent.service.AgentService.run", new_callable=AsyncMock) as mock_agent_run, \
         patch("src.services.ai_orchestrator.TelegramService") as mock_tg_cls:

        mock_ext_instance = MagicMock()
        mock_ext_instance.classify_and_extract = AsyncMock(return_value=mock_unified)
        mock_extract_cls.return_value = mock_ext_instance

        mock_agent_run.return_value = mock_agent_response

        mock_tg_instance = MagicMock()
        mock_tg_instance.send_message = AsyncMock()
        mock_tg_cls.return_value = mock_tg_instance

        orchestrator = AIOrchestrator()
        result = await orchestrator._orchestrate_impl(
            user_id=user_id,
            text=query_text,
            audio_file_id=None,
            chat_id=12345678,
            message_id=None,
            send_telegram=True,
            dry_run=False
        )

        assert result["status"] == "success"
        assert result["bot_response"] == mock_agent_response["response"]
        mock_agent_run.assert_awaited_once()


@pytest.mark.asyncio
async def test_orchestrator_falls_back_when_agentic_core_disabled(agentic_orchestrator_db, monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_AGENTIC_CORE", False)

    user_id = str(agentic_orchestrator_db["user_id"])
    query_text = "cuanto gaste hoy?"

    mock_unified = UnifiedResult(
        action="query",
        concept="spending query"
    )

    with patch("src.services.ai_orchestrator.ExtractionService") as mock_extract_cls, \
         patch("src.services.agent.service.AgentService.run", new_callable=AsyncMock) as mock_agent_run, \
         patch("src.services.ai_orchestrator.QueryService.parse_intent", new_callable=AsyncMock) as mock_parse_intent, \
         patch.object(AIOrchestrator, "_execute_parsed_query", new_callable=AsyncMock) as mock_exec_query:

        mock_ext_instance = MagicMock()
        mock_ext_instance.classify_and_extract = AsyncMock(return_value=mock_unified)
        mock_extract_cls.return_value = mock_ext_instance

        mock_exec_query.return_value = "Gastos de hoy: $500 ARS"

        orchestrator = AIOrchestrator()
        result = await orchestrator._orchestrate_impl(
            user_id=user_id,
            text=query_text,
            audio_file_id=None,
            chat_id=12345678,
            message_id=None,
            send_telegram=False,
            dry_run=False
        )

        assert result["bot_response"] == "Gastos de hoy: $500 ARS"
        mock_agent_run.assert_not_called()
        mock_parse_intent.assert_awaited_once()


@pytest.mark.asyncio
async def test_orchestrator_falls_back_on_agent_service_exception(agentic_orchestrator_db, monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_AGENTIC_CORE", True)

    user_id = str(agentic_orchestrator_db["user_id"])
    query_text = "balance de este mes"

    mock_unified = UnifiedResult(
        action="query",
        concept="month balance"
    )

    with patch("src.services.ai_orchestrator.ExtractionService") as mock_extract_cls, \
         patch("src.services.agent.service.AgentService.run", side_effect=RuntimeError("Gemini timeout")), \
         patch("src.services.ai_orchestrator.QueryService.parse_intent", new_callable=AsyncMock) as mock_parse_intent, \
         patch.object(AIOrchestrator, "_execute_parsed_query", new_callable=AsyncMock) as mock_exec_query:

        mock_ext_instance = MagicMock()
        mock_ext_instance.classify_and_extract = AsyncMock(return_value=mock_unified)
        mock_extract_cls.return_value = mock_ext_instance

        mock_exec_query.return_value = "Resumen de balance mensual legado"

        orchestrator = AIOrchestrator()
        result = await orchestrator._orchestrate_impl(
            user_id=user_id,
            text=query_text,
            audio_file_id=None,
            chat_id=12345678,
            message_id=None,
            send_telegram=False,
            dry_run=False
        )

        assert result["bot_response"] == "Resumen de balance mensual legado"
        mock_parse_intent.assert_awaited_once()
