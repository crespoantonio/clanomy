from typing import List, Optional, Literal
from uuid import UUID, uuid4
from datetime import datetime, timezone
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import BigInteger

class Family(SQLModel, table=True):
    """
    Represents a family unit (multi-tenancy scope).
    All data is isolated by family_id.
    """
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    notion_api_key: Optional[str] = Field(default=None)
    notion_database_id: Optional[str] = Field(default=None, index=True)
    notion_database_name: Optional[str] = Field(default=None)
    notion_connected_at: Optional[datetime] = Field(default=None)

    # Subscription Tracking (Epic 7)
    plan_type: str = Field(default="free")
    subscription_status: str = Field(default="active")
    monthly_tx_count: int = Field(default=0)
    daily_tx_count: int = Field(default=0, sa_column_kwargs={"server_default": "0"})
    last_reset_month: Optional[str] = Field(default=None)
    max_members: int = Field(default=5)
    trial_ends_at: Optional[datetime] = Field(default=None)
    current_period_end: Optional[datetime] = Field(default=None)
    telegram_payment_charge_id: Optional[str] = Field(default=None)
    customer_portal_url: Optional[str] = Field(default=None)
    notified_day_50: bool = Field(default=False)
    notified_day_60: bool = Field(default=False)

    # Household Currency Configuration
    default_currency: str = Field(default="USD", sa_column_kwargs={"server_default": "USD"}, max_length=3)
    timezone: str = Field(default="America/Argentina/Buenos_Aires", sa_column_kwargs={"server_default": "America/Argentina/Buenos_Aires"}, max_length=50)

    # Relationships
    users: List["User"] = Relationship(back_populates="family", sa_relationship_kwargs={"cascade": "all, delete-orphan"})
    transactions: List["Transaction"] = Relationship(back_populates="family", sa_relationship_kwargs={"cascade": "all, delete-orphan"})
    invites: List["FamilyInvite"] = Relationship(back_populates="family", sa_relationship_kwargs={"cascade": "all, delete-orphan"})
    scheduled_bills: List["ScheduledBill"] = Relationship(back_populates="family", sa_relationship_kwargs={"cascade": "all, delete-orphan"})

class User(SQLModel, table=True):
    """
    Represents a Telegram user associated with a family.
    """
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    telegram_id: int = Field(unique=True, index=True, sa_type=BigInteger) # Explicitly use BIGINT for Telegram IDs
    username: Optional[str] = Field(default=None)
    full_name: Optional[str] = Field(default=None)
    family_id: UUID = Field(foreign_key="family.id", index=True, ondelete="CASCADE")
    is_admin: bool = Field(default=False)
    has_used_trial: bool = Field(default=False)
    timezone: Optional[str] = Field(default=None, max_length=50)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relationships
    family: Family = Relationship(back_populates="users")
    transactions: List["Transaction"] = Relationship(back_populates="user", sa_relationship_kwargs={"cascade": "all, delete-orphan"})
    created_invites: List["FamilyInvite"] = Relationship(back_populates="creator", sa_relationship_kwargs={"cascade": "all, delete-orphan"})

class Transaction(SQLModel, table=True):
    """
    Represents a financial transaction.
    Sensitive fields (amount, concept) are stored as ciphertext.
    """
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    family_id: UUID = Field(foreign_key="family.id", index=True, ondelete="CASCADE")
    user_id: UUID = Field(foreign_key="user.id", index=True, ondelete="CASCADE")
    
    # These fields store base64-encoded ciphertext from EncryptionService
    amount: str 
    concept: str 
    
    type: str = Field(
        default="expense",
        sa_column_kwargs={"server_default": "expense"},
        index=True,
        max_length=7
    )
    category: str = Field(index=True)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)

    notion_page_id: Optional[str] = Field(default=None, nullable=True, index=True)
    notion_synced_at: Optional[datetime] = Field(default=None, nullable=True)

    # Relationships
    family: Family = Relationship(back_populates="transactions")
    user: User = Relationship(back_populates="transactions")

    def __init__(self, **data):
        if "tx_type" in data and "type" not in data:
            data["type"] = data.pop("tx_type")
        super().__init__(**data)

    @property
    def tx_type(self) -> str:
        return self.type

    @tx_type.setter
    def tx_type(self, value: str):
        self.type = value

class FamilyInvite(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    family_id: UUID = Field(foreign_key="family.id", index=True, ondelete="CASCADE")
    created_by_user_id: UUID = Field(foreign_key="user.id", index=True, ondelete="CASCADE")
    token: str = Field(unique=True, index=True)
    expires_at: datetime = Field(index=True)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    family: "Family" = Relationship(back_populates="invites")
    creator: "User" = Relationship(back_populates="created_invites")

class ScheduledBill(SQLModel, table=True):
    """
    Represents a scheduled or fixed upcoming bill/commitment.
    Stored with encrypted amount and concept (matching Zero-Knowledge privacy principles).
    """
    __tablename__ = "scheduled_bill"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    family_id: UUID = Field(foreign_key="family.id", index=True, ondelete="CASCADE")
    user_id: UUID = Field(foreign_key="user.id", index=True, ondelete="CASCADE")

    # These fields store base64-encoded ciphertext from EncryptionService
    amount: str
    concept: str

    category: str = Field(index=True)
    due_date: datetime = Field(index=True)
    status: str = Field(default="pending", index=True, max_length=15)  # pending, paid, cancelled

    paid_transaction_id: Optional[UUID] = Field(default=None, foreign_key="transaction.id", nullable=True, ondelete="SET NULL")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relationships
    family: Family = Relationship(back_populates="scheduled_bills")
    user: User = Relationship()
    transaction: Optional[Transaction] = Relationship()
