import time
import logging
import threading
import asyncio
from datetime import datetime, timezone
from typing import Optional
from pydantic import ValidationError
import ollama
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.core.config import settings
from src.services.extraction.models import ExtractionResult, UnifiedResult, ExtractionError
from src.services.extraction.prompts import build_extraction_prompt, build_unified_prompt
from src.services.extraction.fallback import fallback_regex_extract, fallback_regex_classify

logger = logging.getLogger(__name__)

_ollama_semaphore = asyncio.Semaphore(3)

class ExtractionService:
    _instance: Optional['ExtractionService'] = None
    _lock = threading.Lock()

    def __new__(cls) -> 'ExtractionService':
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(ExtractionService, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.client = ollama.AsyncClient(host=settings.OLLAMA_BASE_URL)
            self.model = settings.OLLAMA_MODEL
            self._initialized = True

    def _fallback_regex_extract(self, text: str, default_currency: Optional[str] = None) -> ExtractionResult:
        return fallback_regex_extract(text, default_currency=default_currency)

    def _fallback_regex_classify(self, text: str, default_currency: Optional[str] = None) -> UnifiedResult:
        return fallback_regex_classify(text, default_currency=default_currency)

    @retry(
        stop=stop_after_attempt(settings.AI_MAX_RETRIES),
        wait=wait_exponential(multiplier=settings.AI_RETRY_BACKOFF_MIN, max=settings.AI_RETRY_BACKOFF_MAX),
        retry=retry_if_exception_type((httpx.HTTPError, asyncio.TimeoutError, ConnectionError, OSError)),
        reraise=True
    )
    async def _call_cloud_ai_unified(self, system_prompt: str, text: str) -> str:
        logger.info(f"Calling Cloud AI model {settings.AI_MODEL} at {settings.AI_BASE_URL} for unified classification & extraction...")
        from src.core.http_client import get_http_client
        client = get_http_client()
        headers = {
            "Authorization": f"Bearer {settings.AI_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": settings.AI_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Classify intent and extract details from this text:\n```\n{text}\n```"}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.0
        }
        response = await client.post(
            f"{settings.AI_BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
            timeout=30.0
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        if not content:
            raise ExtractionError("Received empty response from Cloud AI")
        return content

    @retry(
        stop=stop_after_attempt(settings.AI_MAX_RETRIES),
        wait=wait_exponential(multiplier=settings.AI_RETRY_BACKOFF_MIN, max=settings.AI_RETRY_BACKOFF_MAX),
        retry=retry_if_exception_type((ollama.ResponseError, ollama.RequestError, asyncio.TimeoutError, ConnectionError, OSError)),
        reraise=True
    )
    async def _call_ollama_unified(self, system_prompt: str, text: str) -> str:
        logger.info(f"Calling Ollama model {self.model} for unified classification & extraction...")
        async with _ollama_semaphore:
            response = await asyncio.wait_for(
                self.client.chat(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Classify intent and extract details from this text:\n```\n{text}\n```"}
                    ],
                    format=UnifiedResult.model_json_schema(),
                ),
                timeout=60.0
            )
            content = response.message.content
            if not content:
                raise ExtractionError("Received empty response from Ollama")
            return content

    async def classify_and_extract(
        self,
        text: str,
        reference_time: Optional[datetime] = None,
        default_currency: Optional[str] = None
    ) -> UnifiedResult:
        """
        Unified single-call method: Classifies user intent (log_transaction, edit_last, undo_last, query)
        and extracts relevant transaction or correction fields.
        """
        if not text or not text.strip():
            raise ValueError("Input text is empty or contains only whitespace")

        ref = reference_time or datetime.now(timezone.utc)
        current_date_str = ref.strftime("%Y-%m-%d %H:%M:%S UTC")
        effective_default_currency = (default_currency or settings.DEFAULT_CURRENCY or "USD").upper()

        system_prompt = build_unified_prompt(effective_default_currency, current_date_str)

        start_time = time.time()
        try:
            if settings.AI_API_KEY and settings.AI_API_KEY.strip():
                content = await self._call_cloud_ai_unified(system_prompt, text)
            else:
                content = await self._call_ollama_unified(system_prompt, text)

            try:
                result = UnifiedResult.model_validate_json(content)
                return result
            except ValidationError as ve:
                logger.warning(f"Pydantic validation failed on UnifiedResult output: {ve}. Attempting fallback regex parser.")
                return self._fallback_regex_classify(text, default_currency=effective_default_currency)
        except (ollama.ResponseError, ollama.RequestError, httpx.HTTPError, asyncio.TimeoutError, ConnectionError, OSError) as e:
            logger.error(f"AI engine error in classify_and_extract: {e}. Attempting fallback regex parser.")
            return self._fallback_regex_classify(text, default_currency=effective_default_currency)
        except Exception as e:
            logger.error(f"classify_and_extract unexpected error: {e}")
            if isinstance(e, ExtractionError):
                raise
            raise ExtractionError(f"Failed to parse classification and extraction result: {e}")
        finally:
            duration = time.time() - start_time
            logger.info(f"[3s Audit] Unified classification and extraction took {duration:.2f} seconds")

    @retry(
        stop=stop_after_attempt(settings.AI_MAX_RETRIES),
        wait=wait_exponential(multiplier=settings.AI_RETRY_BACKOFF_MIN, max=settings.AI_RETRY_BACKOFF_MAX),
        retry=retry_if_exception_type((httpx.HTTPError, asyncio.TimeoutError, ConnectionError, OSError)),
        reraise=True
    )
    async def _call_cloud_ai(self, system_prompt: str, text: str) -> str:
        logger.info(f"Calling Cloud AI model {settings.AI_MODEL} at {settings.AI_BASE_URL} for extraction...")
        from src.core.http_client import get_http_client
        client = get_http_client()
        headers = {
            "Authorization": f"Bearer {settings.AI_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": settings.AI_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Extract transaction details from this text:\n```\n{text}\n```"}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.0
        }
        response = await client.post(
            f"{settings.AI_BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
            timeout=30.0
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        if not content:
            raise ExtractionError("Received empty response from Cloud AI")
        return content

    @retry(
        stop=stop_after_attempt(settings.AI_MAX_RETRIES),
        wait=wait_exponential(multiplier=settings.AI_RETRY_BACKOFF_MIN, max=settings.AI_RETRY_BACKOFF_MAX),
        retry=retry_if_exception_type((ollama.ResponseError, ollama.RequestError, asyncio.TimeoutError, ConnectionError, OSError)),
        reraise=True
    )
    async def _call_ollama(self, system_prompt: str, text: str) -> str:
        logger.info(f"Calling Ollama model {self.model} for extraction...")
        async with _ollama_semaphore:
            response = await asyncio.wait_for(
                self.client.chat(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Extract transaction details from this text:\n```\n{text}\n```"}
                    ],
                    format=ExtractionResult.model_json_schema(),
                ),
                timeout=60.0
            )
            content = response.message.content
            if not content:
                raise ExtractionError("Received empty response from Ollama")
            return content

    async def extract(self, text: str, reference_time: Optional[datetime] = None, default_currency: Optional[str] = None) -> ExtractionResult:
        if not text or not text.strip():
            raise ValueError("Input text is empty or contains only whitespace")

        ref = reference_time or datetime.now(timezone.utc)
        current_date_str = ref.strftime("%Y-%m-%d %H:%M:%S UTC")
        effective_default_currency = (default_currency or settings.DEFAULT_CURRENCY or "USD").upper()

        system_prompt = build_extraction_prompt(effective_default_currency, current_date_str)

        start_time = time.time()
        try:
            if settings.AI_API_KEY and settings.AI_API_KEY.strip():
                content = await self._call_cloud_ai(system_prompt, text)
            else:
                content = await self._call_ollama(system_prompt, text)
            try:
                result = ExtractionResult.model_validate_json(content)
                return result
            except ValidationError as ve:
                logger.warning(f"Pydantic validation failed on LLM output: {ve}. Attempting fallback regex parser.")
                return self._fallback_regex_extract(text, default_currency=effective_default_currency)
        except (ollama.ResponseError, ollama.RequestError, httpx.HTTPError, asyncio.TimeoutError, ConnectionError, OSError) as e:
            logger.error(f"AI engine connection/API error after retries: {e}. Attempting fallback regex parser.")
            return self._fallback_regex_extract(text, default_currency=effective_default_currency)
        except Exception as e:
            logger.error(f"Extraction error: {e}")
            if isinstance(e, ExtractionError):
                raise
            raise ExtractionError(f"Failed to parse extraction result: {e}")
        finally:
            duration = time.time() - start_time
            logger.info(f"[3s Audit] Ollama extraction (including retries) took {duration:.2f} seconds")
