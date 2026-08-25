import time
import logging
import threading
import asyncio
import re
from datetime import datetime, timezone
from typing import Optional, Union, Literal
from pydantic import BaseModel, Field, field_validator, ValidationError
import ollama
from src.core.config import settings
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

class ExtractionError(Exception):
    """Custom exception raised when extraction fails."""
    pass

class ExtractionResult(BaseModel):
    type: Literal["expense", "income"] = Field(
        default="expense",
        description="The transaction intent / type: 'expense' or 'income'. Defaults to 'expense'."
    )
    amount: float = Field(..., gt=0, description="The exact positive amount of the transaction")
    category: str = Field(..., description="Mapped to one of: 'Food/Drink', 'Transport', 'Rent/Bills', 'Shopping', 'Leisure', 'Salary', 'Bonus', 'Freelance', 'Investment', 'Gift', 'Sale', 'Other'")
    concept: str = Field(..., description="The transaction description, concept, merchant name, or earnings source")
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

    @field_validator("type", mode="before")
    @classmethod
    def validate_type(cls, v: Optional[str]) -> str:
        if isinstance(v, str) and v.strip().lower() == "income":
            return "income"
        return "expense"

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        category_map = {
            "food/drink": "Food/Drink",
            "transport": "Transport",
            "rent/bills": "Rent/Bills",
            "shopping": "Shopping",
            "leisure": "Leisure",
            "salary": "Salary",
            "wage": "Salary",
            "wages": "Salary",
            "bonus": "Bonus",
            "freelance": "Freelance",
            "freelance payment": "Freelance",
            "investment": "Investment",
            "dividend": "Investment",
            "dividends": "Investment",
            "gift": "Gift",
            "sale": "Sale",
            "sales": "Sale",
            "other": "Other",
        }
        cleaned = v.strip().lower()
        if cleaned in category_map:
            return category_map[cleaned]
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
        """Attempt to extract amount, type, category, and concept via regex and keyword heuristics as a last resort."""
        # Look for numbers (e.g. 15.50 or $15) with robust regex
        amount_match = re.search(r'\b(\d+(?:[.,]\d{1,2})?)\b', text.replace(',', ''))
        if not amount_match:
            # Maybe it starts with $ without word boundary
            amount_match = re.search(r'[$€£](\d+(?:[.,]\d{1,2})?)', text.replace(',', ''))
            if not amount_match:
                raise ExtractionError("Fallback failed: No amount found in text.")
        
        amount = float(amount_match.group(1).replace(',', ''))
        
        currency = "USD"
        text_lower = text.lower()
        if re.search(r'\beuro?s?\b|€', text_lower):
            currency = "EUR"
        elif re.search(r'\bgbp\b|\bpounds?\b|£', text_lower):
            currency = "GBP"
            
        # Classify intent (income vs expense)
        income_keywords = [
            "salary", "earned", "got paid", "sold", "bonus",
            "freelance payment", "freelance", "dividend", "dividends", "invoice paid", "received"
        ]
        expense_keywords = [
            "spent", "bought", "paid for", "coffee", "lunch", "rent"
        ]
        
        tx_type = "expense"
        category = "Other"
        
        has_income = any(re.search(rf'\b{re.escape(kw)}\b', text_lower) for kw in income_keywords)
        has_expense = any(re.search(rf'\b{re.escape(kw)}\b', text_lower) for kw in expense_keywords)
        
        if has_income and not has_expense:
            tx_type = "income"
            if any(re.search(rf'\b{re.escape(kw)}\b', text_lower) for kw in ["salary", "got paid", "wage", "wages"]):
                category = "Salary"
            elif re.search(r'\bbonus\b', text_lower):
                category = "Bonus"
            elif any(re.search(rf'\b{re.escape(kw)}\b', text_lower) for kw in ["sold", "sale", "sales"]):
                category = "Sale"
            elif any(re.search(rf'\b{re.escape(kw)}\b', text_lower) for kw in ["freelance", "freelance payment", "invoice paid", "consulting"]):
                category = "Freelance"
            elif any(re.search(rf'\b{re.escape(kw)}\b', text_lower) for kw in ["dividend", "dividends", "investment", "interest"]):
                category = "Investment"
            elif re.search(r'\bgift\b', text_lower):
                category = "Gift"
                
        return ExtractionResult(
            type=tx_type,
            amount=amount,
            category=category,
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
1. Determine the transaction 'type':
   - Must be either "expense" or "income".
   - Classify as "income" for earnings, wages, salaries, sales, bonuses, freelance payments, dividends, or received money (e.g. keywords: "salary", "earned", "got paid", "sold", "bonus", "freelance payment", "dividend", "invoice paid", "received").
   - Classify as "expense" for spending, purchases, payments, bills (e.g. keywords: "spent", "bought", "paid for", "coffee", "lunch", "rent").
   - Default safely to "expense" if intent is ambiguous.
2. Extract the numeric 'amount' as a positive float (> 0).
3. Determine the 'category':
   - For expenses, use one of: "Food/Drink", "Transport", "Rent/Bills", "Shopping", "Leisure", "Other".
   - For income, use one of: "Salary", "Bonus", "Freelance", "Investment", "Gift", "Sale", "Other".
   - If ambiguous or does not fit, use "Other".
4. Extract the 'concept' (a brief description of what was purchased or earned, client/merchant name, or item sold).
5. Determine the 'currency' and return its standard ISO 3-letter code (e.g., "euros" -> "EUR", "dollars" -> "USD", "pounds" -> "GBP"). If no currency is mentioned, use "USD".
6. Extract 'transaction_date' as an ISO format YYYY-MM-DD string:
   - Current Date: {current_date_str}
   - If a relative date is specified like "yesterday", "last Monday", "3 days ago", compute the specific date based on Current Date.
   - If a vague relative date is specified like "last week" without specifying a day, default to 7 days prior to Current Date.
   - If no date or time is specified or if it explicitly occurred today, set 'transaction_date' to null.

Return ONLY the JSON matching the provided schema. Do not include any markdown formatting like ```json, and do not include any commentary.'''

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
