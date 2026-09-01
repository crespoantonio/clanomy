import asyncio
import logging
import httpx
from typing import Type
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.core.config import settings
from src.core.http_client import get_http_client
from src.core.ai_client import sanitize_prompt_input
from src.core.llm.base import BaseLLMProvider

logger = logging.getLogger(__name__)


class OpenAICompatibleProvider(BaseLLMProvider):
    """Cloud AI / OpenAI compatible provider for structured and text completions."""

    def __init__(
        self,
        model: str = settings.AI_MODEL,
        base_url: str = settings.AI_BASE_URL,
        api_key: str = settings.AI_API_KEY
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    @retry(
        stop=stop_after_attempt(settings.AI_MAX_RETRIES),
        wait=wait_exponential(multiplier=settings.AI_RETRY_BACKOFF_MIN, max=settings.AI_RETRY_BACKOFF_MAX),
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError, asyncio.TimeoutError, ConnectionError, OSError)),
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
            "temperature": temperature
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
        content = data["choices"][0]["message"]["content"]
        if not content:
            raise ValueError("Received empty response from Cloud AI provider")
        return content

    @retry(
        stop=stop_after_attempt(settings.AI_MAX_RETRIES),
        wait=wait_exponential(multiplier=settings.AI_RETRY_BACKOFF_MIN, max=settings.AI_RETRY_BACKOFF_MAX),
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError, asyncio.TimeoutError, ConnectionError, OSError)),
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
            "temperature": temperature
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
