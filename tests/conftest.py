import pytest
from src.core.config import settings

@pytest.fixture(autouse=True)
def test_environment_isolation():
    """Default ENABLE_SUBSCRIPTIONS=True and AI_API_KEY=None for unit test isolation, while allowing overrides."""
    original_subs = settings.ENABLE_SUBSCRIPTIONS
    original_ai_key = settings.AI_API_KEY
    settings.ENABLE_SUBSCRIPTIONS = True
    settings.AI_API_KEY = None
    yield
    settings.ENABLE_SUBSCRIPTIONS = original_subs
    settings.AI_API_KEY = original_ai_key
