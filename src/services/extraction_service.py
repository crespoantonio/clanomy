import time
import logging
import threading
import asyncio
import re
from datetime import datetime, timezone
from typing import Optional, Union
from pydantic import BaseModel, Field, field_validator, ValidationError
import ollama
from src.core.config import settings
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

class ExtractionError(Exception):
    """Custom exception raised when extraction fails."""
    pass

class ExtractionResult(BaseModel):
    amount: float = Field(..., gt=0, description="The exact amount of the transaction")
    category: str = Field(..., description="Mapped to one of: 'Food/Drink', 'Transport', 'Rent/Bills', 'Shopping', 'Leisure', 'Other'")
    concept: str = Field(..., description="The transaction description or concept")
    currency: str = Field(default="USD", description="ISO 3-letter currency code, e.g. 'USD', 'EUR', 'GBP'")
    transaction_date: Optional[str] = Field(default=None, description="ISO format date string (YYYY-MM-DD) in UTC if explicitly mentioned or relative to current date (e.g. 'yesterday', 'last Monday', 'last week', '3 days ago'). Null/None if no date mentioned or if the purchase happened today.")

    def to_datetime(self, reference_time: Optional[datetime] = None) -> datetime:
        """Parses the extracted transaction date to a UTC datetime. Falls back to reference_time or now if none."""
        ref = reference_time or datetime.now(timezone.utc)
        if not self.transaction_date:
            return ref
        try:
            parsed_date = datetime.strptime(self.transaction_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            # Combine parsed date with midday time to avoid timezone boundary issues
            return parsed_date.replace(hour=12, minute=0, second=0, microsecond=0)
        except ValueError:
            logger.warning(f"Could not parse transaction_date '{self.transaction_date}'. Falling back to reference time.")
            return ref

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        allowed = {"Food/Drink", "Transport", "Rent/Bills", "Shopping", "Leisure", "Other"}
        cleaned = v.strip()
        
        if cleaned.title() == "Food/Drink":
            return "Food/Drink"
            
        for cat in allowed:
            if cleaned.lower() == cat.lower():
                return cat
        return "Other"

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        mapping = {
            "dollar": "USD", "dollars": "USD", "usd": "USD", "$": "USD",
            "euro": "EUR", "euros": "EUR", "eur": "EUR", "€": "EUR",
            "pound": "GBP", "pounds": "GBP", "gbp": "GBP", "£": "GBP"
        }
        cleaned = v.strip().lower()
        if cleaned in mapping:
            return mapping[cleaned]
            
        if len(cleaned) == 3 and cleaned.isalpha():
            return cleaned.upper()
        return "USD"

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

    def _fallback_regex_extract(self, text: str) -> ExtractionResult:
        """Attempt to extract amount and concept via regex as a last resort."""
        # Look for numbers (e.g. 15.50 or $15)
        amount_match = re.search(r'\b\d+(?:\.\d{1,2})?\b', text)
        if not amount_match:
            raise ExtractionError("Fallback failed: No amount found in text.")
        
        amount = float(amount_match.group(0))
        
        currency = "USD"
        if "eur" in text.lower() or "€" in text:
            currency = "EUR"
        elif "gbp" in text.lower() or "£" in text:
            currency = "GBP"
            
        return ExtractionResult(
            amount=amount,
            category="Other",
            concept=text.strip(),
            currency=currency,
            transaction_date=None
        )
            
    @retry(
        stop=stop_after_attempt(settings.OLLAMA_MAX_RETRIES),
        wait=wait_exponential(multiplier=settings.OLLAMA_RETRY_BACKOFF_MIN, max=settings.OLLAMA_RETRY_BACKOFF_MAX),
        retry=retry_if_exception_type((ollama.ResponseError, ollama.RequestError, asyncio.TimeoutError, ConnectionError, OSError)),
        reraise=True
    )
    async def _call_ollama(self, system_prompt: str, text: str) -> str:
        logger.info(f"Calling Ollama model {self.model} for extraction...")
        response = await asyncio.wait_for(
            self.client.chat(
                model=self.model,
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': f"Extract transaction details from this text: '{text}'"}
                ],
                format=ExtractionResult.model_json_schema(),
            ),
            timeout=60.0
        )
        content = response.message.content
        if not content:
            raise ExtractionError("Received empty response from Ollama")
        return content

    async def extract(self, text: str, reference_time: Optional[datetime] = None) -> ExtractionResult:
        if not text or not text.strip():
            raise ValueError("Input text is empty or contains only whitespace")

        ref = reference_time or datetime.now(timezone.utc)
        current_date_str = ref.strftime("%Y-%m-%d %H:%M:%S UTC")

        system_prompt = f'''You are an expert financial data extraction parser.
Your job is to extract transaction details from unstructured natural language text and return them in structured JSON format.

RULES:
1. Extract the numeric 'amount' as a float.
2. Determine the 'category'. It MUST be one of the following exact strings: "Food/Drink", "Transport", "Rent/Bills", "Shopping", "Leisure", "Other". If the category is ambiguous or doesn't fit, use "Other".
3. Extract the 'concept' (a brief description of what was purchased or the merchant name).
4. Determine the 'currency' and return its standard ISO 3-letter code (e.g., "euros" -> "EUR", "dollars" -> "USD", "pounds" -> "GBP"). If no currency is mentioned, use "USD".
5. Extract 'transaction_date' as an ISO format YYYY-MM-DD string.
   - Current Date: {current_date_str}
   - If a relative date is specified like "yesterday", "last Monday", "3 days ago", compute the specific date based on Current Date.
   - If a vague relative date is specified like "last week" without specifying a day, default to 7 days prior to Current Date.
   - If no date or time is specified or if it explicitly occurred today, set 'transaction_date' to null.

Return ONLY the JSON matching the provided schema.'''

        start_time = time.time()
        
        try:
            content = await self._call_ollama(system_prompt, text)
            
            try:
                result = ExtractionResult.model_validate_json(content)
                return result
            except ValidationError as ve:
                logger.warning(f"Pydantic validation failed on Ollama output: {ve}. Attempting fallback regex parser.")
                return self._fallback_regex_extract(text)
                
        except (ollama.ResponseError, ollama.RequestError, asyncio.TimeoutError, ConnectionError, OSError) as e:
            logger.error(f"Ollama connection/API error after retries: {e}. Attempting fallback regex parser.")
            return self._fallback_regex_extract(text)
        except Exception as e:
            logger.error(f"Extraction error: {e}")
            if isinstance(e, ExtractionError):
                raise
            raise ExtractionError(f"Failed to parse extraction result: {e}")
        finally:
            duration = time.time() - start_time
            logger.info(f"[3s Audit] Ollama extraction (including retries) took {duration:.2f} seconds")
