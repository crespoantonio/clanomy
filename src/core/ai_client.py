import asyncio
import re
from typing import Optional
from src.core.config import settings

# Global shared semaphore for Ollama local inference to prevent GPU memory thrashing
_global_ollama_semaphore: Optional[asyncio.Semaphore] = None

def get_global_ollama_semaphore() -> asyncio.Semaphore:
    """Returns the shared asyncio Semaphore for Ollama requests across all AI services."""
    global _global_ollama_semaphore
    if _global_ollama_semaphore is None:
        _global_ollama_semaphore = asyncio.Semaphore(settings.OLLAMA_MAX_CONCURRENT)
    return _global_ollama_semaphore

def sanitize_prompt_input(text: str) -> str:
    """
    Sanitizes untrusted user input before passing into LLM prompt templates.
    Neutralizes markdown code fences and removes boundary tags to prevent prompt injection breakouts.
    """
    if not text:
        return ""
    # Replace triple backticks to prevent markdown fence breakout
    sanitized = text.replace("```", "'''")
    # Neutralize user_input and system_context XML boundary delimiters (case-insensitive)
    tags_to_strip = ["<user_input>", "</user_input>", "<system_context>", "</system_context>"]
    for tag in tags_to_strip:
        sanitized = re.sub(re.escape(tag), "", sanitized, flags=re.IGNORECASE)
    return sanitized.strip()

