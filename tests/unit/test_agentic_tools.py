import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from src.services.agent import (
    AgentService,
    AgentContext,
    CLANOMY_TOOLS_DECLARATIONS,
    execute_agent_tool
)
from src.services.query.models import DecryptedTransaction, DecryptedScheduledBill


@pytest.fixture
def agent_context():
    return AgentContext(
        user_id=uuid.uuid4(),
        family_id=uuid.uuid4(),
        user_name="Tony",
        family_name="Smith Family",
        default_currency="USD",
        timezone_name="America/Argentina/Buenos_Aires",
        is_spanish=True
    )


@pytest.mark.anyio
async def test_execute_query_savings_specific_currency(agent_context):
    now = datetime.now(timezone.utc)
    mock_txs = [
        DecryptedTransaction(
            id=uuid.uuid4(), family_id=agent_context.family_id, user_id=agent_context.user_id,
            amount=1000.0, currency="USD", concept="Freelance job", category="Salary", type="income", timestamp=now
        ),
        DecryptedTransaction(
            id=uuid.uuid4(), family_id=agent_context.family_id, user_id=agent_context.user_id,
            amount=400.0, currency="USD", concept="Electricity", category="Rent/Bills", type="expense", timestamp=now
        ),
        DecryptedTransaction(
            id=uuid.uuid4(), family_id=agent_context.family_id, user_id=agent_context.user_id,
            amount=50000.0, currency="ARS", concept="Consulting", category="Salary", type="income", timestamp=now
        )
    ]

    mock_qs = MagicMock()
    mock_qs._fetch_and_decrypt_transactions = AsyncMock(return_value=mock_txs)

    # 1. Query with specific currency = "USD"
    res_usd = await execute_agent_tool(
        tool_name="query_savings",
        args={"currency": "USD", "scope": "family"},
        context=agent_context,
        query_service=mock_qs
    )

    assert res_usd["status"] == "success"
    assert res_usd["requested_currency"] == "USD"
    assert res_usd["specific_currency_balance"] == 600.0  # 1000 - 400
    assert "ARS" in res_usd["currency_positions"]

    # 2. Query personal scope
    other_user_id = uuid.uuid4()
    mock_txs_mixed = [
        DecryptedTransaction(
            id=uuid.uuid4(), family_id=agent_context.family_id, user_id=agent_context.user_id,
            amount=500.0, currency="USD", concept="Tony Pay", category="Salary", type="income", timestamp=now
        ),
        DecryptedTransaction(
            id=uuid.uuid4(), family_id=agent_context.family_id, user_id=other_user_id,
            amount=800.0, currency="USD", concept="Partner Pay", category="Salary", type="income", timestamp=now
        )
    ]
    mock_qs._fetch_and_decrypt_transactions = AsyncMock(return_value=mock_txs_mixed)

    res_personal = await execute_agent_tool(
        tool_name="query_savings",
        args={"currency": "USD", "scope": "personal"},
        context=agent_context,
        query_service=mock_qs
    )
    assert res_personal["status"] == "success"
    assert res_personal["specific_currency_balance"] == 500.0  # Only Tony's transaction


@pytest.mark.anyio
async def test_execute_query_cash_flow(agent_context):
    now = datetime.now(timezone.utc)
    mock_txs = [
        DecryptedTransaction(
            id=uuid.uuid4(), family_id=agent_context.family_id, user_id=agent_context.user_id,
            amount=2000.0, currency="USD", concept="Salary", category="Salary", type="income", timestamp=now
        ),
        DecryptedTransaction(
            id=uuid.uuid4(), family_id=agent_context.family_id, user_id=agent_context.user_id,
            amount=500.0, currency="USD", concept="Groceries", category="Food/Drink", type="expense", timestamp=now
        )
    ]

    mock_qs = MagicMock()
    mock_qs._resolve_date_range = MagicMock(return_value=(now - timedelta(days=30), now))
    mock_qs._fetch_and_decrypt_transactions = AsyncMock(return_value=mock_txs)

    res = await execute_agent_tool(
        tool_name="query_cash_flow",
        args={"timeframe": "this_month", "scope": "family"},
        context=agent_context,
        query_service=mock_qs
    )

    assert res["status"] == "success"
    assert res["total_income"] == 2000.0
    assert res["total_expenses"] == 500.0
    assert res["net_balance"] == 1500.0
    assert res["savings_rate_pct"] == 75.0


@pytest.mark.anyio
async def test_execute_query_bills(agent_context):
    now = datetime.now(timezone.utc)
    mock_bills = [
        DecryptedScheduledBill(
            id=uuid.uuid4(), family_id=agent_context.family_id, user_id=agent_context.user_id,
            amount=120.0, currency="USD", concept="WiFi", category="Rent/Bills",
            due_date=now + timedelta(days=5), status="pending", created_at=now
        )
    ]

    mock_qs = MagicMock()
    mock_qs._resolve_date_range = MagicMock(return_value=(now, now + timedelta(days=30)))
    mock_qs._fetch_and_decrypt_scheduled_bills = AsyncMock(return_value=mock_bills)

    res = await execute_agent_tool(
        tool_name="query_bills",
        args={"timeframe": "this_month", "status": "pending"},
        context=agent_context,
        query_service=mock_qs
    )

    assert res["status"] == "success"
    assert res["count"] == 1
    assert res["total_pending_primary"] == 120.0
    assert res["bills"][0]["concept"] == "WiFi"


@pytest.mark.anyio
async def test_agent_service_end_to_end_simulation(agent_context):
    """
    Simulates the exact user scenario:
    User asks: 'cuantos USD tengo en este momento en total?'
    Gemini recognizes intent, calls query_savings(currency='USD'), and responds.
    """
    mock_provider = MagicMock()

    async def mock_complete_chat_with_tools(system_prompt, user_prompt, tool_declarations, tool_executor, **kwargs):
        # Gemini executes query_savings tool
        tool_result = await tool_executor("query_savings", {"currency": "USD", "scope": "family"})
        final_answer = f"En este momento tienes un total acumulado de ${tool_result['specific_currency_balance']:,.2f} USD 🏦."
        return final_answer, [{"name": "query_savings", "args": {"currency": "USD"}, "output": tool_result}]

    mock_provider.complete_chat_with_tools = AsyncMock(side_effect=mock_complete_chat_with_tools)

    now = datetime.now(timezone.utc)
    mock_txs = [
        DecryptedTransaction(
            id=uuid.uuid4(), family_id=agent_context.family_id, user_id=agent_context.user_id,
            amount=850.0, currency="USD", concept="Earnings", category="Salary", type="income", timestamp=now
        ),
        DecryptedTransaction(
            id=uuid.uuid4(), family_id=agent_context.family_id, user_id=agent_context.user_id,
            amount=400.0, currency="USD", concept="Supplies", category="Shopping", type="expense", timestamp=now
        )
    ]
    mock_qs = MagicMock()
    mock_qs._fetch_and_decrypt_transactions = AsyncMock(return_value=mock_txs)

    service = AgentService(provider=mock_provider, query_service=mock_qs)

    res = await service.run(
        text="cuantos USD tengo en este momento en total?",
        user_id=agent_context.user_id,
        family_id=agent_context.family_id,
        user_name="Tony",
        family_name="Smith",
        default_currency="USD"
    )

    assert "450.00 USD" in res["response"]
    assert len(res["tools_used"]) == 1
    assert res["tools_used"][0]["name"] == "query_savings"
    assert res["tools_used"][0]["output"]["specific_currency_balance"] == 450.0
