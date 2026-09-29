import logging
from datetime import datetime, timezone
from typing import Optional, Literal, List
from pydantic import BaseModel, Field, field_validator, model_validator
from src.core.config import settings
from src.services.extraction.normalizers import normalize_category_value, normalize_currency_value

logger = logging.getLogger(__name__)

from src.core.llm.base import PayloadTruncatedError

class ExtractionError(Exception):
    """Custom exception raised when extraction fails."""
    pass



class ParsedItem(BaseModel):
    type: Literal["expense", "income"] = Field(
        default="expense",
        description="The transaction intent / type: 'expense' or 'income'. Defaults to 'expense'."
    )
    amount: float = Field(..., gt=0, description="The exact positive amount of the transaction or bill.")
    category: str = Field(default="Other", description="Mapped to one of standard categories.")
    concept: str = Field(..., description="The transaction description, concept, merchant name, or bill name.")
    currency: str = Field(default="USD", description="ISO 3-letter currency code, e.g. 'USD', 'ARS', 'EUR', 'MXN', 'GBP'.")
    transaction_date: Optional[str] = Field(default=None, description="ISO format date string (YYYY-MM-DD) if relative or past date specified. Null if today.")
    due_date: Optional[str] = Field(default=None, description="ISO format date string (YYYY-MM-DD) if future/scheduled bill. Null if immediate.")
    is_scheduled_bill: bool = Field(default=False, description="True if marked with future due date / 'con vencimiento' / 'due on'.")

    def to_datetime(self, reference_time: Optional[datetime] = None) -> datetime:
        ref = reference_time or datetime.now(timezone.utc)
        target_str = self.due_date if self.is_scheduled_bill and self.due_date else self.transaction_date
        if not target_str:
            return ref
        try:
            parsed_date = datetime.strptime(target_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            return parsed_date.replace(hour=12, minute=0, second=0, microsecond=0)
        except ValueError:
            logger.warning(f"Could not parse date '{target_str}'. Falling back to reference time.")
            return ref

    @field_validator("type", mode="before")
    @classmethod
    def validate_type(cls, v: Optional[str]) -> str:
        if isinstance(v, str) and v.strip().lower() == "income":
            return "income"
        return "expense"

    @field_validator("category", mode="before")
    @classmethod
    def validate_category(cls, v: Optional[str]) -> str:
        if v is None:
            return "Other"
        return normalize_category_value(v) or "Other"

    @field_validator("currency", mode="before")
    @classmethod
    def validate_currency(cls, v: Optional[str]) -> str:
        if v is None:
            return (settings.DEFAULT_CURRENCY or "USD").upper()
        return normalize_currency_value(v) or (settings.DEFAULT_CURRENCY or "USD").upper()

class ExtractionResult(BaseModel):
    type: Literal["expense", "income"] = Field(
        default="expense",
        description="The transaction intent / type: 'expense' or 'income'. Defaults to 'expense'."
    )
    amount: float = Field(..., gt=0, description="The exact positive amount of the transaction")
    category: str = Field(..., description="Mapped to one of standard categories")
    concept: str = Field(..., description="The transaction description, concept, merchant name, or earnings source")
    currency: str = Field(default="USD", description="ISO 3-letter currency code, e.g. 'USD', 'EUR', 'GBP'")
    transaction_date: Optional[str] = Field(default=None, description="ISO format date string (YYYY-MM-DD) in UTC if explicitly mentioned or relative to current date. Null if today.")

    def to_datetime(self, reference_time: Optional[datetime] = None) -> datetime:
        """Parses the extracted transaction date to a UTC datetime. Falls back to reference_time or now if none."""
        ref = reference_time or datetime.now(timezone.utc)
        if not self.transaction_date:
            return ref
        try:
            parsed_date = datetime.strptime(self.transaction_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
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
        return normalize_category_value(v) or "Other"

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        return normalize_currency_value(v) or (settings.DEFAULT_CURRENCY or "USD").upper()

class UnifiedResult(BaseModel):
    action: Literal["log_transaction", "edit_last", "undo_last", "query"] = Field(
        default="log_transaction",
        description="The action intent: 'log_transaction', 'edit_last', 'undo_last', or 'query'."
    )
    # Transaction fields (populated when action == 'log_transaction')
    type: Optional[Literal["expense", "income"]] = Field(
        default="expense",
        description="The transaction intent / type: 'expense' or 'income'."
    )
    amount: Optional[float] = Field(
        default=None,
        gt=0,
        description="The exact positive amount of the transaction."
    )
    category: Optional[str] = Field(
        default=None,
        description="Mapped category: 'Food/Drink', 'Transport', 'Rent/Bills', 'Shopping', 'Leisure', 'Salary', 'Bonus', 'Freelance', 'Investment', 'Gift', 'Sale', 'Other'."
    )
    concept: Optional[str] = Field(
        default=None,
        description="The description, merchant name, or item."
    )
    currency: Optional[str] = Field(
        default="USD",
        description="ISO 3-letter currency code, e.g. 'USD', 'ARS', 'EUR', 'MXN', 'GBP'."
    )
    transaction_date: Optional[str] = Field(
        default=None,
        description="ISO format date string (YYYY-MM-DD) if relative or past date specified. Null if today."
    )
    due_date: Optional[str] = Field(
        default=None,
        description="ISO format date string (YYYY-MM-DD) if future/scheduled bill. Null if immediate."
    )
    is_scheduled_bill: bool = Field(
        default=False,
        description="True if marked with future due date / 'con vencimiento' / 'due on'."
    )
    items: List[ParsedItem] = Field(
        default_factory=list,
        description="List of one or more transaction items or scheduled bills extracted from the message."
    )

    # Edit fields (populated when action == 'edit_last')
    new_amount: Optional[float] = Field(
        default=None,
        gt=0,
        description="The corrected positive amount if amount was updated."
    )
    new_category: Optional[str] = Field(
        default=None,
        description="The corrected category if category was updated."
    )
    new_concept: Optional[str] = Field(
        default=None,
        description="The corrected description/merchant if concept was updated."
    )
    new_currency: Optional[str] = Field(
        default=None,
        description="The corrected 3-letter currency code if currency was updated."
    )
    new_type: Optional[Literal["expense", "income"]] = Field(
        default=None,
        description="The corrected type ('expense' or 'income') if type was updated."
    )

    # Targeting fields for specific transaction edits or undos
    target_amount: Optional[float] = Field(
        default=None,
        description="The specific amount of the transaction to update or delete, if specified by the user."
    )
    target_currency: Optional[str] = Field(
        default=None,
        description="The specific currency of the transaction to update or delete, if specified by the user."
    )
    target_concept: Optional[str] = Field(
        default=None,
        description="The specific concept or keyword of the transaction to update or delete, if specified by the user."
    )

    # Currency exchange (FX) flags
    is_exchange: bool = Field(
        default=False,
        description="True if this operation represents a dual-leg currency exchange."
    )
    exchange_rate: Optional[float] = Field(
        default=None,
        description="The implied or explicit exchange rate between the two currencies."
    )

    def to_datetime(self, reference_time: Optional[datetime] = None) -> datetime:
        """Parses the transaction date to a UTC datetime. Falls back to reference_time or now if none."""
        ref = reference_time or datetime.now(timezone.utc)
        if not self.transaction_date:
            return ref
        try:
            parsed_date = datetime.strptime(self.transaction_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            return parsed_date.replace(hour=12, minute=0, second=0, microsecond=0)
        except ValueError:
            logger.warning(f"Could not parse transaction_date '{self.transaction_date}'. Falling back to reference time.")
            return ref

    @field_validator("type", "new_type", mode="before")
    @classmethod
    def validate_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if isinstance(v, str) and v.strip().lower() == "income":
            return "income"
        return "expense"

    @field_validator("category", "new_category", mode="before")
    @classmethod
    def validate_category(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return normalize_category_value(v) or "Other"

    @field_validator("currency", "new_currency", "target_currency", mode="before")
    @classmethod
    def validate_currency(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return normalize_currency_value(v) or (settings.DEFAULT_CURRENCY or "USD").upper()

    @model_validator(mode="after")
    def synchronize_items_and_scalars(self) -> 'UnifiedResult':
        if self.action == "log_transaction":
            if self.items and self.amount is None:
                first = self.items[0]
                self.amount = first.amount
                self.category = first.category
                self.concept = first.concept
                self.currency = first.currency
                self.type = first.type
                self.transaction_date = first.transaction_date
                self.due_date = first.due_date
                self.is_scheduled_bill = first.is_scheduled_bill
            elif not self.items and self.amount is not None:
                self.items = [
                    ParsedItem(
                        type=self.type or "expense",
                        amount=self.amount,
                        category=self.category or "Other",
                        concept=self.concept or "",
                        currency=self.currency or (settings.DEFAULT_CURRENCY or "USD").upper(),
                        transaction_date=self.transaction_date,
                        due_date=self.due_date,
                        is_scheduled_bill=self.is_scheduled_bill
                    )
                ]
        return self

    def get_all_items(self) -> List[ParsedItem]:
        if self.items:
            return self.items
        if self.amount is not None:
            return [
                ParsedItem(
                    type=self.type or "expense",
                    amount=self.amount,
                    category=self.category or "Other",
                    concept=self.concept or "",
                    currency=self.currency or (settings.DEFAULT_CURRENCY or "USD").upper(),
                    transaction_date=self.transaction_date,
                    due_date=self.due_date,
                    is_scheduled_bill=self.is_scheduled_bill
                )
            ]
        return []
