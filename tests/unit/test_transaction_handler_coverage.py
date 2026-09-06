import pytest
import asyncio
from uuid import uuid4
import datetime
from unittest.mock import MagicMock, patch

from src.services.handlers.transaction_handler import (
    create_logged_task,
    format_currency,
    get_monthly_cash_flow_snapshot,
)
from src.db.models import Transaction

@pytest.mark.anyio
async def test_create_logged_task_success_and_error():
    # 1. Normal task completes
    async def normal_coro():
        return 42

    task1 = create_logged_task(normal_coro(), name="normal_task")
    await task1
    assert task1.result() == 42

    # 2. Task raises exception -> callback logs it
    async def failing_coro():
        raise ValueError("Task blew up")

    task2 = create_logged_task(failing_coro(), name="failing_task")
    with pytest.raises(ValueError, match="Task blew up"):
        await task2

    # 3. Cancelled task
    async def sleeping_coro():
        await asyncio.sleep(10)

    task3 = create_logged_task(sleeping_coro(), name="sleeping_task")
    task3.cancel()
    try:
        await task3
    except asyncio.CancelledError:
        pass

def test_format_currency_coverage():
    # Negative amount
    assert format_currency(-15.5, "USD") == "-$15.50 USD"

    # Positive with sign
    assert format_currency(20.0, "EUR", show_sign=True) == "+€20.00 EUR"

    # Other currency symbols
    assert "£" in format_currency(10.0, "GBP")
    assert "R$" in format_currency(10.0, "BRL")
    assert "S/" in format_currency(10.0, "PEN")

    # None currency fallback
    assert "USD" in format_currency(5.0, None)

def test_get_monthly_cash_flow_snapshot_december():
    fid = uuid4()
    target_date = datetime.datetime(2026, 12, 15, 10, 0, 0, tzinfo=datetime.timezone.utc)

    mock_sess = MagicMock()
    mock_sess.__enter__.return_value.exec.return_value.all.return_value = []
    mock_factory = MagicMock(return_value=mock_sess)

    snapshot = get_monthly_cash_flow_snapshot(fid, target_date, "USD", session_factory=mock_factory)
    assert snapshot["total_in"] == 0.0
    assert snapshot["total_out"] == 0.0
    assert snapshot["net_savings"] == 0.0
