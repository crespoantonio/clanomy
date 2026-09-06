import pytest
import httpx
from unittest.mock import MagicMock, patch
from src.core.llm.retry import ProviderRateLimitWait
from src.core.llm.factory import get_llm_provider
from src.core.llm.providers.gemini_provider import GeminiProvider
from src.core.llm.providers.openai_provider import OpenAICompatibleProvider
from src.core.llm.providers.ollama_provider import OllamaProvider
from src.core.config import settings

def test_provider_rate_limit_gemini_retry_delay():
    wait_strategy = ProviderRateLimitWait(min_wait=0.5, max_wait=30.0)
    req = httpx.Request("POST", "https://generativelanguage.googleapis.com")
    resp_body = {
        "error": {
            "code": 429,
            "message": "Resource exhausted",
            "details": [
                {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "3.5s"}
            ]
        }
    }
    resp = httpx.Response(429, request=req, json=resp_body)
    err = httpx.HTTPStatusError("429", request=req, response=resp)

    retry_state = MagicMock()
    retry_state.outcome.exception.return_value = err
    retry_state.attempt_number = 1

    delay = wait_strategy(retry_state)
    assert 3.5 <= delay <= 4.5

def test_provider_rate_limit_gemini_retry_delay_clean_number():
    wait_strategy = ProviderRateLimitWait(min_wait=0.5, max_wait=30.0)
    req = httpx.Request("POST", "https://generativelanguage.googleapis.com")
    resp_body = {"error": {"details": [{"retryDelay": "2"}]}}
    resp = httpx.Response(429, request=req, json=resp_body)
    err = httpx.HTTPStatusError("429", request=req, response=resp)

    retry_state = MagicMock()
    retry_state.outcome.exception.return_value = err
    retry_state.attempt_number = 1

    delay = wait_strategy(retry_state)
    assert 2.0 <= delay <= 3.0

def test_provider_rate_limit_fallback_exponential_backoff():
    wait_strategy = ProviderRateLimitWait(min_wait=1.0, max_wait=10.0)
    # When error is 500 (not 429), falls back to exponential backoff
    req = httpx.Request("POST", "https://api.groq.com")
    resp = httpx.Response(500, request=req)
    err = httpx.HTTPStatusError("500", request=req, response=resp)

    retry_state = MagicMock()
    retry_state.outcome.exception.return_value = err
    retry_state.attempt_number = 2

    delay = wait_strategy(retry_state)
    # attempt 2: base_delay = min(10.0, 1.0 * 2^1) = 2.0. With jitter [0.5, 1.0]: 1.0 <= delay <= 2.0
    assert 0.8 <= delay <= 2.2

def test_provider_rate_limit_invalid_json_falls_back():
    wait_strategy = ProviderRateLimitWait(min_wait=0.5, max_wait=30.0)
    req = httpx.Request("POST", "https://api.groq.com")
    resp = httpx.Response(429, request=req, content=b"Non-JSON error page")
    err = httpx.HTTPStatusError("429", request=req, response=resp)

    retry_state = MagicMock()
    retry_state.outcome.exception.return_value = err
    retry_state.attempt_number = 1

    delay = wait_strategy(retry_state)
    assert delay >= 0.2

def test_llm_factory_auto_detection():
    # 1. Explicit Gemini
    p1 = get_llm_provider("gemini")
    assert isinstance(p1, GeminiProvider)

    # 2. Explicit Google alias
    p2 = get_llm_provider("google")
    assert isinstance(p2, GeminiProvider)

    # 3. Explicit Ollama
    p3 = get_llm_provider("ollama")
    assert isinstance(p3, OllamaProvider)

    from src.core.config import Settings
    # 4. Fallback based on AI_API_KEY starting with AIzaSy
    with patch.object(Settings, "effective_ai_provider", None), \
         patch.object(settings, "AI_API_KEY", "AIzaSy_fake_key_123"):
        p4 = get_llm_provider()
        assert isinstance(p4, GeminiProvider)

    # 5. Fallback based on non-Gemini AI_API_KEY (e.g. gsk_)
    with patch.object(Settings, "effective_ai_provider", None), \
         patch.object(settings, "AI_API_KEY", "gsk_fake_key_123"):
        p5 = get_llm_provider()
        assert isinstance(p5, OpenAICompatibleProvider)

    # 6. Fallback when no AI_API_KEY
    with patch.object(Settings, "effective_ai_provider", None), \
         patch.object(settings, "AI_API_KEY", None):
        p6 = get_llm_provider()
        assert isinstance(p6, OllamaProvider)
