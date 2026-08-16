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
    _parse_amount_string
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
