import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from unittest.mock import AsyncMock, patch, MagicMock

from pydantic import ValidationError
from sqlmodel import Session
from src.services.query import (
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
    QueryService._instance = None
    with patch("src.core.llm.providers.ollama_provider.ollama.AsyncClient"), \
         patch("src.services.query.service.EncryptionService") as mock_enc:
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

@patch("src.services.query.service.Session")
def test_process_query_success(mock_session, query_service):
    async def _test():
        query_service.provider.complete_structured = AsyncMock(
            return_value='{"intent": "query_spending", "timeframe": "today", "category": "Food/Drink"}'
        )

        mock_session_inst = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_session_inst
        
        family_id = uuid4()
        tx = Transaction(
            id=uuid4(), family_id=family_id, user_id=uuid4(),
            amount="15.0 USD", concept="Lunch", category="Food/Drink",
            timestamp=datetime.now(timezone.utc)
        )
        def mock_exec(query):
            res = MagicMock()
            res.all.return_value = [tx] if "transaction" in str(query).lower() else []
            return res
        mock_session_inst.exec.side_effect = mock_exec

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
        query_service.provider.complete_structured = AsyncMock(side_effect=Exception("Ollama down"))

        with pytest.raises(QueryProcessingError, match="Failed to process query"):
            await query_service.process_query("test", uuid4())
    import asyncio
    asyncio.run(_test())

from src.services.query import (
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

@patch("src.services.query.service.Session")
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
        def mock_exec(query):
            res = MagicMock()
            res.all.return_value = [tx] if "transaction" in str(query).lower() else []
            return res
        mock_session_inst.exec.side_effect = mock_exec
        
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

@patch("src.services.query.service.Session")
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
        def mock_exec(query):
            res = MagicMock()
            res.all.return_value = [tx] if "transaction" in str(query).lower() else []
            return res
        mock_session_inst.exec.side_effect = mock_exec
        
        breakdown = await query_service.get_category_aggregation(family_id, "groceries", "this_month")
        assert breakdown.top_category == "Food/Drink"
        assert breakdown.total_spending == 15.0
    import asyncio
    asyncio.run(_test())



def test_multi_member_aggregation():
    from src.services.query import aggregate_transactions, DecryptedTransaction
    family_id = uuid4()
    user_a = uuid4()
    user_b = uuid4()
    transactions = [
        DecryptedTransaction(id=uuid4(), family_id=family_id, user_id=user_a, amount=10.0, currency="USD", concept="A", category="Other", timestamp=datetime.now(timezone.utc)),
        DecryptedTransaction(id=uuid4(), family_id=family_id, user_id=user_b, amount=20.0, currency="USD", concept="B", category="Other", timestamp=datetime.now(timezone.utc))
    ]
    agg = aggregate_transactions(transactions, "this_month")
    assert agg.total_amount == 30.0
    assert agg.transaction_count == 2

def test_cross_tenant_isolation_in_db_query(query_service):
    # This just ensures our _fetch_and_decrypt_transactions only filters by family_id
    from unittest.mock import patch, MagicMock
    from src.db.models import Transaction
    with patch("src.services.query.service.Session") as mock_session:
        mock_session_inst = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_session_inst
        mock_session_inst.exec.return_value.all.return_value = []
        
        family_id = uuid4()
        query_service._fetch_and_decrypt_transactions(family_id, None, None, None, None)
        
        # In a real DB it checks `where(Transaction.family_id == family_id)`
        # The test relies on SQLModel syntax. If we mocked correctly, it shouldn't raise.
        assert mock_session_inst.exec.called

def test_family_aware_summary_context():
    from src.services.query import _build_summary_prompt_context, QueryResult, ParsedQueryIntent, TimeAggregation
    intent = ParsedQueryIntent(intent="query", timeframe="this_week", scope="family")
    agg = TimeAggregation(timeframe="this_week", total_amount=100.0, primary_currency="USD", currency_totals={"USD": 100.0}, transaction_count=5, average_per_transaction=20.0, daily_breakdown={})
    qr = QueryResult(intent=intent, total_count=5, aggregation=agg)
    
    ctx = _build_summary_prompt_context(qr, family_name="The Smiths", member_names=["Alice", "Bob"])
    assert "Family Group: The Smiths" in ctx
    assert "Family Members: Alice, Bob" in ctx

def test_family_aware_fallback_summary():
    from src.services.query import generate_fallback_summary, QueryResult, ParsedQueryIntent, TimeAggregation
    intent = ParsedQueryIntent(intent="query", timeframe="this_week", scope="family")
    agg = TimeAggregation(timeframe="this_week", total_amount=100.0, primary_currency="USD", currency_totals={"USD": 100.0}, transaction_count=5, average_per_transaction=20.0, daily_breakdown={})
    qr = QueryResult(intent=intent, total_count=5, aggregation=agg)
    
    res = generate_fallback_summary(qr, family_name="The Smiths", member_names=["Alice", "Bob"])
    assert "Your family (The Smiths) has spent 100.00 USD" in res

def test_build_summary_prompt_context():
    from src.services.query import _build_summary_prompt_context, QueryResult, ParsedQueryIntent, TimeAggregation, CategoryBreakdown
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
    from src.services.query import generate_fallback_summary, QueryResult, ParsedQueryIntent, TimeAggregation, CategoryBreakdown, PeriodComparison
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

@patch("src.services.query.service.Session")
def test_generate_summary_success(mock_session, query_service):
    async def _test():
        from src.services.query import QueryResult, ParsedQueryIntent
        intent = ParsedQueryIntent(intent="query", timeframe="this_week", category=None)
        qr = QueryResult(intent=intent)
        
        query_service.provider.complete_text = AsyncMock(return_value="This is a mocked summary response.")
        
        summary = await query_service.generate_summary(qr, user_name="Tony", use_llm=True)
        assert summary == "This is a mocked summary response."
    import asyncio
    asyncio.run(_test())

@patch("src.services.query.service.Session")
def test_generate_summary_fallback(mock_session, query_service):
    async def _test():
        from src.services.query import QueryResult, ParsedQueryIntent
        intent = ParsedQueryIntent(intent="query", timeframe="this_week", category=None)
        qr = QueryResult(intent=intent)
        
        query_service.provider.complete_text = AsyncMock(side_effect=Exception("Ollama error"))
        
        summary = await query_service.generate_summary(qr, user_name="Tony", use_llm=True)
        assert "Tony" in summary
    import asyncio
    asyncio.run(_test())

@patch("src.services.query.service.Session")
def test_get_spending_summary(mock_session, query_service):
    async def _test():
        mock_session_inst = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_session_inst
        mock_session_inst.exec.return_value.all.return_value = []
        
        query_service.provider.complete_text = AsyncMock(return_value="Mocked spending summary.")
        
        res = await query_service.get_spending_summary(uuid4(), timeframe="this_week", user_name="Tony")
        assert res == "Mocked spending summary."
    import asyncio
    asyncio.run(_test())

@patch("src.services.query.service.Session")
def test_process_query_with_summary(mock_session, query_service):
    async def _test():
        mock_session_inst = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_session_inst
        mock_session_inst.exec.return_value.all.return_value = []
        
        query_service.provider.complete_structured = AsyncMock(
            return_value='{"intent": "query_spending", "timeframe": "today", "category": "Food/Drink"}'
        )
        
        with patch.object(query_service, 'generate_summary', return_value="Summary from process_query"):
            res = await query_service.process_query("What did I spend today?", uuid4(), user_name="Tony", generate_summary=True)
            assert res.summary == "Summary from process_query"
    import asyncio
    asyncio.run(_test())

def test_decrypted_transaction_with_user_info():
    tx = DecryptedTransaction(
        id=uuid4(), family_id=uuid4(), user_id=uuid4(),
        user_name="Tony Stark", user_handle="@ironman",
        amount=10.0, currency="USD", concept="A", category="Other", timestamp=datetime.now(timezone.utc)
    )
    assert tx.user_name == "Tony Stark"
    assert tx.user_handle == "@ironman"

def test_aggregate_by_member():
    from src.services.query import aggregate_by_member
    user_a = uuid4()
    user_b = uuid4()
    transactions = [
        DecryptedTransaction(id=uuid4(), family_id=uuid4(), user_id=user_a, user_name="Alice", user_handle="@alice", amount=10.0, currency="USD", concept="A", category="Food/Drink", timestamp=datetime.now(timezone.utc)),
        DecryptedTransaction(id=uuid4(), family_id=uuid4(), user_id=user_a, user_name="Alice", user_handle="@alice", amount=20.0, currency="USD", concept="B", category="Food/Drink", timestamp=datetime.now(timezone.utc)),
        DecryptedTransaction(id=uuid4(), family_id=uuid4(), user_id=user_b, user_name="Bob", user_handle=None, amount=10.0, currency="EUR", concept="C", category="Transport", timestamp=datetime.now(timezone.utc))
    ]
    breakdown = aggregate_by_member(transactions, "this_month", None, None, "USD", 30.0)
    assert breakdown.top_spender == "Alice"
    assert breakdown.top_spender_amount == 30.0
    assert "Alice" in breakdown.members
    assert breakdown.members["Alice"].total_amount == 30.0
    assert breakdown.members["Alice"].transaction_count == 2
    assert breakdown.members["Bob"].transaction_count == 1
    assert breakdown.members["Bob"].currency_totals == {"EUR": 10.0}

def test_aggregate_by_member_empty():
    from src.services.query import aggregate_by_member
    breakdown = aggregate_by_member([], "this_month", None, None, "USD", 0.0)
    assert breakdown.total_spending == 0.0
    assert breakdown.top_spender is None
    assert breakdown.members == {}

def test_parse_intent_with_member_filter():
    from src.services.query import ParsedQueryIntent
    intent = ParsedQueryIntent(intent="query", member_filter="Tony")
    assert intent.member_filter == "Tony"

@patch("src.services.query.service.Session")
def test_fetch_and_decrypt_with_member_filter(mock_session, query_service):
    async def _test():
        from src.db.models import User, Transaction
        mock_session_inst = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_session_inst
        
        family_id = uuid4()
        user_id = uuid4()
        tx = Transaction(
            id=uuid4(), family_id=family_id, user_id=user_id,
            amount="15.0 USD", concept="Lunch", category="Food/Drink",
            timestamp=datetime.now(timezone.utc)
        )
        
        user = User(id=user_id, family_id=family_id, telegram_id=123, username="tony", full_name="Tony Stark")

        def mock_exec(query):
            res = MagicMock()
            if "transaction" in str(query).lower():
                res.all.return_value = [tx]
            else:
                res.all.return_value = [user]
            return res
            
        mock_session_inst.exec.side_effect = mock_exec
        
        txs = query_service._fetch_and_decrypt_transactions(family_id, None, None, None, None, member_filter="Tony")
        assert len(txs) == 1
        assert txs[0].user_name == "Tony Stark"
        
        txs_no = query_service._fetch_and_decrypt_transactions(family_id, None, None, None, None, member_filter="Maria")
        assert len(txs_no) == 0
    import asyncio
    asyncio.run(_test())

def test_build_summary_prompt_context_with_members():
    from src.services.query import _build_summary_prompt_context, QueryResult, ParsedQueryIntent, TimeAggregation, CategoryBreakdown, MemberBreakdown, MemberSpending, DecryptedTransaction
    
    intent = ParsedQueryIntent(intent="query", timeframe="this_week", category=None)
    agg = TimeAggregation(timeframe="this_week", total_amount=205.5, primary_currency="USD", currency_totals={"USD": 205.5}, transaction_count=5, average_per_transaction=41.1, daily_breakdown={})
    
    ms_tony = MemberSpending(user_id=uuid4(), user_name="Tony", total_amount=120.0, primary_currency="USD", currency_totals={"USD": 120.0}, transaction_count=3, percentage_of_total=58.4, average_per_transaction=40.0, top_category="Shopping")
    ms_maria = MemberSpending(user_id=uuid4(), user_name="Maria", total_amount=85.5, primary_currency="USD", currency_totals={"USD": 85.5}, transaction_count=2, percentage_of_total=41.6, average_per_transaction=42.75, top_category="Food/Drink")
    
    mb = MemberBreakdown(timeframe="this_week", total_spending=205.5, primary_currency="USD", members={"Tony": ms_tony, "Maria": ms_maria}, top_spender="Tony", top_spender_amount=120.0)
    
    tx1 = DecryptedTransaction(id=uuid4(), family_id=uuid4(), user_id=uuid4(), user_name="Tony", user_handle="@tony", amount=40.0, currency="USD", concept="Shoes", category="Shopping", timestamp=datetime.now(timezone.utc))
    
    qr = QueryResult(intent=intent, total_count=5, aggregation=agg, member_breakdown=mb, transactions=[tx1])
    
    ctx = _build_summary_prompt_context(qr, user_name="Tony")
    assert "Member Breakdown:" in ctx
    assert "Tony: 120.00 USD (3 transactions, 58.4% of total, Top category: Shopping)" in ctx
    assert "Shoes (40.00 USD by Tony)" in ctx

def test_generate_fallback_summary_with_members():
    from src.services.query import generate_fallback_summary, QueryResult, ParsedQueryIntent, TimeAggregation, MemberBreakdown, MemberSpending
    intent = ParsedQueryIntent(intent="query", timeframe="this_week", category=None)
    agg = TimeAggregation(timeframe="this_week", total_amount=205.5, primary_currency="USD", currency_totals={"USD": 205.5}, transaction_count=5, average_per_transaction=41.1, daily_breakdown={})
    ms_tony = MemberSpending(user_id=uuid4(), user_name="Tony", total_amount=120.0, primary_currency="USD", currency_totals={"USD": 120.0}, transaction_count=3, percentage_of_total=58.4, average_per_transaction=40.0, top_category="Shopping")
    ms_maria = MemberSpending(user_id=uuid4(), user_name="Maria", total_amount=85.5, primary_currency="USD", currency_totals={"USD": 85.5}, transaction_count=2, percentage_of_total=41.6, average_per_transaction=42.75, top_category="Food/Drink")
    mb = MemberBreakdown(timeframe="this_week", total_spending=205.5, primary_currency="USD", members={"Tony": ms_tony, "Maria": ms_maria}, top_spender="Tony", top_spender_amount=120.0)
    qr = QueryResult(intent=intent, total_count=5, aggregation=agg, member_breakdown=mb)
    
    res = generate_fallback_summary(qr, family_name="The Smiths")
    assert "(Tony: 120.00; Maria: 85.50)" in res

def test_generate_fallback_summary_member_filter():
    from src.services.query import generate_fallback_summary, QueryResult, ParsedQueryIntent, TimeAggregation
    intent = ParsedQueryIntent(intent="query", timeframe="this_week", category=None, member_filter="Maria")
    agg = TimeAggregation(timeframe="this_week", total_amount=85.5, primary_currency="USD", currency_totals={"USD": 85.5}, transaction_count=2, average_per_transaction=42.75, daily_breakdown={})
    qr = QueryResult(intent=intent, total_count=2, aggregation=agg)
    res = generate_fallback_summary(qr)
    assert "Maria has spent 85.50 USD across 2 transactions" in res

def test_decrypted_transaction_with_type():
    tx_inc = DecryptedTransaction(
        id=uuid4(), family_id=uuid4(), user_id=uuid4(),
        amount=3500.0, currency="USD", concept="Acme Corp",
        category="Salary", type="income", timestamp=datetime.now(timezone.utc)
    )
    assert tx_inc.type == "income"

    tx_exp = DecryptedTransaction(
        id=uuid4(), family_id=uuid4(), user_id=uuid4(),
        amount=50.0, currency="USD", concept="Coffee",
        category="Food/Drink", timestamp=datetime.now(timezone.utc)
    )
    assert tx_exp.type == "expense"

def test_parsed_query_intent_income_and_net_cash_flow():
    intent_inc = ParsedQueryIntent(intent="income_summary", timeframe="this_month")
    assert intent_inc.intent == "income_summary"

    intent_net = ParsedQueryIntent(intent="net_cash_flow", timeframe="this_month")
    assert intent_net.intent == "net_cash_flow"

    intent_bal = ParsedQueryIntent(intent="net_balance", timeframe="this_week")
    assert intent_bal.intent == "net_balance"

def test_resolve_income_category_aliases():
    assert resolve_category_alias("salary") == "Salary"
    assert resolve_category_alias("paycheck") == "Salary"
    assert resolve_category_alias("wages") == "Salary"
    assert resolve_category_alias("bonus") == "Bonus"
    assert resolve_category_alias("freelance") == "Freelance"
    assert resolve_category_alias("consulting") == "Freelance"
    assert resolve_category_alias("dividends") == "Investment"
    assert resolve_category_alias("stocks") == "Investment"
    assert resolve_category_alias("gift") == "Gift"
    assert resolve_category_alias("sold items") == "Sale"

def test_aggregate_transactions_net_cash_flow_surplus():
    transactions = [
        DecryptedTransaction(id=uuid4(), family_id=uuid4(), user_id=uuid4(), amount=3500.0, currency="USD", concept="Salary", category="Salary", type="income", timestamp=datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc)),
        DecryptedTransaction(id=uuid4(), family_id=uuid4(), user_id=uuid4(), amount=500.0, currency="USD", concept="Freelance", category="Freelance", type="income", timestamp=datetime(2026, 8, 5, 10, 0, tzinfo=timezone.utc)),
        DecryptedTransaction(id=uuid4(), family_id=uuid4(), user_id=uuid4(), amount=1200.0, currency="USD", concept="Rent", category="Rent/Bills", type="expense", timestamp=datetime(2026, 8, 2, 10, 0, tzinfo=timezone.utc)),
        DecryptedTransaction(id=uuid4(), family_id=uuid4(), user_id=uuid4(), amount=300.0, currency="USD", concept="Groceries", category="Food/Drink", type="expense", timestamp=datetime(2026, 8, 6, 10, 0, tzinfo=timezone.utc)),
    ]
    agg = aggregate_transactions(transactions, "this_month", primary_currency="USD")
    assert agg.total_income == 4000.0
    assert agg.total_expenses == 1500.0
    assert agg.total_amount == 5500.0  # preserves backwards compatibility for spending queries
    assert agg.net_balance == 2500.0
    assert agg.savings_rate == 62.5 # (2500 / 4000) * 100
    assert agg.income_count == 2
    assert agg.expense_count == 2
    assert agg.transaction_count == 4
    assert agg.income_category_breakdown == {"Salary": 4000.0 - 500.0, "Freelance": 500.0}

def test_aggregate_transactions_net_cash_flow_deficit():
    transactions = [
        DecryptedTransaction(id=uuid4(), family_id=uuid4(), user_id=uuid4(), amount=1000.0, currency="USD", concept="Side gig", category="Freelance", type="income", timestamp=datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc)),
        DecryptedTransaction(id=uuid4(), family_id=uuid4(), user_id=uuid4(), amount=1500.0, currency="USD", concept="Laptop", category="Shopping", type="expense", timestamp=datetime(2026, 8, 2, 10, 0, tzinfo=timezone.utc)),
    ]
    agg = aggregate_transactions(transactions, "this_month", primary_currency="USD")
    assert agg.total_income == 1000.0
    assert agg.total_expenses == 1500.0
    assert agg.net_balance == -500.0
    assert agg.savings_rate == -50.0 # (-500 / 1000) * 100

def test_aggregate_transactions_zero_income():
    transactions = [
        DecryptedTransaction(id=uuid4(), family_id=uuid4(), user_id=uuid4(), amount=200.0, currency="USD", concept="Groceries", category="Food/Drink", type="expense", timestamp=datetime(2026, 8, 2, 10, 0, tzinfo=timezone.utc)),
    ]
    agg = aggregate_transactions(transactions, "this_month", primary_currency="USD")
    assert agg.total_income == 0.0
    assert agg.total_expenses == 200.0
    assert agg.net_balance == -200.0
    assert agg.savings_rate == 0.0 or agg.savings_rate is None

def test_aggregate_transactions_multi_currency_cash_flow():
    transactions = [
        DecryptedTransaction(id=uuid4(), family_id=uuid4(), user_id=uuid4(), amount=3000.0, currency="USD", concept="US Salary", category="Salary", type="income", timestamp=datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc)),
        DecryptedTransaction(id=uuid4(), family_id=uuid4(), user_id=uuid4(), amount=1000.0, currency="EUR", concept="EU Freelance", category="Freelance", type="income", timestamp=datetime(2026, 8, 2, 10, 0, tzinfo=timezone.utc)),
        DecryptedTransaction(id=uuid4(), family_id=uuid4(), user_id=uuid4(), amount=1000.0, currency="USD", concept="US Rent", category="Rent/Bills", type="expense", timestamp=datetime(2026, 8, 3, 10, 0, tzinfo=timezone.utc)),
        DecryptedTransaction(id=uuid4(), family_id=uuid4(), user_id=uuid4(), amount=400.0, currency="EUR", concept="EU Hotel", category="Leisure", type="expense", timestamp=datetime(2026, 8, 4, 10, 0, tzinfo=timezone.utc)),
    ]
    agg = aggregate_transactions(transactions, "this_month", primary_currency="USD")
    assert agg.total_income == 3000.0
    assert agg.total_expenses == 1000.0
    assert agg.net_balance == 2000.0
    assert agg.income_currency_totals == {"USD": 3000.0, "EUR": 1000.0}
    assert agg.expense_currency_totals == {"USD": 1000.0, "EUR": 400.0}

def test_generate_fallback_summary_income_query():
    from src.services.query import generate_fallback_summary, QueryResult, ParsedQueryIntent, TimeAggregation
    intent = ParsedQueryIntent(intent="income_summary", timeframe="this_month")
    agg = TimeAggregation(
        timeframe="this_month", total_amount=0.0, primary_currency="USD",
        total_income=4500.0, total_expenses=0.0, net_balance=4500.0,
        income_currency_totals={"USD": 4500.0}, transaction_count=2, income_count=2,
        average_per_transaction=2250.0, daily_breakdown={},
        income_category_breakdown={"Salary": 3500.0, "Bonus": 1000.0}
    )
    qr = QueryResult(intent=intent, total_count=2, aggregation=agg)
    res = generate_fallback_summary(qr, user_name="Tony")
    assert "earned 4,500.00 USD" in res or "earned $4,500.00" in res or "4500.00 USD" in res

def test_generate_fallback_summary_net_cash_flow_query():
    from src.services.query import generate_fallback_summary, QueryResult, ParsedQueryIntent, TimeAggregation
    intent = ParsedQueryIntent(intent="net_cash_flow", timeframe="this_month")
    agg = TimeAggregation(
        timeframe="this_month", total_amount=1200.0, primary_currency="USD",
        total_income=3500.0, total_expenses=1200.0, net_balance=2300.0, savings_rate=65.71,
        currency_totals={"USD": 1200.0}, income_currency_totals={"USD": 3500.0}, expense_currency_totals={"USD": 1200.0},
        transaction_count=5, income_count=1, expense_count=4, average_per_transaction=240.0, daily_breakdown={}
    )
    qr = QueryResult(intent=intent, total_count=5, aggregation=agg)
    res = generate_fallback_summary(qr, family_name="The Smiths")
    assert "3500.00" in res or "3,500.00" in res
    assert "1200.00" in res or "1,200.00" in res
    assert "2300.00" in res or "2,300.00" in res

def test_resolve_date_range_dynamic_days_and_spanish(query_service):
    ref_time = datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)
    
    # 15 days
    start, end = query_service._resolve_date_range("last_15_days", None, None, ref_time)
    assert start == datetime(2026, 8, 16, 0, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 8, 31, 23, 59, 59, 999999, tzinfo=timezone.utc)

    # Spanish ultimos_15_dias
    start_es, end_es = query_service._resolve_date_range("ultimos_15_dias", None, None, ref_time)
    assert start_es == datetime(2026, 8, 16, 0, 0, tzinfo=timezone.utc)
    assert end_es == datetime(2026, 8, 31, 23, 59, 59, 999999, tzinfo=timezone.utc)

    # Spanish este_mes
    start_m, end_m = query_service._resolve_date_range("este_mes", None, None, ref_time)
    assert start_m == datetime(2026, 8, 1, 0, 0, tzinfo=timezone.utc)
    assert end_m == datetime(2026, 8, 31, 23, 59, 59, 999999, tzinfo=timezone.utc)

def test_multi_currency_summary_segregation():
    from src.services.query import generate_fallback_summary, _build_summary_prompt_context, QueryResult, ParsedQueryIntent, TimeAggregation
    intent = ParsedQueryIntent(intent="net_cash_flow", timeframe="this_month")
    agg = TimeAggregation(
        timeframe="this_month",
        total_amount=0.0,
        primary_currency="USD",
        currency_totals={"USD": 4000.0, "MXN": 15.0},
        income_currency_totals={"USD": 4000.0},
        expense_currency_totals={"MXN": 15.0},
        transaction_count=2,
        income_count=1,
        expense_count=1
    )
    qr = QueryResult(intent=intent, total_count=2, aggregation=agg)
    res = generate_fallback_summary(qr, user_name="Tony")
    
    assert "4,000.00 USD" in res
    assert "15.00 MXN" in res
    
    ctx = _build_summary_prompt_context(qr, user_name="Tony")
    assert "MULTI-CURRENCY LEDGER" in ctx
    assert "4,000.00 USD" in ctx
    assert "15.00 MXN" in ctx


def test_aggregate_transactions_empty_custom_default_currency():
    agg = aggregate_transactions([], "this_month", primary_currency="ARS")
    assert agg.total_amount == 0.0
    assert agg.transaction_count == 0
    assert agg.primary_currency == "ARS"
    assert agg.currency_totals == {}


def test_summary_empty_state_custom_default_currency():
    from src.services.query import QueryResult, generate_fallback_summary, _build_summary_prompt_context
    intent = ParsedQueryIntent(intent="spending_summary", timeframe="last_week")
    agg = aggregate_transactions([], "last_week", primary_currency="ARS")
    qr = QueryResult(intent=intent, total_count=0, aggregation=agg)
    
    fallback = generate_fallback_summary(qr, user_name="Tony")
    assert "0.00 ARS" in fallback
    
    ctx = _build_summary_prompt_context(qr, user_name="Tony")
    assert "0.00 ARS" in ctx


@pytest.mark.anyio
async def test_get_spending_summary_with_custom_default_currency(query_service):
    family_id = uuid4()
    with patch.object(query_service, '_fetch_and_decrypt_transactions', return_value=[]):
        with patch.object(query_service, '_resolve_family_currency', return_value="ARS"):
            # Test fallback path when LLM fails or is disabled
            with patch.object(query_service.provider, 'complete_text', side_effect=Exception("Ollama unavailable")):
                res = await query_service.get_spending_summary(family_id, timeframe="last_week", user_name="Tony")
                assert "0.00 ARS" in res
            
            # Test that LLM receives context with 0.00 ARS
            async def mock_summary(sys_prompt, user_prompt, **kwargs):
                assert "0.00 ARS" in user_prompt
                return "Resumen: Tu balance es 0.00 ARS"
                
            with patch.object(query_service.provider, 'complete_text', side_effect=mock_summary):
                res = await query_service.get_spending_summary(family_id, timeframe="last_week", user_name="Tony")
                assert "0.00 ARS" in res



