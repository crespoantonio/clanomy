import asyncio
import json
import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch
from pydantic import BaseModel

from src.core.config import Settings
from src.core.security import sanitize_auth_tokens, sanitize_exception_message
from src.core.llm.providers.openai_provider import (
    OpenAICompatibleProvider,
    is_retryable_provider_error,
    OpenAIRateLimitWait,
)
from src.services.whisper_service import WhisperService
from src.services.telegram_service import TelegramService
from src.services.query.service import QueryService, ParsedQueryIntent


class DummySchema(BaseModel):
    category: str


# ---------------------------------------------------------------------------
# 1. Retry Predicate & Rate Limit Backoff Tests
# ---------------------------------------------------------------------------

def test_is_retryable_provider_error_transient_network():
    req = httpx.Request("POST", "https://api.groq.com")
    assert is_retryable_provider_error(httpx.ConnectError("Connection refused", request=req))
    assert is_retryable_provider_error(httpx.ReadTimeout("Timeout", request=req))
    assert is_retryable_provider_error(ConnectionError("Connection lost"))
    assert is_retryable_provider_error(OSError("Network down"))
    assert is_retryable_provider_error(asyncio.TimeoutError())


def test_is_retryable_provider_error_http_status():
    req = httpx.Request("POST", "https://api.groq.com")

    # 429 and 5xx are retryable
    resp_429 = httpx.Response(429, request=req)
    assert is_retryable_provider_error(httpx.HTTPStatusError("429", request=req, response=resp_429))

    resp_500 = httpx.Response(500, request=req)
    assert is_retryable_provider_error(httpx.HTTPStatusError("500", request=req, response=resp_500))

    resp_503 = httpx.Response(503, request=req)
    assert is_retryable_provider_error(httpx.HTTPStatusError("503", request=req, response=resp_503))

    # 4xx client errors are NOT retryable
    for code in (400, 401, 403, 404, 422):
        resp = httpx.Response(code, request=req)
        err = httpx.HTTPStatusError(str(code), request=req, response=resp)
        assert not is_retryable_provider_error(err), f"HTTP {code} should not be retryable"


def test_openai_rate_limit_wait_with_retry_after():
    wait_strategy = OpenAIRateLimitWait(min_wait=1.0, max_wait=30.0)
    req = httpx.Request("POST", "https://api.groq.com")
    resp = httpx.Response(429, request=req, headers={"Retry-After": "4.5"})
    err = httpx.HTTPStatusError("429", request=req, response=resp)

    retry_state = MagicMock()
    retry_state.outcome.exception.return_value = err
    retry_state.attempt_number = 1

    delay = wait_strategy(retry_state)
    assert 4.5 <= delay <= 5.5


def test_openai_rate_limit_wait_with_groq_reset_header():
    wait_strategy = OpenAIRateLimitWait(min_wait=0.5, max_wait=30.0)
    req = httpx.Request("POST", "https://api.groq.com")
    resp = httpx.Response(429, request=req, headers={"x-ratelimit-reset-tokens": "2.2s"})
    err = httpx.HTTPStatusError("429", request=req, response=resp)

    retry_state = MagicMock()
    retry_state.outcome.exception.return_value = err
    retry_state.attempt_number = 1

    delay = wait_strategy(retry_state)
    assert 2.2 <= delay <= 3.0


# ---------------------------------------------------------------------------
# 2. Token Budget Enforcement Tests
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_openai_provider_enforces_max_tokens_payload():
    provider = OpenAICompatibleProvider(api_key="gsk_mock_test")

    mock_client = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": '{"category": "Food"}'}}]
    }
    mock_resp.raise_for_status.return_value = None
    mock_client.post.return_value = mock_resp

    with patch("src.core.llm.providers.openai_provider.get_http_client", return_value=mock_client):
        # 1. Structured output max_tokens=600
        res = await provider.complete_structured(
            system_prompt="sys",
            user_prompt="user",
            schema=DummySchema
        )
        assert res == '{"category": "Food"}'
        call_kwargs = mock_client.post.call_args.kwargs
        assert call_kwargs["json"]["max_tokens"] == 600

        # 2. Text summary max_tokens=300
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "This is a summary."}}]
        }
        summary = await provider.complete_text(
            system_prompt="sys",
            user_prompt="user"
        )
        assert summary == "This is a summary."
        call_kwargs = mock_client.post.call_args.kwargs
        assert call_kwargs["json"]["max_tokens"] == 300


# ---------------------------------------------------------------------------
# 3. Whisper Failover to Local Faster-Whisper
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_whisper_service_falls_back_to_local_on_cloud_failure():
    service = WhisperService()

    # Mock Cloud Whisper returning 429
    mock_client = AsyncMock()
    req = httpx.Request("POST", "https://api.groq.com/openai/v1/audio/transcriptions")
    resp_429 = httpx.Response(429, request=req)
    mock_client.post.side_effect = httpx.HTTPStatusError("Rate limited", request=req, response=resp_429)

    mock_segment = MagicMock()
    mock_segment.text = "fallback text"
    mock_info = MagicMock()
    mock_info.language = "en"
    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([mock_segment], mock_info)

    with patch("src.services.whisper_service.get_http_client", return_value=mock_client), \
         patch("src.services.whisper_service.settings.AI_API_KEY", "gsk_valid_key"), \
         patch.object(service, "get_model", return_value=mock_model) as mock_get_model:

        text, lang = await service.transcribe(audio_bytes=b"fake_audio_bytes", language="en")
        assert text == "fallback text"
        assert lang == "en"
        assert mock_get_model.called
        assert mock_model.transcribe.called


# ---------------------------------------------------------------------------
# 4. Telegram 429 Retry Handling
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_telegram_service_retries_on_429():
    service = TelegramService()
    mock_client = AsyncMock()

    req = httpx.Request("POST", "https://api.telegram.org/bot123/sendMessage")
    resp_429 = httpx.Response(
        429,
        request=req,
        json={"ok": False, "error_code": 429, "parameters": {"retry_after": 0.01}}
    )
    resp_200 = httpx.Response(200, request=req, json={"ok": True, "result": {"message_id": 42}})

    # First call returns 429, second succeeds with 200
    mock_client.post.side_effect = [resp_429, resp_200]

    with patch("src.services.telegram_service.get_http_client", return_value=mock_client):
        resp = await service._post_with_retry("sendMessage", max_attempts=3, json={"chat_id": 1, "text": "hi"})
        assert resp.status_code == 200
        assert mock_client.post.call_count == 2


# ---------------------------------------------------------------------------
# 5. Configuration Aliasing
# ---------------------------------------------------------------------------

def test_settings_aliases_groq_and_api_base_url():
    # Pass GROQ_API_KEY and AI_API_BASE_URL to verify AliasChoices resolve correctly
    s = Settings(
        ENCRYPTION_KEY="MDEyMzQ1Njc4OTAxMjM0NTY3ODkwMTIzNDU2Nzg5MDE=",
        TELEGRAM_BOT_TOKEN="mock_tg_token",
        MESSAGING_WEBHOOK_SECRET="mock_secret",
        DATABASE_URL="sqlite:///:memory:",
        GROQ_API_KEY="gsk_aliased_key_12345",
        AI_API_BASE_URL="https://api.groq.com/v1"
    )
    assert s.AI_API_KEY == "gsk_aliased_key_12345"
    assert s.AI_BASE_URL == "https://api.groq.com/v1"


# ---------------------------------------------------------------------------
# 6. Security Sanitization (Bearer & Token Redaction)
# ---------------------------------------------------------------------------

def test_sanitize_auth_tokens_redacts_keys():
    raw_error = "Error calling API: Authorization: Bearer some_secret_token and key gsk_123456789012345678901234 on token 1234567890:ABCdefGHIjklMNOpqrsTUVwxyz1234567"
    sanitized = sanitize_auth_tokens(raw_error)
    assert "Bearer [REDACTED]" in sanitized
    assert "gsk_[REDACTED]" in sanitized
    assert "[TELEGRAM_TOKEN_REDACTED]" in sanitized
    assert "some_secret_token" not in sanitized
    assert "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz1234567" not in sanitized


def test_sanitize_exception_message_masks_both_db_and_auth():
    raw_msg = "Database postgresql+psycopg://user:secretpassword@localhost:5432/db failed with gsk_abcdef1234567890abcdef123456"
    sanitized = sanitize_exception_message(raw_msg)
    assert ":***@" in sanitized
    assert "secretpassword" not in sanitized
    assert "gsk_[REDACTED]" in sanitized


# ---------------------------------------------------------------------------
# 7. QueryService Intent Fallback on LLM Error
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_query_service_parse_intent_fallback():
    mock_provider = AsyncMock()
    # Simulate LLM returning invalid schema or non-JSON output that causes ValidationError/ValueError
    mock_provider.complete_structured.return_value = '{"intent": "unrecognized_intent", "timeframe": "never"}'

    service = QueryService(provider=mock_provider)
    intent = await service.parse_intent("how much did we spend on food this month?")

    assert isinstance(intent, ParsedQueryIntent)
    assert intent.intent == "spending_summary"
    assert intent.timeframe == "this_month"
