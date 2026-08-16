import asyncio
import logging
import threading
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Tuple
from uuid import UUID

import ollama
from pydantic import BaseModel, field_validator
from sqlmodel import Session, select

from src.core.config import settings
from src.core.encryption import EncryptionService
from src.db.session import engine
from src.db.models import Transaction

logger = logging.getLogger(__name__)

class QueryProcessingError(Exception):
    pass

class ParsedQueryIntent(BaseModel):
    intent: str
    timeframe: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    category: Optional[str] = None
    concept_keyword: Optional[str] = None

    @field_validator('category')
    @classmethod
    def normalize_category(cls, v: Optional[str]) -> Optional[str]:
        if not v or not isinstance(v, str) or not v.strip():
            return None
        valid_categories = {
            "Food/Drink", "Transport", "Rent/Bills", 
            "Shopping", "Leisure", "Other"
        }
        cleaned = v.strip()
        lower_mapping = {cat.lower(): cat for cat in valid_categories}
        if cleaned.lower() in lower_mapping:
            return lower_mapping[cleaned.lower()]
        return "Other"

class DecryptedTransaction(BaseModel):
    id: UUID
    family_id: UUID
    user_id: UUID
    amount: float
    currency: str
    concept: str
    category: str
    timestamp: datetime

class QueryResult(BaseModel):
    intent: ParsedQueryIntent
    resolved_start_time: Optional[datetime] = None
    resolved_end_time: Optional[datetime] = None
    transactions: List[DecryptedTransaction] = []
    total_count: int = 0

def _parse_amount_string(decrypted_str: str) -> tuple[float, str]:
    parts = decrypted_str.strip().split()
    if not parts:
        return 0.0, "USD"
    try:
        amount = float(parts[0])
    except ValueError:
        amount = 0.0
    currency = parts[1].upper() if len(parts) > 1 else "USD"
    return amount, currency

class QueryService:
    _instance: Optional['QueryService'] = None
    _lock = threading.Lock()

    def __new__(cls) -> 'QueryService':
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(QueryService, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.client = ollama.AsyncClient(host=settings.OLLAMA_BASE_URL)
        self.model = settings.OLLAMA_MODEL
        self.encryption_service = EncryptionService()
        self._initialized = True

    def _resolve_date_range(self, timeframe: str, start_date_str: Optional[str], end_date_str: Optional[str], reference_time: Optional[datetime] = None) -> tuple[Optional[datetime], Optional[datetime]]:
        ref_time = reference_time or datetime.now(timezone.utc)
        
        if timeframe == "today":
            start_time = ref_time.replace(hour=0, minute=0, second=0, microsecond=0)
            end_time = ref_time.replace(hour=23, minute=59, second=59, microsecond=999999)
            return start_time, end_time
        elif timeframe == "yesterday":
            yesterday = ref_time - timedelta(days=1)
            start_time = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
            end_time = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
            return start_time, end_time
        elif timeframe == "this_week":
            start_time = (ref_time - timedelta(days=ref_time.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
            end_time = ref_time.replace(hour=23, minute=59, second=59, microsecond=999999) # up to current day end
            return start_time, end_time
        elif timeframe == "last_week":
            start_of_this_week = (ref_time - timedelta(days=ref_time.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
            start_time = start_of_this_week - timedelta(days=7)
            end_time = start_of_this_week - timedelta(microseconds=1)
            return start_time, end_time
        elif timeframe == "this_month":
            start_time = ref_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end_time = ref_time.replace(hour=23, minute=59, second=59, microsecond=999999)
            return start_time, end_time
        elif timeframe == "last_month":
            first_of_this_month = ref_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end_time = first_of_this_month - timedelta(microseconds=1)
            start_time = end_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            return start_time, end_time
        elif timeframe == "custom":
            start_time = None
            end_time = None
            if start_date_str and isinstance(start_date_str, str):
                try:
                    start_time = datetime.strptime(start_date_str.strip(), "%Y-%m-%d").replace(tzinfo=timezone.utc)
                except (ValueError, AttributeError):
                    pass
            if end_date_str and isinstance(end_date_str, str):
                try:
                    end_time = datetime.strptime(end_date_str.strip(), "%Y-%m-%d").replace(tzinfo=timezone.utc, hour=23, minute=59, second=59, microsecond=999999)
                except (ValueError, AttributeError):
                    pass
            return start_time, end_time
        
        return None, None

    def _decrypt_transaction(self, tx: Transaction) -> Optional[DecryptedTransaction]:
        amount_str = self.encryption_service.decrypt(tx.amount)
        if not amount_str:
            return None
        concept_str = self.encryption_service.decrypt(tx.concept)
        if not concept_str:
            return None
        
        amount, currency = _parse_amount_string(amount_str)
        return DecryptedTransaction(
            id=tx.id,
            family_id=tx.family_id,
            user_id=tx.user_id,
            amount=amount,
            currency=currency,
            concept=concept_str,
            category=tx.category,
            timestamp=tx.timestamp
        )

    def _fetch_and_decrypt_transactions(self, family_id: UUID, start_time: Optional[datetime], end_time: Optional[datetime], category: Optional[str], concept_keyword: Optional[str]) -> List[DecryptedTransaction]:
        with Session(engine) as session:
            query = select(Transaction).where(Transaction.family_id == family_id)
            if start_time:
                query = query.where(Transaction.timestamp >= start_time)
            if end_time:
                query = query.where(Transaction.timestamp <= end_time)
            if category:
                query = query.where(Transaction.category == category)
            
            query = query.order_by(Transaction.timestamp.desc())
            db_transactions = session.exec(query).all()
            
            results = []
            for tx in db_transactions:
                decrypted = self._decrypt_transaction(tx)
                if not decrypted:
                    continue
                if concept_keyword:
                    if concept_keyword.lower() not in decrypted.concept.lower():
                        continue
                results.append(decrypted)
            return results

    async def process_query(self, text: str, family_id: UUID, reference_time: Optional[datetime] = None) -> QueryResult:
        if not text or not text.strip():
            raise ValueError("Query string cannot be empty")
        
        ref_time = reference_time or datetime.now(timezone.utc)
        current_date_str = ref_time.strftime("%Y-%m-%d %H:%M:%S UTC")
        
        start_exec_time = time.time()
        
        system_prompt = f"""You are a financial query parser. Your task is to extract intent, timeframe, and filters from the user's plain English query.
Current Date: {current_date_str}

Allowed categories: "Food/Drink", "Transport", "Rent/Bills", "Shopping", "Leisure", "Other".
Standard timeframes: "today", "yesterday", "this_week", "last_week", "this_month", "last_month", "custom", "all_time".
Extract `concept_keyword` if the user asks about a specific place or item (e.g., "Starbucks", "Uber")."""

        try:
            response = await asyncio.wait_for(
                self.client.chat(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": text}
                    ],
                    format=ParsedQueryIntent.model_json_schema(),
                ),
                timeout=60.0
            )
            intent_json = response.message.content
            intent = ParsedQueryIntent.model_validate_json(intent_json)
        except asyncio.TimeoutError as e:
            logger.error(f"Ollama query request timed out: {e}")
            raise QueryProcessingError(f"Ollama request timed out after 60.0 seconds: {e}")
        except Exception as e:
            logger.error(f"Error processing query with Ollama: {e}")
            raise QueryProcessingError(f"Failed to process query with Ollama: {e}")

        start_time, end_time = self._resolve_date_range(intent.timeframe, intent.start_date, intent.end_date, ref_time)
        
        try:
            transactions = await asyncio.to_thread(
                self._fetch_and_decrypt_transactions,
                family_id, start_time, end_time, intent.category, intent.concept_keyword
            )
        except Exception as e:
            logger.error(f"Database query error in process_query: {e}")
            raise QueryProcessingError(f"Database query failed: {e}")

        elapsed = time.time() - start_exec_time
        logger.info(f"[3s Audit] Query processing took {elapsed:.2f} seconds (model: {self.model}, family_id: {family_id})")

        return QueryResult(
            intent=intent,
            resolved_start_time=start_time,
            resolved_end_time=end_time,
            transactions=transactions,
            total_count=len(transactions)
        )
