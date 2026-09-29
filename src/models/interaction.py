"""
Interaction models for Clanomy.
Defines channel-agnostic response representations for messaging adapters (Telegram, WhatsApp, Web, etc.).
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class InteractionAction(BaseModel):
    label: str
    callback_data: str
    url: Optional[str] = None


class InteractionResult(BaseModel):
    """
    Channel-agnostic result of user interaction processing.
    Encapsulates text messages, structured documents/files, actionable buttons, and metadata.
    """
    text: Optional[str] = None
    document_path: Optional[str] = None
    document_caption: Optional[str] = None
    actions: List[InteractionAction] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    should_notify: bool = True
