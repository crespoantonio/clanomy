import pytest
from unittest.mock import MagicMock, AsyncMock
from uuid import uuid4
from datetime import datetime, timezone
from decimal import Decimal

from src.services.query.synthesizer import QuerySynthesizer
from src.services.query.models import (
    NormalizedQueryAST,
    TemporalScope,
    EntityFilters,
    QueryOperation,
    DecryptedTransaction,
    DecryptedScheduledBill
)
from src.services.query.dataset_router import RoutedDataset
from src.services.query.math_engine import AggregatedFinancialMetrics
from src.services.agent.service import AgentService, _BoundedAgentSessionStore
from src.core.llm.providers.gemini_provider import GeminiProvider


@pytest.mark.asyncio
async def test_synthesizer_context_budgeting_caps_exemplars_to_five():
    """Verify AC 26.1.1 & AC 26.1.2: Synthesizer caps exemplars to 5 when total records > 5."""
    captured_prompts = []

    mock_llm = MagicMock()
    async def mock_complete(system_prompt: str, user_prompt: str, timeout: float = 60.0):
        captured_prompts.append(user_prompt)
        return "Tus gastos suman <b>$1,500.00 USD</b>."
    mock_llm.complete = mock_complete

    synthesizer = QuerySynthesizer(provider=mock_llm)

    fam_id = uuid4()
    # Create 15 transactions
    transactions = [
        DecryptedTransaction(
            id=uuid4(),
            family_id=fam_id,
            user_id=uuid4(),
            user_name="User",
            user_handle="@user",
            amount=Decimal(str(i * 100)),
            currency="USD",
            concept=f"Store purchase {i}",
            category="Shopping",
            timestamp=datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc),
            type="expense"
        )
        for i in range(1, 16)
    ]

    routed = RoutedDataset(
        domain="expenses",
        is_historical=True,
        is_projected=False,
        transactions=transactions,
        scheduled_bills=[]
    )

    metrics = {
        "USD": AggregatedFinancialMetrics(
            currency="USD",
            total_amount=Decimal("1500.00"),
            count=15
        )
    }

    ast = NormalizedQueryAST(
        raw_query="How much did we spend on shopping?",
        temporal=TemporalScope(timeframe="this_month", is_historical=True, is_projected=False),
        filters=EntityFilters(domains=["expenses"], category_hints=["Shopping"]),
        operation=QueryOperation(op="sum")
    )

    result = await synthesizer.synthesize(
        query_text="How much did we spend on shopping?",
        ast=ast,
        routed=routed,
        metrics_by_currency=metrics,
        user_name="Alice",
        default_currency="USD",
        is_spanish=True
    )

    assert len(captured_prompts) == 1
    prompt = captured_prompts[0]

    # Verify that only top 5 exemplars are in the Individual Records block
    assert "Showing top 5 representative items out of 15 total records" in prompt
    assert "Store purchase 15" in prompt  # Top amount ($1500)
    assert "Store purchase 14" in prompt
    assert "Store purchase 13" in prompt
    assert "Store purchase 12" in prompt
    assert "Store purchase 11" in prompt
    # Items with lower amounts should be pruned from the prompt
    assert "Store purchase 1," not in prompt
    assert "Store purchase 2," not in prompt


@pytest.mark.asyncio
async def test_synthesizer_context_budgeting_includes_all_when_five_or_less():
    """Verify that when records <= 5, all are included and no pruning note is added."""
    captured_prompts = []

    mock_llm = MagicMock()
    async def mock_complete(system_prompt: str, user_prompt: str, timeout: float = 60.0):
        captured_prompts.append(user_prompt)
        return "Tus gastos suman <b>$300.00 USD</b>."
    mock_llm.complete = mock_complete

    synthesizer = QuerySynthesizer(provider=mock_llm)

    fam_id = uuid4()
    transactions = [
        DecryptedTransaction(
            id=uuid4(),
            family_id=fam_id,
            user_id=uuid4(),
            user_name="User",
            user_handle="@user",
            amount=Decimal(str(i * 100)),
            currency="USD",
            concept=f"Small item {i}",
            category="Shopping",
            timestamp=datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc),
            type="expense"
        )
        for i in range(1, 4)
    ]

    routed = RoutedDataset(
        domain="expenses",
        is_historical=True,
        is_projected=False,
        transactions=transactions,
        scheduled_bills=[]
    )

    metrics = {
        "USD": AggregatedFinancialMetrics(
            currency="USD",
            total_amount=Decimal("300.00"),
            count=3
        )
    }

    ast = NormalizedQueryAST(
        raw_query="Spending?",
        temporal=TemporalScope(timeframe="this_month", is_historical=True, is_projected=False),
        filters=EntityFilters(domains=["expenses"]),
        operation=QueryOperation(op="sum")
    )

    await synthesizer.synthesize(
        query_text="Spending?",
        ast=ast,
        routed=routed,
        metrics_by_currency=metrics,
        user_name="Alice",
        default_currency="USD",
        is_spanish=True
    )

    prompt = captured_prompts[0]
    assert "Small item 1" in prompt
    assert "Small item 2" in prompt
    assert "Small item 3" in prompt
    assert "Showing top 5 representative items" not in prompt


@pytest.mark.asyncio
async def test_bounded_agent_session_store():
    """Verify AC 26.2.1 & AC 26.2.2: LRU session store bounds turns and evicts oldest sessions."""
    store = _BoundedAgentSessionStore(max_sessions=2, max_turns=4)
    user1 = uuid4()
    user2 = uuid4()
    user3 = uuid4()

    # User 1 turns
    await store.append_turn(user1, None, "Hello", "Hi there!")
    await store.append_turn(user1, None, "Balance?", "Your balance is $500.")
    await store.append_turn(user1, None, "What about food?", "$120 was food.")

    history1 = await store.get_history(user1, None)
    # max_turns is 4 (2 user + 2 assistant messages), so the first turn ("Hello") must have slid out
    assert len(history1) == 4
    assert history1[0]["parts"][0]["text"] == "Balance?"
    assert history1[-1]["parts"][0]["text"] == "$120 was food."

    # User 2 turn
    await store.append_turn(user2, None, "User 2 msg", "Resp 2")

    # User 3 turn (should evict user 1 because max_sessions is 2 and user2 was recently added)
    # First access user1 to ensure user2 is oldest, or let user3 evict user1:
    await store.append_turn(user3, None, "User 3 msg", "Resp 3")

    history_evicted = await store.get_history(user1, None)
    assert history_evicted == []  # Evicted

    history3 = await store.get_history(user3, None)
    assert len(history3) == 2


@pytest.mark.asyncio
async def test_agent_service_multi_turn_flow():
    """Verify AC 26.2.3 & AC 26.2.4: AgentService passes chat history to provider and supports clear_session."""
    mock_provider = MagicMock()
    captured_histories = []

    async def mock_chat(system_prompt, user_prompt, tool_declarations, tool_executor, chat_history=None, **kwargs):
        captured_histories.append(chat_history)
        return f"Response to: {user_prompt}", []

    mock_provider.complete_chat_with_tools = mock_chat

    agent = AgentService(provider=mock_provider)
    uid = uuid4()
    fid = uuid4()

    # Turn 1
    res1 = await agent.run(text="How much did I spend this month?", user_id=uid, family_id=fid)
    assert "Response to: How much did I spend this month?" in res1["response"]
    assert captured_histories[0] is None

    # Turn 2: Should receive history from turn 1
    res2 = await agent.run(text="And on dining out?", user_id=uid, family_id=fid)
    assert len(captured_histories) == 2
    assert captured_histories[1] is not None
    assert len(captured_histories[1]) == 2
    assert captured_histories[1][0]["parts"][0]["text"] == "How much did I spend this month?"

    # Clear session
    await agent.clear_session(user_id=uid, family_id=fid)
    captured_histories.clear()

    # Turn 3: History should be empty after clear
    await agent.run(text="Start fresh question", user_id=uid, family_id=fid)
    assert captured_histories[0] is None


@pytest.mark.asyncio
async def test_agent_session_inactivity_ttl_expiration():
    """Verify that sessions expire after the configured TTL (e.g. 3 hours later is a new session)."""
    import asyncio
    # Store with a very short TTL (0.1s)
    store = _BoundedAgentSessionStore(max_sessions=10, max_turns=6, ttl_seconds=0.1)
    uid = uuid4()
    fid = uuid4()

    await store.append_turn(uid, fid, "Morning question", "Morning answer")
    
    # Immediately check: history is present
    hist = await store.get_history(uid, fid)
    assert len(hist) == 2
    assert hist[0]["parts"][0]["text"] == "Morning question"

    # Wait for TTL to expire (simulate sending 3 hours later)
    await asyncio.sleep(0.15)

    # After TTL, session should automatically flush and return empty history
    expired_hist = await store.get_history(uid, fid)
    assert expired_hist == []

    # New turn starts fresh without old context
    await store.append_turn(uid, fid, "Afternoon question", "Afternoon answer")
    new_hist = await store.get_history(uid, fid)
    assert len(new_hist) == 2
    assert new_hist[0]["parts"][0]["text"] == "Afternoon question"
    assert "Morning question" not in str(new_hist)
