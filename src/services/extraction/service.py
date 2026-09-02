import time
import logging
import threading
import asyncio
from datetime import datetime, timezone
from typing import Optional
from pydantic import ValidationError

from src.core.config import settings
from src.core.llm.base import BaseLLMProvider
from src.core.llm.factory import get_llm_provider
from src.services.extraction.models import ExtractionResult, UnifiedResult, ExtractionError
from src.services.extraction.prompts import (
    UNIFIED_SYSTEM_PROMPT,
    EXTRACTION_SYSTEM_PROMPT,
    build_extraction_prompt,
    build_unified_prompt,
)
from src.services.extraction.fallback import fallback_regex_extract, fallback_regex_classify

logger = logging.getLogger(__name__)


class ExtractionService:
    _instance: Optional['ExtractionService'] = None
    _lock = threading.Lock()

    def __new__(cls, provider: Optional[BaseLLMProvider] = None) -> 'ExtractionService':
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(ExtractionService, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, provider: Optional[BaseLLMProvider] = None):
        if not self._initialized:
            self.provider = provider or get_llm_provider()
            self._initialized = True
        elif provider is not None:
            self.provider = provider

    def _fallback_regex_extract(self, text: str, default_currency: Optional[str] = None) -> ExtractionResult:
        return fallback_regex_extract(text, default_currency=default_currency)

    def _fallback_regex_classify(self, text: str, default_currency: Optional[str] = None) -> UnifiedResult:
        return fallback_regex_classify(text, default_currency=default_currency)

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
        current_date_str = ref.strftime("%Y-%m-%d")
        effective_default_currency = (default_currency or settings.DEFAULT_CURRENCY or "USD").upper()

        system_prompt = UNIFIED_SYSTEM_PROMPT
        user_prompt = (
            "<system_context>\n"
            f"Default Workspace Currency: {effective_default_currency}\n"
            f"Current Reference Date: {current_date_str}\n"
            "</system_context>\n\n"
            "Classify intent and extract details from this text:\n"
            f"<user_input>\n{text}\n</user_input>"
        )

        start_time = time.time()
        try:
            content = await self.provider.complete_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                schema=UnifiedResult,
                timeout=60.0,
                max_tokens=2000
            )

            try:
                result = UnifiedResult.model_validate_json(content)
                return result
            except ValidationError as ve:
                logger.warning(f"Pydantic validation failed on UnifiedResult output: {ve}. Attempting fallback regex parser.")
                return self._fallback_regex_classify(text, default_currency=effective_default_currency)
        except Exception as e:
            logger.error(f"AI provider error in classify_and_extract: {e}. Attempting fallback regex parser.")
            if isinstance(e, ExtractionError):
                raise
            try:
                return self._fallback_regex_classify(text, default_currency=effective_default_currency)
            except Exception as fb_err:
                raise ExtractionError(f"Failed to parse classification and extraction result: {e}") from fb_err
        finally:
            duration = time.time() - start_time
            logger.info(f"[3s Audit] Unified classification and extraction took {duration:.2f} seconds")

    async def extract(
        self,
        text: str,
        reference_time: Optional[datetime] = None,
        default_currency: Optional[str] = None
    ) -> ExtractionResult:
        """
        Extracts structured transaction details from text.
        """
        if not text or not text.strip():
            raise ValueError("Input text is empty or contains only whitespace")

        ref = reference_time or datetime.now(timezone.utc)
        current_date_str = ref.strftime("%Y-%m-%d")
        effective_default_currency = (default_currency or settings.DEFAULT_CURRENCY or "USD").upper()

        system_prompt = EXTRACTION_SYSTEM_PROMPT
        user_prompt = (
            "<system_context>\n"
            f"Default Workspace Currency: {effective_default_currency}\n"
            f"Current Reference Date: {current_date_str}\n"
            "</system_context>\n\n"
            "Extract transaction details from this text:\n"
            f"<user_input>\n{text}\n</user_input>"
        )

        start_time = time.time()
        try:
            content = await self.provider.complete_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                schema=ExtractionResult,
                timeout=60.0,
                max_tokens=2000
            )
            try:
                result = ExtractionResult.model_validate_json(content)
                return result
            except ValidationError as ve:
                logger.warning(f"Pydantic validation failed on LLM output: {ve}. Attempting fallback regex parser.")
                return self._fallback_regex_extract(text, default_currency=effective_default_currency)
        except Exception as e:
            logger.error(f"Extraction error: {e}. Attempting fallback regex parser.")
            if isinstance(e, ExtractionError):
                raise
            try:
                return self._fallback_regex_extract(text, default_currency=effective_default_currency)
            except Exception as fb_err:
                raise ExtractionError(f"Failed to parse extraction result: {e}") from fb_err
        finally:
            duration = time.time() - start_time
            logger.info(f"[3s Audit] Extraction (including retries) took {duration:.2f} seconds")
