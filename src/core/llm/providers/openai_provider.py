import asyncio
import logging
import random
import re
from typing import Optional, Type
import httpx
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, retry_if_exception, RetryCallState
from tenacity.wait import wait_base

from src.core.config import settings
from src.core.http_client import get_http_client
from src.core.ai_client import sanitize_prompt_input
from src.core.llm.base import BaseLLMProvider
from src.services.extraction.models import PayloadTruncatedError

logger = logging.getLogger(__name__)


def is_retryable_provider_error(exception: BaseException) -> bool:
    """
    Only retries transient network errors, rate limits (429), and server errors (5xx).
    Never retries client errors (400, 401, 403, 404, 422) or deterministic truncation.
    """
    if isinstance(exception, PayloadTruncatedError):
        return False
    if isinstance(exception, (httpx.RequestError, asyncio.TimeoutError, ConnectionError, OSError)):
        return True
    if isinstance(exception, httpx.HTTPStatusError):
        status = exception.response.status_code
        return status == 429 or status >= 500
    return False


class OpenAIRateLimitWait(wait_base):
    """
    Dynamic wait strategy that inspects Retry-After or rate-limit reset headers
    when facing HTTP 429, adding jitter and falling back to exponential backoff.
    """
    def __init__(self, min_wait: float = 0.5, max_wait: float = 30.0):
        self.min_wait = min_wait
        self.max_wait = max_wait

    def __call__(self, retry_state: RetryCallState) -> float:
        exc = retry_state.outcome.exception() if retry_state.outcome else None
        if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429:
            resp = exc.response
            # 1. Standard RFC Retry-After header
            retry_after = resp.headers.get("Retry-After")
            if retry_after:
                try:
                    delay = float(retry_after) + random.uniform(0.1, 0.5)
                    logger.warning(f"[RateLimit 429] Respecting Retry-After header: sleeping {delay:.2f}s")
                    return min(max(delay, self.min_wait), self.max_wait)
                except ValueError:
                    pass

            # 2. Provider specific reset headers (e.g. Groq x-ratelimit-reset-tokens or x-ratelimit-reset-requests)
            reset_header = resp.headers.get("x-ratelimit-reset-tokens") or resp.headers.get("x-ratelimit-reset-requests")
            if reset_header:
                match = re.search(r"(\d+(?:\.\d+)?)\s*(s|ms)?", reset_header)
                if match:
                    val = float(match.group(1))
                    unit = match.group(2)
                    delay = (val / 1000.0 if unit == "ms" else val) + random.uniform(0.1, 0.5)
                    logger.warning(f"[RateLimit 429] Respecting {reset_header} header: sleeping {delay:.2f}s")
                    return min(max(delay, self.min_wait), self.max_wait)

        # 3. Fallback: Full Jitter Exponential Backoff
        attempt = retry_state.attempt_number
        base_delay = min(self.max_wait, self.min_wait * (2 ** (attempt - 1)))
        return base_delay * random.uniform(0.5, 1.0)


class OpenAICompatibleProvider(BaseLLMProvider):
    """Cloud AI / OpenAI compatible provider for structured and text completions."""

    def __init__(
        self,
        model: str = settings.AI_MODEL,
        base_url: str = settings.AI_BASE_URL,
        api_key: Optional[str] = None
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or settings.AI_API_KEY

    @retry(
        stop=stop_after_attempt(settings.AI_MAX_RETRIES),
        wait=OpenAIRateLimitWait(min_wait=settings.AI_RETRY_BACKOFF_MIN, max_wait=30.0),
        retry=retry_if_exception(is_retryable_provider_error),
        reraise=True
    )
    async def complete_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: Type[BaseModel],
        temperature: float = 0.0,
        timeout: float = 30.0
    ) -> str:
        client = get_http_client()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        sanitized_user = sanitize_prompt_input(user_prompt)
        
        # Include schema description in system prompt for OpenAI compatible endpoints
        schema_json = schema.model_json_schema()
        full_system_prompt = f"{system_prompt}\n\nRequired JSON Schema:\n{schema_json}"

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": full_system_prompt},
                {"role": "user", "content": sanitized_user}
            ],
            "response_format": {"type": "json_object"},
            "temperature": temperature,
            "max_tokens": 2000
        }

        logger.info(f"Calling Cloud AI model {self.model} at {self.base_url}...")
        response = await client.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=timeout
        )
        response.raise_for_status()
        data = response.json()
        choice = data["choices"][0]
        if choice.get("finish_reason") == "length":
            raise PayloadTruncatedError("AI output exceeded token budget and was truncated.")
        content = choice["message"]["content"]
        if not content:
            raise ValueError("Received empty response from Cloud AI provider")
        return content

    @retry(
        stop=stop_after_attempt(settings.AI_MAX_RETRIES),
        wait=OpenAIRateLimitWait(min_wait=settings.AI_RETRY_BACKOFF_MIN, max_wait=30.0),
        retry=retry_if_exception(is_retryable_provider_error),
        reraise=True
    )
    async def complete_text(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        timeout: float = 30.0
    ) -> str:
        client = get_http_client()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        sanitized_user = sanitize_prompt_input(user_prompt)

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": sanitized_user}
            ],
            "temperature": temperature,
            "max_tokens": 300
        }

        logger.info(f"Calling Cloud AI model {self.model} at {self.base_url} for text summary...")
        response = await client.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=timeout
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        return content.strip() if content else ""
