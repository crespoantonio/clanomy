import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from unittest.mock import AsyncMock, patch, MagicMock

from pydantic import ValidationError
from sqlmodel import Session
from src.services.query_service import (
    ParsedQueryIntent, 
    QueryProcessingError, 
    QueryService, 
    _parse_amount_string,
    resolve_category_alias,
    aggregate_by_category,
    CategoryBreakdown
)
from src.db.models import Transaction

def test_parsed_query_intent_category_normalization():
    intent = ParsedQueryIntent(intent="query", timeframe="today", category="food/drink")
    assert intent.category == "Food/Drink"
    intent2 = ParsedQueryIntent(intent="query", timeframe="today", category=None)
    assert intent2.category is None
    intent3 = ParsedQueryIntent(intent="query", timeframe="today", category="InvalidCategory")
    assert intent3.category == "Other"

def test_query_processing_error():
    err = QueryProcessingError("Test error")
    assert str(err) == "Test error"

def test_parse_amount_string():
    assert _parse_amount_string("15.5 USD") == (15.5, "USD")
    assert _parse_amount_string("100 EUR") == (100.0, "EUR")
    assert _parse_amount_string("Invalid USD") == (0.0, "USD")
    assert _parse_amount_string("") == (0.0, "USD")

@pytest.fixture
def query_service():
    with patch("src.services.query_service.ollama.AsyncClient"), \
         patch("src.services.query_service.EncryptionService") as mock_enc:
        service = QueryService()
        # Mock the encryption service to return what we pass for simplicity in testing
        mock_enc.return_value.decrypt.side_effect = lambda x: x
        yield service

def test_resolve_date_range_today(query_service):
    ref_time = datetime(2023, 10, 5, 12, 30, tzinfo=timezone.utc)
    start, end = query_service._resolve_date_range("today", None, None, ref_time)
    assert start == datetime(2023, 10, 5, 0, 0, tzinfo=timezone.utc)
    assert end == datetime(2023, 10, 5, 23, 59, 59, 999999, tzinfo=timezone.utc)

def test_resolve_date_range_this_month(query_service):
    ref_time = datetime(2023, 10, 5, 12, 30, tzinfo=timezone.utc)
    start, end = query_service._resolve_date_range("this_month", None, None, ref_time)
    assert start == datetime(2023, 10, 1, 0, 0, tzinfo=timezone.utc)
    assert end == datetime(2023, 10, 5, 23, 59, 59, 999999, tzinfo=timezone.utc)

def test_resolve_date_range_custom(query_service):
    start, end = query_service._resolve_date_range("custom", "2023-10-01", "2023-10-05")
    assert start == datetime(2023, 10, 1, 0, 0, tzinfo=timezone.utc)
    assert end == datetime(2023, 10, 5, 23, 59, 59, 999999, tzinfo=timezone.utc)

def test_process_query_empty_text(query_service):
    async def _test():
        with pytest.raises(ValueError, match="Query string cannot be empty"):
            await query_service.process_query("", uuid4())
    import asyncio
    asyncio.run(_test())

@patch("src.services.query_service.Session")
def test_process_query_success(mock_session, query_service):
    async def _test():
        mock_chat = AsyncMock()
        mock_chat.return_value.message.content = '{"intent": "query_spending", "timeframe": "today", "category": "Food/Drink"}'
        query_service.client.chat = mock_chat

        mock_session_inst = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_session_inst
        
        family_id = uuid4()
        tx = Transaction(
            id=uuid4(), family_id=family_id, user_id=uuid4(),
            amount="15.0 USD", concept="Lunch", category="Food/Drink",
            timestamp=datetime.now(timezone.utc)
        )
        mock_session_inst.exec.return_value.all.return_value = [tx]

        result = await query_service.process_query("How much did I spend on food today?", family_id)
        
        assert result.intent.intent == "query_spending"
        assert result.intent.timeframe == "today"
        assert result.total_count == 1
        assert result.transactions[0].amount == 15.0
        assert result.transactions[0].concept == "Lunch"
    import asyncio
    asyncio.run(_test())

def test_process_query_ollama_failure(query_service):
    async def _test():
        mock_chat = AsyncMock(side_effect=Exception("Ollama down"))
        query_service.client.chat = mock_chat

        with pytest.raises(QueryProcessingError, match="Failed to process query with Ollama"):
            await query_service.process_query("test", uuid4())
    import asyncio
    asyncio.run(_test())

from src.services.query_service import (
    aggregate_transactions,
    _resolve_comparison_timeframe,
    compute_period_comparison,
    TimeAggregation,
    PeriodComparison,
    DecryptedTransaction
)

def test_aggregate_transactions_basic():
    transactions = [
        DecryptedTransaction(id=uuid4(), family_id=uuid4(), user_id=uuid4(), amount=10.0, currency="USD", concept="A", category="Other", timestamp=datetime(2023, 10, 5, 12, 0, tzinfo=timezone.utc)),
        DecryptedTransaction(id=uuid4(), family_id=uuid4(), user_id=uuid4(), amount=20.0, currency="USD", concept="B", category="Other", timestamp=datetime(2023, 10, 5, 14, 0, tzinfo=timezone.utc)),
        DecryptedTransaction(id=uuid4(), family_id=uuid4(), user_id=uuid4(), amount=15.0, currency="EUR", concept="C", category="Other", timestamp=datetime(2023, 10, 6, 12, 0, tzinfo=timezone.utc))
    ]
    
    agg = aggregate_transactions(transactions, "this_week", primary_currency="USD")
    assert agg.total_amount == 30.0
    assert agg.transaction_count == 3
    assert agg.currency_totals == {"USD": 30.0, "EUR": 15.0}
    assert agg.daily_breakdown == {"2023-10-05": 30.0}

def test_aggregate_transactions_empty():
    agg = aggregate_transactions([], "this_month")
    assert agg.total_amount == 0.0
    assert agg.transaction_count == 0
    assert agg.currency_totals == {}

def test_aggregate_transactions_single_non_default_currency():
    transactions = [
        DecryptedTransaction(id=uuid4(), family_id=uuid4(), user_id=uuid4(), amount=45.0, currency="EUR", concept="Coffee", category="Food/Drink", timestamp=datetime(2023, 10, 5, 12, 0, tzinfo=timezone.utc))
    ]
    agg = aggregate_transactions(transactions, "this_month", primary_currency="USD")
    assert agg.total_amount == 45.0
    assert agg.primary_currency == "EUR"
    assert agg.daily_breakdown == {"2023-10-05": 45.0}

def test_resolve_comparison_timeframe():
    ref_time = datetime(2023, 10, 15, 12, 0, tzinfo=timezone.utc)
    prev_tf, prev_start, prev_end = _resolve_comparison_timeframe("this_month", ref_time)
    assert prev_tf == "last_month"
    assert prev_start == datetime(2023, 9, 1, 0, 0, tzinfo=timezone.utc)
    assert prev_end == datetime(2023, 9, 30, 23, 59, 59, 999999, tzinfo=timezone.utc)

def test_compute_period_comparison():
    agg = TimeAggregation(
        timeframe="this_month", total_amount=150.0, currency_totals={"USD": 150.0},
        transaction_count=2, average_per_transaction=75.0, daily_breakdown={}
    )
    prev_txs = [
        DecryptedTransaction(id=uuid4(), family_id=uuid4(), user_id=uuid4(), amount=100.0, currency="USD", concept="A", category="Other", timestamp=datetime(2023, 9, 5, 12, 0, tzinfo=timezone.utc))
    ]
    
    comp = compute_period_comparison(agg, prev_txs, "last_month", None, None)
    assert comp.difference_amount == 50.0
    assert comp.percentage_change == 50.0

@patch("src.services.query_service.Session")
def test_get_time_aggregation(mock_session, query_service):
    async def _test():
        mock_session_inst = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_session_inst
        
        family_id = uuid4()
        tx = Transaction(
            id=uuid4(), family_id=family_id, user_id=uuid4(),
            amount="15.0 USD", concept="Lunch", category="Food/Drink",
            timestamp=datetime.now(timezone.utc)
        )
        mock_session_inst.exec.return_value.all.return_value = [tx]
        
        agg = await query_service.get_time_aggregation(family_id, "this_month")
        assert agg.total_amount == 15.0
        assert agg.transaction_count == 1
    import asyncio
    asyncio.run(_test())

def test_resolve_category_alias():
    assert resolve_category_alias("groceries") == "Food/Drink"
    assert resolve_category_alias("Food/Drink") == "Food/Drink"
    assert resolve_category_alias("Food / Drink") == "Food/Drink"
    assert resolve_category_alias("Rent / Bills") == "Rent/Bills"
    assert resolve_category_alias("utilities") == "Rent/Bills"
    assert resolve_category_alias("hardware") == "Shopping"
    assert resolve_category_alias("unknown") == "Other"
    assert resolve_category_alias(None) is None
    assert resolve_category_alias("") is None

def test_aggregate_by_category():
    transactions = [
        DecryptedTransaction(id=uuid4(), family_id=uuid4(), user_id=uuid4(), amount=10.0, currency="USD", concept="A", category="Food/Drink", timestamp=datetime.now(timezone.utc)),
        DecryptedTransaction(id=uuid4(), family_id=uuid4(), user_id=uuid4(), amount=20.0, currency="USD", concept="B", category="Food/Drink", timestamp=datetime.now(timezone.utc)),
        DecryptedTransaction(id=uuid4(), family_id=uuid4(), user_id=uuid4(), amount=10.0, currency="EUR", concept="C", category="Transport", timestamp=datetime.now(timezone.utc))
    ]
    breakdown = aggregate_by_category(transactions)
    assert breakdown.top_category == "Food/Drink"
    assert breakdown.top_category_amount == 30.0
    assert breakdown.categories["Food/Drink"].percentage_of_total == 100.0
    assert breakdown.categories["Food/Drink"].transaction_count == 2
    assert breakdown.categories["Transport"].transaction_count == 1
    assert breakdown.categories["Transport"].total_amount == 0.0
    assert breakdown.categories["Transport"].currency_totals == {"EUR": 10.0}

def test_aggregate_by_category_single_non_default_currency():
    transactions = [
        DecryptedTransaction(id=uuid4(), family_id=uuid4(), user_id=uuid4(), amount=45.0, currency="EUR", concept="Coffee", category="Food/Drink", timestamp=datetime.now(timezone.utc))
    ]
    breakdown = aggregate_by_category(transactions, primary_currency="USD")
    assert breakdown.total_spending == 45.0
    assert breakdown.primary_currency == "EUR"
    assert breakdown.top_category == "Food/Drink"
    assert breakdown.top_category_amount == 45.0
    assert breakdown.categories["Food/Drink"].percentage_of_total == 100.0

def test_aggregate_by_category_empty():
    breakdown = aggregate_by_category([])
    assert breakdown.total_spending == 0.0
    assert breakdown.top_category is None
    assert breakdown.categories == {}

@patch("src.services.query_service.Session")
def test_get_category_aggregation(mock_session, query_service):
    async def _test():
        mock_session_inst = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_session_inst
        
        family_id = uuid4()
        tx = Transaction(
            id=uuid4(), family_id=family_id, user_id=uuid4(),
            amount="15.0 USD", concept="Lunch", category="Food/Drink",
            timestamp=datetime.now(timezone.utc)
        )
        mock_session_inst.exec.return_value.all.return_value = [tx]
        
        breakdown = await query_service.get_category_aggregation(family_id, "groceries", "this_month")
        assert breakdown.top_category == "Food/Drink"
        assert breakdown.total_spending == 15.0
    import asyncio
    asyncio.run(_test())



def test_build_summary_prompt_context():
    from src.services.query_service import _build_summary_prompt_context, QueryResult, ParsedQueryIntent, TimeAggregation, CategoryBreakdown
    intent = ParsedQueryIntent(intent="query", timeframe="this_week", category=None)
    agg = TimeAggregation(timeframe="this_week", total_amount=45.0, primary_currency="USD", currency_totals={"USD": 45.0}, transaction_count=2, average_per_transaction=22.5, daily_breakdown={})
    cb = CategoryBreakdown(timeframe="this_week", total_spending=45.0, primary_currency="USD", categories={}, top_category="Food/Drink", top_category_amount=45.0)
    qr = QueryResult(intent=intent, total_count=2, aggregation=agg, category_breakdown=cb)
    
    ctx = _build_summary_prompt_context(qr, user_name="Tony")
    assert "User: Tony" in ctx
    assert "this_week" in ctx
    assert "45.0" in ctx
    assert "Food/Drink" in ctx

def test_generate_fallback_summary():
    from src.services.query_service import generate_fallback_summary, QueryResult, ParsedQueryIntent, TimeAggregation, CategoryBreakdown, PeriodComparison
    intent = ParsedQueryIntent(intent="query", timeframe="this_week", category=None)
    
    # Standard summary with comparison diff > 0
    agg = TimeAggregation(
        timeframe="this_week", total_amount=45.0, primary_currency="USD",
        currency_totals={"USD": 45.0}, transaction_count=2, average_per_transaction=22.5, daily_breakdown={},
        comparison=PeriodComparison(previous_timeframe="last_week", previous_total_amount=50.0, previous_transaction_count=2, difference_amount=-5.0, percentage_change=-10.0)
    )
    cb = CategoryBreakdown(timeframe="this_week", total_spending=45.0, primary_currency="USD", categories={}, top_category="Food/Drink", top_category_amount=45.0)
    qr = QueryResult(intent=intent, total_count=2, aggregation=agg, category_breakdown=cb)
    
    res = generate_fallback_summary(qr, user_name="Tony")
    assert "45.00 USD" in res
    assert "Food/Drink" in res
    assert "less than last week" in res

    # Comparison diff == 0.0
    agg.comparison = PeriodComparison(previous_timeframe="last_week", previous_total_amount=45.0, previous_transaction_count=2, difference_amount=0.0, percentage_change=0.0)
    res_zero_diff = generate_fallback_summary(qr, user_name="Tony")
    assert "exact same total as last week" in res_zero_diff

    # Zero total amount but transactions exist (total_count > 0)
    agg_zero_val = TimeAggregation(timeframe="this_week", total_amount=0.0, primary_currency="USD", currency_totals={"USD": 0.0}, transaction_count=1, average_per_transaction=0.0, daily_breakdown={})
    qr_zero_val = QueryResult(intent=intent, total_count=1, aggregation=agg_zero_val)
    res_zero_val = generate_fallback_summary(qr_zero_val, user_name="Tony")
    assert "0.00 USD across 1 transactions" in res_zero_val

@patch("src.services.query_service.Session")
def test_generate_summary_success(mock_session, query_service):
    async def _test():
        from src.services.query_service import QueryResult, ParsedQueryIntent
        intent = ParsedQueryIntent(intent="query", timeframe="this_week", category=None)
        qr = QueryResult(intent=intent)
        
        mock_chat = AsyncMock()
        mock_chat.return_value.message.content = "This is a mocked summary response."
        query_service.client.chat = mock_chat
        
        summary = await query_service.generate_summary(qr, user_name="Tony", use_llm=True)
        assert summary == "This is a mocked summary response."
    import asyncio
    asyncio.run(_test())

@patch("src.services.query_service.Session")
def test_generate_summary_fallback(mock_session, query_service):
    async def _test():
        from src.services.query_service import QueryResult, ParsedQueryIntent
        intent = ParsedQueryIntent(intent="query", timeframe="this_week", category=None)
        qr = QueryResult(intent=intent)
        
        mock_chat = AsyncMock(side_effect=Exception("Ollama error"))
        query_service.client.chat = mock_chat
        
        summary = await query_service.generate_summary(qr, user_name="Tony", use_llm=True)
        assert "Tony" in summary
    import asyncio
    asyncio.run(_test())

@patch("src.services.query_service.Session")
def test_get_spending_summary(mock_session, query_service):
    async def _test():
        mock_session_inst = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_session_inst
        mock_session_inst.exec.return_value.all.return_value = []
        
        mock_chat = AsyncMock()
        mock_chat.return_value.message.content = "Mocked spending summary."
        query_service.client.chat = mock_chat
        
        res = await query_service.get_spending_summary(uuid4(), timeframe="this_week", user_name="Tony")
        assert res == "Mocked spending summary."
    import asyncio
    asyncio.run(_test())

@patch("src.services.query_service.Session")
def test_process_query_with_summary(mock_session, query_service):
    async def _test():
        mock_session_inst = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_session_inst
        mock_session_inst.exec.return_value.all.return_value = []
        
        mock_chat = AsyncMock()
        # First call is for intent parsing
        mock_chat.return_value.message.content = '{"intent": "query_spending", "timeframe": "today", "category": "Food/Drink"}'
        query_service.client.chat = mock_chat
        
        # We need to mock generate_summary because the intent parser and summary generator use the same ollama client mock.
        # Alternatively, we can patch generate_summary.
        with patch.object(query_service, 'generate_summary', return_value="Summary from process_query"):
            res = await query_service.process_query("What did I spend today?", uuid4(), user_name="Tony", generate_summary=True)
            assert res.summary == "Summary from process_query"
    import asyncio
    asyncio.run(_test())


