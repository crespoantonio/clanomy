from abc import ABC, abstractmethod
from typing import Type, Any, Optional
from pydantic import BaseModel

class LLMError(Exception):
    """Base exception for LLM provider errors."""
    pass


class PayloadTruncatedError(LLMError):
    """Raised when LLM output generation exceeds token budget and was truncated."""
    pass


class BaseLLMProvider(ABC):

    """Abstract base class for all LLM inference providers."""

    @abstractmethod
    async def complete_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: Type[BaseModel],
        temperature: float = 0.0,
        timeout: float = 60.0,
        max_tokens: int = 600
    ) -> str:

        """
        Executes a completion request and returns a raw JSON string matching the provided Pydantic schema.
        """
        pass

    @abstractmethod
    async def complete_text(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        timeout: float = 30.0
    ) -> str:
        """
        Executes a text completion request and returns the resulting string.
        """
        pass
