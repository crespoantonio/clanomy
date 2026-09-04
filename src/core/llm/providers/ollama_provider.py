import asyncio
import logging
import ollama
from typing import Type
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.core.config import settings
from src.core.ai_client import get_global_ollama_semaphore, sanitize_prompt_input
from src.core.llm.base import BaseLLMProvider

logger = logging.getLogger(__name__)


class OllamaProvider(BaseLLMProvider):
    """Local Ollama LLM provider with shared GPU concurrency management."""

    def __init__(self, model: Optional[str] = None, host: Optional[str] = None):
        self.model = model or settings.OLLAMA_MODEL
        self.host = host or settings.OLLAMA_BASE_URL
        self.client = ollama.AsyncClient(host=self.host)

    @retry(
        stop=stop_after_attempt(settings.AI_MAX_RETRIES),
        wait=wait_exponential(multiplier=settings.AI_RETRY_BACKOFF_MIN, max=settings.AI_RETRY_BACKOFF_MAX),
        retry=retry_if_exception_type((ollama.ResponseError, ollama.RequestError, asyncio.TimeoutError, ConnectionError, OSError)),
        reraise=True
    )
    async def complete_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: Type[BaseModel],
        temperature: float = 0.0,
        timeout: float = 60.0,
        max_tokens: int = 600
    ) -> str:

        sanitized_user = sanitize_prompt_input(user_prompt)
        logger.info(f"Calling Ollama model {self.model} for structured completion...")
        async with get_global_ollama_semaphore():
            response = await asyncio.wait_for(
                self.client.chat(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": sanitized_user}
                    ],
                    format=schema.model_json_schema(),
                    options={"temperature": temperature, "num_predict": max_tokens}
                ),
                timeout=timeout
            )
            content = response.message.content
            if not content:
                raise ValueError("Received empty response from Ollama")
            return content

    @retry(
        stop=stop_after_attempt(settings.AI_MAX_RETRIES),
        wait=wait_exponential(multiplier=settings.AI_RETRY_BACKOFF_MIN, max=settings.AI_RETRY_BACKOFF_MAX),
        retry=retry_if_exception_type((ollama.ResponseError, ollama.RequestError, asyncio.TimeoutError, ConnectionError, OSError)),
        reraise=True
    )
    async def complete_text(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        timeout: float = 30.0
    ) -> str:
        sanitized_user = sanitize_prompt_input(user_prompt)
        logger.info(f"Calling Ollama model {self.model} for text completion...")
        async with get_global_ollama_semaphore():
            response = await asyncio.wait_for(
                self.client.chat(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": sanitized_user}
                    ],
                    options={"temperature": temperature} if temperature > 0 else None
                ),
                timeout=timeout
            )
            content = response.message.content if response.message else ""
            return content.strip() if content else ""
