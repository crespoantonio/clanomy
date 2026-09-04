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
from src.core.http_client import get_http_client, make_timeout
from src.core.ai_client import sanitize_prompt_input
from src.core.llm.base import BaseLLMProvider, PayloadTruncatedError
from src.core.llm.retry import is_retryable_provider_error, ProviderRateLimitWait

logger = logging.getLogger(__name__)


def _log_token_usage(data: dict, model: str) -> None:
    """Logs token consumption and reports cache HIT / MISS status for OpenAI/Groq requests."""
    usage = data.get("usage")
    if not isinstance(usage, dict):
        return
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    prompt_details = usage.get("prompt_tokens_details")
    cached_tokens = 0
    if isinstance(prompt_details, dict):
        cached_tokens = prompt_details.get("cached_tokens", 0)

    if cached_tokens > 0:
        logger.info(
            f"[Prompt Cache HIT] {cached_tokens}/{prompt_tokens} tokens served from cache for {model} (output: {completion_tokens})"
        )
    else:
        logger.info(
            f"[Prompt Cache MISS] 0/{prompt_tokens} cached (full inference run) for {model} (output: {completion_tokens})"
        )



class OpenAICompatibleProvider(BaseLLMProvider):
    """Cloud AI / OpenAI compatible provider for structured and text completions."""

    def __init__(
        self,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None
    ):
        self.model = model or settings.AI_MODEL
        self.base_url = (base_url or settings.AI_BASE_URL).rstrip("/")
        self.api_key = api_key or settings.AI_API_KEY


    @retry(
        stop=stop_after_attempt(settings.AI_MAX_RETRIES),
        wait=ProviderRateLimitWait(min_wait=settings.AI_RETRY_BACKOFF_MIN, max_wait=30.0),
        retry=retry_if_exception(is_retryable_provider_error),
        reraise=True
    )
    async def complete_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: Type[BaseModel],
        temperature: float = 0.0,
        timeout: float = 30.0,
        max_tokens: int = 600
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
            "max_tokens": max_tokens
        }


        logger.info(f"Calling Cloud AI model {self.model} at {self.base_url}...")
        response = await client.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=make_timeout(timeout, default_read=60.0)
        )
        response.raise_for_status()
        data = response.json()
        _log_token_usage(data, self.model)
        choice = data["choices"][0]
        if choice.get("finish_reason") == "length":
            raise PayloadTruncatedError("AI output exceeded token budget and was truncated.")
        content = choice["message"]["content"]
        if not content:
            raise ValueError("Received empty response from Cloud AI provider")
        return content

    @retry(
        stop=stop_after_attempt(settings.AI_MAX_RETRIES),
        wait=ProviderRateLimitWait(min_wait=settings.AI_RETRY_BACKOFF_MIN, max_wait=30.0),
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
            timeout=make_timeout(timeout, default_read=30.0)
        )
        response.raise_for_status()
        data = response.json()
        _log_token_usage(data, self.model)
        content = data["choices"][0]["message"]["content"]
        return content.strip() if content else ""
