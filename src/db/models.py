from typing import List, Optional
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

    # Relationships
    users: List["User"] = Relationship(back_populates="family", sa_relationship_kwargs={"cascade": "all, delete-orphan"})
    transactions: List["Transaction"] = Relationship(back_populates="family", sa_relationship_kwargs={"cascade": "all, delete-orphan"})
    invites: List["FamilyInvite"] = Relationship(back_populates="family", sa_relationship_kwargs={"cascade": "all, delete-orphan"})

class User(SQLModel, table=True):
    """
    Represents a Telegram user associated with a family.
    """
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    telegram_id: int = Field(unique=True, index=True, sa_type=BigInteger) # Explicitly use BIGINT for Telegram IDs
    username: Optional[str] = Field(default=None)
    full_name: Optional[str] = Field(default=None)
    family_id: UUID = Field(foreign_key="family.id", index=True, ondelete="CASCADE")
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
    
    category: str = Field(index=True)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)

    # Relationships
    family: Family = Relationship(back_populates="transactions")
    user: User = Relationship(back_populates="transactions")

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
