import asyncio
import pytest
import httpx
from unittest.mock import MagicMock

from src.core.http_client import make_timeout
from src.core.llm.retry import ProviderRateLimitWait, is_retryable_provider_error
from src.core.llm.base import PayloadTruncatedError
from src.services.extraction.fallback import _parse_amount_str, fallback_regex_extract
from src.services.ai_orchestrator import _BoundedLockStore


def test_parse_amount_str_various_formats():
    # European / Latin American decimal comma
    assert _parse_amount_str("1,50") == 1.50
    assert _parse_amount_str("1,5") == 1.5
    assert _parse_amount_str("12,50") == 12.50
    assert _parse_amount_str("1.250,50") == 1250.50
    assert _parse_amount_str("12.500,75") == 12500.75

    # Standard dot decimal
    assert _parse_amount_str("1,250.50") == 1250.50
    assert _parse_amount_str("15.50") == 15.50
    assert _parse_amount_str("0.99") == 0.99

    # Whole numbers and thousands
    assert _parse_amount_str("1000") == 1000.0
    assert _parse_amount_str("1,000") == 1000.0
    assert _parse_amount_str("1.000") == 1000.0
    assert _parse_amount_str("50000") == 50000.0

    # With currency symbols
    assert _parse_amount_str("$1,50") == 1.50
    assert _parse_amount_str("€12.50") == 12.50
    assert _parse_amount_str("£1.250,50") == 1250.50


def test_fallback_regex_extract_decimal_comma():
    res1 = fallback_regex_extract("1,50 en pan", default_currency="EUR")
    assert res1.amount == 1.50
    assert res1.currency == "EUR"

    res2 = fallback_regex_extract("1.250,50 alquiler", default_currency="EUR")
    assert res2.amount == 1250.50

    res3 = fallback_regex_extract("1,250.50 on groceries", default_currency="USD")
    assert res3.amount == 1250.50

    res4 = fallback_regex_extract("1000 en zapatillas", default_currency="ARS")
    assert res4.amount == 1000.0


def test_make_timeout_preserves_connect_and_pool():
    t_default = make_timeout()
    assert t_default.read == 30.0
    assert t_default.connect == 5.0
    assert t_default.pool == 5.0

    t_custom = make_timeout(60.0)
    assert t_custom.read == 60.0
    assert t_custom.connect == 5.0
    assert t_custom.pool == 5.0

    existing_timeout = httpx.Timeout(12.0, connect=2.0, pool=2.0)
    t_pass = make_timeout(existing_timeout)
    assert t_pass is existing_timeout


@pytest.mark.anyio
async def test_bounded_lock_store_evicts_only_unlocked():
    store = _BoundedLockStore(max_entries=2)

    # Acquire lock for key1
    lock1 = store["user_1"]
    await lock1.acquire()

    # Add key2 and key3
    lock2 = store["user_2"]
    lock3 = store["user_3"]

    # Since user_1 is still locked, it should NOT be evicted
    assert "user_1" in store._locks
    assert store["user_1"] is lock1

    lock1.release()


def test_retry_helper_classification():
    assert is_retryable_provider_error(PayloadTruncatedError("Truncated")) is False
    assert is_retryable_provider_error(asyncio.TimeoutError()) is True
    assert is_retryable_provider_error(ConnectionError()) is True

    # 429 is retryable
    resp_429 = MagicMock()
    resp_429.status_code = 429
    err_429 = httpx.HTTPStatusError("Rate limited", request=MagicMock(), response=resp_429)
    assert is_retryable_provider_error(err_429) is True

    # 400 is not retryable
    resp_400 = MagicMock()
    resp_400.status_code = 400
    err_400 = httpx.HTTPStatusError("Bad Request", request=MagicMock(), response=resp_400)
    assert is_retryable_provider_error(err_400) is False
