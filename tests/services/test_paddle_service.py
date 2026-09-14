"""
Unit tests for PaddleService:
- Signature verification.
- Timestamp drift tolerance.
- Checkout transaction URL creation.
- Customer portal session creation.
"""

import time
import hmac
import hashlib
import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock

from src.services.billing.paddle_service import PaddleService
from src.core.config import settings


@pytest.fixture
def paddle_service():
    return PaddleService(
        api_key="pdl_sdbx_apikey_test123",
        webhook_secret="pdl_ntfset_secret123",
        environment="sandbox"
    )


def test_verify_webhook_signature_valid(paddle_service):
    """Test valid signature passes verification."""
    raw_body = '{"event_id": "123"}'
    ts = int(time.time())
    signed_payload = f"{ts}:{raw_body}"
    h1 = hmac.new(b"pdl_ntfset_secret123", signed_payload.encode("utf-8"), hashlib.sha256).hexdigest()
    header = f"ts={ts};h1={h1}"

    assert paddle_service.verify_webhook_signature(raw_body, header) is True


def test_verify_webhook_signature_invalid_hash(paddle_service):
    """Test signature mismatch returns False."""
    raw_body = '{"event_id": "123"}'
    ts = int(time.time())
    header = f"ts={ts};h1=wrong_hash"

    assert paddle_service.verify_webhook_signature(raw_body, header) is False


def test_verify_webhook_signature_expired_timestamp(paddle_service):
    """Test timestamp drift > 5s returns False."""
    raw_body = '{"event_id": "123"}'
    ts = int(time.time()) - 10
    signed_payload = f"{ts}:{raw_body}"
    h1 = hmac.new(b"pdl_ntfset_secret123", signed_payload.encode("utf-8"), hashlib.sha256).hexdigest()
    header = f"ts={ts};h1={h1}"

    assert paddle_service.verify_webhook_signature(raw_body, header) is False


def test_verify_webhook_signature_missing_components(paddle_service):
    """Test malformed headers return False."""
    assert paddle_service.verify_webhook_signature("{}", "") is False
    assert paddle_service.verify_webhook_signature("", "ts=123;h1=abc") is False
    assert paddle_service.verify_webhook_signature("{}", "invalid_header") is False


@pytest.mark.anyio
async def test_create_checkout_url_success(paddle_service, monkeypatch):
    """Test successful checkout URL creation via Paddle API."""
    settings.PADDLE_PRICE_ID_SOLO_PRO = "pri_solo_test_123"

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {
            "id": "txn_test_123",
            "checkout": {
                "url": "https://pay.paddle.com/checkout/txn_test_123"
            }
        }
    }

    with patch("src.services.billing.paddle_service.get_http_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_get_client.return_value = mock_client

        url = await paddle_service.create_checkout_url(
            family_id="fam_123",
            user_id="usr_123",
            plan_code="solo_pro"
        )
        assert url == "https://pay.paddle.com/checkout/txn_test_123"

        # Verify payload structure
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args.kwargs["json"]["items"][0]["price_id"] == "pri_solo_test_123"
        assert call_args.kwargs["json"]["custom_data"]["family_id"] == "fam_123"


@pytest.mark.anyio
async def test_create_checkout_url_unconfigured_price(paddle_service):
    """Test checkout returns None when price ID is not configured."""
    settings.PADDLE_PRICE_ID_SOLO_PRO = None
    url = await paddle_service.create_checkout_url(
        family_id="fam_123",
        user_id="usr_123",
        plan_code="solo_pro"
    )
    assert url is None


@pytest.mark.anyio
async def test_create_customer_portal_session_success(paddle_service):
    """Test customer portal session overview URL generation."""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {
            "id": "cpls_123",
            "urls": {
                "general": {
                    "overview": "https://customer-portal.paddle.com/overview_link?token=abc"
                }
            }
        }
    }

    with patch("src.services.billing.paddle_service.get_http_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_get_client.return_value = mock_client

        url = await paddle_service.create_customer_portal_session(
            customer_id="ctm_123",
            subscription_ids=["sub_123"]
        )
        assert url == "https://customer-portal.paddle.com/overview_link?token=abc"
