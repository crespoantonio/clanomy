import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4
from datetime import datetime, timezone

from src.services.agent.service import AgentService
from src.services.agent.tools import execute_agent_tool, AgentContext


@pytest.fixture
def agent_context():
    return AgentContext(
        user_id=uuid4(),
        family_id=uuid4(),
        user_name="Tony",
        family_name="Tony Family",
        default_currency="USD",
        timezone_name="America/Argentina/Buenos_Aires",
        is_spanish=True
    )


@pytest.mark.asyncio
async def test_tool_error_envelope_for_unknown_tool(agent_context):
    """Verify AC 26.4.1: Unknown tool call returns structured error envelope with recovery hint."""
    res = await execute_agent_tool(
        tool_name="non_existent_tool",
        args={},
        context=agent_context
    )

    assert res["status"] == "error"
    assert res["tool"] == "non_existent_tool"
    assert "error" in res
    assert res["error"]["code"] == "UNKNOWN_TOOL"
    assert "recovery_hint" in res["error"]
    assert "query_savings" in res["error"]["recovery_hint"]


@pytest.mark.asyncio
async def test_tool_error_envelope_for_invalid_parameters(agent_context):
    """Verify AC 26.4.1: Invalid tool arguments return INVALID_PARAMETERS envelope."""
    # query_savings expects scope to be 'family' or 'personal', pass invalid value
    res = await execute_agent_tool(
        tool_name="query_savings",
        args={"scope": "invalid_scope_value"},
        context=agent_context
    )

    assert res["status"] == "error"
    assert res["error"]["code"] == "INVALID_PARAMETERS"
    assert "recovery_hint" in res["error"]
    assert "Parameter validation failed" in res["message"]


@pytest.mark.asyncio
async def test_tool_error_envelope_for_runtime_failure(agent_context):
    """Verify AC 26.4.2: Runtime errors return EXECUTION_FAILURE without raw stack traces."""
    mock_qs = MagicMock()
    mock_qs._fetch_and_decrypt_transactions = AsyncMock(side_effect=RuntimeError("Database connection lost at /internal/db.py"))

    res = await execute_agent_tool(
        tool_name="query_savings",
        args={"scope": "family"},
        context=agent_context,
        query_service=mock_qs
    )

    assert res["status"] == "error"
    assert res["error"]["code"] == "EXECUTION_FAILURE"
    assert "RuntimeError" in res["message"]
    # Verify raw file path / stack trace details are not leaked in message
    assert "/internal/db.py" not in res["message"]


@pytest.mark.asyncio
async def test_agent_fallback_circuit_breaker_on_empty_response(agent_context):
    """Verify AC 26.4.3: When complete_chat_with_tools returns empty, Fallback Circuit Breaker activates."""
    mock_provider = MagicMock()
    # Provider returns empty string (e.g. hit iteration limit)
    mock_provider.complete_chat_with_tools = AsyncMock(return_value=("", []))

    agent = AgentService(provider=mock_provider)

    with patch("src.services.query.pipeline.DecoupledQueryPipeline.execute", new_callable=AsyncMock) as mock_pipeline:
        mock_pipeline.return_value = "Gastaste un total de <b>$500.00 USD</b> este mes."

        result = await agent.run(
            text="¿Cuánto gastamos este mes?",
            user_id=agent_context.user_id,
            family_id=agent_context.family_id,
            is_spanish=True
        )

        assert mock_pipeline.called
        assert result["response"] == "Gastaste un total de <b>$500.00 USD</b> este mes."


@pytest.mark.asyncio
async def test_agent_fallback_circuit_breaker_on_provider_exception(agent_context):
    """Verify AC 26.4.3: When complete_chat_with_tools raises an unhandled exception, Circuit Breaker falls back."""
    mock_provider = MagicMock()
    mock_provider.complete_chat_with_tools = AsyncMock(side_effect=TimeoutError("Gemini API timeout"))

    agent = AgentService(provider=mock_provider)

    with patch("src.services.query.pipeline.DecoupledQueryPipeline.execute", new_callable=AsyncMock) as mock_pipeline:
        mock_pipeline.return_value = "Tus vencimientos suman <b>$120.00 USD</b>."

        result = await agent.run(
            text="¿Cuáles son mis facturas pendientes?",
            user_id=agent_context.user_id,
            family_id=agent_context.family_id,
            is_spanish=True
        )

        assert mock_pipeline.called
        assert result["response"] == "Tus vencimientos suman <b>$120.00 USD</b>."
