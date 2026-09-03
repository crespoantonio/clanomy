import logging
from typing import Optional, Type
import httpx
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, retry_if_exception

from src.core.config import settings
from src.core.http_client import get_http_client
from src.core.ai_client import sanitize_prompt_input
from src.core.llm.base import BaseLLMProvider, PayloadTruncatedError
from src.core.llm.providers.openai_provider import OpenAIRateLimitWait, is_retryable_provider_error

logger = logging.getLogger(__name__)


def _log_gemini_token_usage(data: dict, model: str) -> None:
    """Logs token consumption and reports cache HIT / MISS status for Gemini requests."""
    usage = data.get("usageMetadata")
    if not isinstance(usage, dict):
        return
    prompt_tokens = usage.get("promptTokenCount", 0)
    candidates_tokens = usage.get("candidatesTokenCount", 0)
    cached_tokens = usage.get("cachedContentTokenCount", 0)

    if cached_tokens > 0:
        logger.info(
            f"[Prompt Cache HIT] {cached_tokens}/{prompt_tokens} tokens served from cache for {model} (output: {candidates_tokens})"
        )
    else:
        logger.info(
            f"[Prompt Cache MISS] 0/{prompt_tokens} cached (full inference run) for {model} (output: {candidates_tokens})"
        )


class GeminiProvider(BaseLLMProvider):
    """Native raw HTTP provider for Google Gemini API."""

    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None):
        self.model = model or settings.AI_MODEL or "gemini-2.5-flash-lite"
        self.api_key = api_key or settings.AI_API_KEY
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"

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
        timeout: float = 30.0,
        max_tokens: int = 2000
    ) -> str:
        client = get_http_client()
        url = f"{self.base_url}/models/{self.model}:generateContent"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key or ""
        }
        sanitized_user = sanitize_prompt_input(user_prompt)

        payload = {
            "systemInstruction": {
                "parts": [{"text": system_prompt}]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": sanitized_user}]
                }
            ],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
                "responseMimeType": "application/json",
                "responseSchema": schema.model_json_schema()
            }
        }

        logger.info(f"Calling native Gemini model {self.model}...")
        response = await client.post(url, headers=headers, json=payload, timeout=timeout)
        response.raise_for_status()
        data = response.json()

        _log_gemini_token_usage(data, self.model)

        candidates = data.get("candidates", [])
        if not candidates:
            # Check for prompt-level feedback block
            block_reason = data.get("promptFeedback", {}).get("blockReason")
            if block_reason:
                raise ValueError(f"Gemini prompt blocked: {block_reason}")
            raise ValueError("No candidate returned by Gemini API")

        candidate = candidates[0]
        finish_reason = candidate.get("finishReason")
        if finish_reason == "MAX_TOKENS":
            raise PayloadTruncatedError("Gemini output exceeded maxOutputTokens and was truncated.")
        elif finish_reason in ("SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT"):
            raise ValueError(f"Gemini candidate blocked by policy: {finish_reason}")

        parts = candidate.get("content", {}).get("parts", [])
        if not parts or "text" not in parts[0]:
            raise ValueError("Empty completion payload received from Gemini API")

        return parts[0]["text"].strip()

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
        url = f"{self.base_url}/models/{self.model}:generateContent"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key or ""
        }
        sanitized_user = sanitize_prompt_input(user_prompt)

        payload = {
            "systemInstruction": {
                "parts": [{"text": system_prompt}]
            },
            "contents": [
                {"role": "user", "parts": [{"text": sanitized_user}]}
            ],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": 600
            }
        }

        logger.info(f"Calling native Gemini model {self.model} for text...")
        response = await client.post(url, headers=headers, json=payload, timeout=timeout)
        response.raise_for_status()
        data = response.json()

        _log_gemini_token_usage(data, self.model)

        candidates = data.get("candidates", [])
        if not candidates:
            return ""
        parts = candidates[0].get("content", {}).get("parts", [])
        return parts[0].get("text", "").strip() if parts else ""
