from typing import Optional
from src.core.config import settings
from src.core.llm.base import BaseLLMProvider
from src.core.llm.providers.ollama_provider import OllamaProvider
from src.core.llm.providers.openai_provider import OpenAICompatibleProvider


def get_llm_provider(provider_type: Optional[str] = None) -> BaseLLMProvider:
    """
    Factory function returning the configured LLM provider instance.
    If provider_type is not given, uses settings.effective_ai_provider.
    """
    selected = provider_type or settings.effective_ai_provider
    if selected:
        selected_clean = selected.lower().strip()
        if selected_clean in ("gemini", "google", "groq", "cloud_ai", "openai", "openai_compatible"):
            return OpenAICompatibleProvider()
        elif selected_clean == "ollama":
            return OllamaProvider()

    # Automatic fallback based on AI_API_KEY presence
    if settings.AI_API_KEY and settings.AI_API_KEY.strip():
        return OpenAICompatibleProvider()
    return OllamaProvider()

