import pytest
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch

from src.db.models import User, Family, Transaction, ScheduledBill
from src.services.query.models import DecryptedTransaction, DecryptedScheduledBill
from src.services.handlers.command_handler import CommandHandler
from src.services.query.formatters import (
    format_month_summary,
    format_me_summary,
    format_today_summary,
    format_bills_summary,
    format_balance_summary,
    format_currency_dict
)
from src.services.query.aggregator import (
    aggregate_transactions,
    aggregate_by_member,
    aggregate_by_category
)

@pytest.mark.anyio
async def test_format_currency_dict():
    assert format_currency_dict({}) == "0.00 USD"
    assert format_currency_dict({"USD": 125.5}) == "125.50 USD"
    assert format_currency_dict({"USD": 100.0, "EUR": 50.0}) == "50.00 EUR, 100.00 USD"

@pytest.mark.anyio
async def test_aggregate_by_member_multi_currency():
    user1_id = uuid.uuid4()
    user2_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    txs = [
        DecryptedTransaction(
            id=uuid.uuid4(),
            family_id=uuid.uuid4(),
            user_id=user1_id,
            user_name="Tony",
            amount=3000.0,
            currency="USD",
            concept="Salary",
            category="Salary",
            type="income",
            timestamp=now
        ),
        DecryptedTransaction(
            id=uuid.uuid4(),
            family_id=uuid.uuid4(),
            user_id=user1_id,
            user_name="Tony",
            amount=800.0,
            currency="USD",
            concept="Groceries",
            category="Food/Drink",
            type="expense",
            timestamp=now
        ),
        DecryptedTransaction(
            id=uuid.uuid4(),
            family_id=uuid.uuid4(),
            user_id=user2_id,
            user_name="Maria",
            amount=500.0,
            currency="EUR",
            concept="Freelance",
            category="Freelance",
            type="income",
            timestamp=now
        ),
        DecryptedTransaction(
            id=uuid.uuid4(),
            family_id=uuid.uuid4(),
            user_id=user2_id,
            user_name="Maria",
            amount=200.0,
            currency="EUR",
            concept="Electricity",
            category="Rent/Bills",
            type="expense",
            timestamp=now
        ),
    ]

    mb = aggregate_by_member(txs, primary_currency="USD")
    assert len(mb.members) == 2

    tony = next(m for m in mb.members.values() if m.user_name == "Tony")
    assert tony.income_currency_totals["USD"] == 3000.0
    assert tony.expense_currency_totals["USD"] == 800.0
    assert tony.total_earned == 3000.0
    assert tony.total_spent == 800.0

    maria = next(m for m in mb.members.values() if m.user_name == "Maria")
    assert maria.income_currency_totals["EUR"] == 500.0
    assert maria.expense_currency_totals["EUR"] == 200.0

@pytest.mark.anyio
async def test_command_handler_handle_month():
    handler = CommandHandler()
    family_id = uuid.uuid4()
    user_id = uuid.uuid4()
    
    family = Family(id=family_id, name="Smith Family", default_currency="USD")
    user = User(id=user_id, family_id=family_id, username="tony", full_name="Tony Smith")

    now = datetime.now(timezone.utc)
    mock_txs = [
        DecryptedTransaction(
            id=uuid.uuid4(),
            family_id=family_id,
            user_id=user_id,
            user_name="Tony Smith",
            amount=4000.0,
            currency="USD",
            concept="Salary",
            category="Salary",
            type="income",
            timestamp=now
        ),
        DecryptedTransaction(
            id=uuid.uuid4(),
            family_id=family_id,
            user_id=user_id,
            user_name="Tony Smith",
            amount=1200.0,
            currency="USD",
            concept="Rent",
            category="Rent/Bills",
            type="expense",
            timestamp=now
        )
    ]

    with patch.object(handler.query_service, "_fetch_and_decrypt_transactions", return_value=mock_txs):
        result = await handler.handle_month(user, family)
        assert "Family Summary" in result
        assert "Smith Family" in result
        assert "4,000.00 USD" in result
        assert "1,200.00 USD" in result
        assert "Tony Smith" in result

@pytest.mark.anyio
async def test_command_handler_handle_me():
    handler = CommandHandler()
    family_id = uuid.uuid4()
    user1_id = uuid.uuid4()
    user2_id = uuid.uuid4()
    
    family = Family(id=family_id, name="Smith Family", default_currency="USD")
    user1 = User(id=user1_id, family_id=family_id, username="tony", full_name="Tony Smith")

    now = datetime.now(timezone.utc)
    mock_txs = [
        DecryptedTransaction(
            id=uuid.uuid4(),
            family_id=family_id,
            user_id=user1_id,
            user_name="Tony Smith",
            amount=2500.0,
            currency="USD",
            concept="Salary",
            category="Salary",
            type="income",
            timestamp=now
        ),
        DecryptedTransaction(
            id=uuid.uuid4(),
            family_id=family_id,
            user_id=user1_id,
            user_name="Tony Smith",
            amount=500.0,
            currency="USD",
            concept="Food",
            category="Food/Drink",
            type="expense",
            timestamp=now
        ),
        DecryptedTransaction(
            id=uuid.uuid4(),
            family_id=family_id,
            user_id=user2_id,
            user_name="Maria Smith",
            amount=800.0,
            currency="USD",
            concept="Shopping",
            category="Shopping",
            type="expense",
            timestamp=now
        )
    ]

    with patch.object(handler.query_service, "_fetch_and_decrypt_transactions", return_value=mock_txs):
        result = await handler.handle_me(user1, family)
        assert "Personal Summary" in result
        assert "Tony Smith" in result
        assert "2,500.00 USD" in result
        assert "500.00 USD" in result
        # Maria's shopping should NOT be in Tony's personal summary
        assert "800.00" not in result

@pytest.mark.anyio
async def test_command_handler_handle_today_and_bills():
    handler = CommandHandler()
    family_id = uuid.uuid4()
    user_id = uuid.uuid4()
    
    family = Family(id=family_id, name="Smith Family", default_currency="USD")
    user = User(id=user_id, family_id=family_id, username="tony", full_name="Tony")

    now = datetime.now(timezone.utc)
    mock_txs = [
        DecryptedTransaction(
            id=uuid.uuid4(),
            family_id=family_id,
            user_id=user_id,
            user_name="Tony",
            amount=45.0,
            currency="USD",
            concept="Dinner",
            category="Food/Drink",
            type="expense",
            timestamp=now
        )
    ]

    mock_bills = [
        DecryptedScheduledBill(
            id=uuid.uuid4(),
            family_id=family_id,
            user_id=user_id,
            user_name="Tony",
            amount=150.0,
            currency="USD",
            concept="Internet Bill",
            category="Rent/Bills",
            due_date=now + timedelta(days=5),
            status="pending",
            created_at=now
        )
    ]

    with patch.object(handler.query_service, "_fetch_and_decrypt_transactions", return_value=mock_txs):
        today_res = await handler.handle_today(user, family)
        assert "Today's Activity" in today_res
        assert "45.00 USD" in today_res

    with patch.object(handler.query_service, "_fetch_and_decrypt_scheduled_bills", return_value=mock_bills) as mock_fetch:
        bills_res = await handler.handle_bills(user, family)
        assert "Upcoming Bills" in bills_res
        assert "Internet Bill" in bills_res
        assert "150.00 USD" in bills_res
        assert "Total Pending" in bills_res
        
        # Verify date range passed covers the entire month
        call_args = mock_fetch.call_args[0]
        start_time, end_time = call_args[1], call_args[2]
        assert start_time.day == 1
        # end_time should be at the end of the month, not capped at today
        assert end_time > now

    # Test /bills next (next_month)
    with patch.object(handler.query_service, "_fetch_and_decrypt_scheduled_bills", return_value=mock_bills) as mock_fetch_next:
        bills_next_res = await handler.handle_bills(user, family, args="next")
        assert "Upcoming Bills — Next Month" in bills_next_res
        call_args_next = mock_fetch_next.call_args[0]
        start_next, end_next = call_args_next[1], call_args_next[2]
        assert start_next > now
        assert end_next > start_next
