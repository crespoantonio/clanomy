import pytest
from unittest.mock import MagicMock, AsyncMock
from src.core.llm.base import BaseLLMProvider
from src.services.extraction.service import ExtractionService
from src.services.query.service import QueryService


class DummyProvider(BaseLLMProvider):
    async def complete_structured(self, system_prompt: str, user_prompt: str, schema, **kwargs):
        return "{}"

    async def complete_text(self, system_prompt: str, user_prompt: str, **kwargs):
        return "text"


def test_extraction_service_instance_isolation():
    """Verify ExtractionService is no longer a singleton and does not bleed state."""
    custom_provider = DummyProvider()
    svc_custom = ExtractionService(provider=custom_provider)
    svc_default = ExtractionService()

    assert svc_custom.provider is custom_provider
    assert svc_default.provider is not custom_provider
    assert svc_custom is not svc_default


def test_query_service_instance_isolation():
    """Verify QueryService is no longer a singleton and does not bleed state."""
    custom_provider = DummyProvider()
    qs_custom = QueryService(provider=custom_provider)
    qs_default = QueryService()

    assert qs_custom.provider is custom_provider
    assert qs_default.provider is not custom_provider
    assert qs_custom is not qs_default
