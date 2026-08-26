import pytest
from src.core.config import settings

@pytest.fixture(autouse=True)
def enable_subscriptions_for_tests():
    """Default ENABLE_SUBSCRIPTIONS=True for existing SaaS/commercial test suite, while allowing overrides."""
    original_val = settings.ENABLE_SUBSCRIPTIONS
    settings.ENABLE_SUBSCRIPTIONS = True
    yield
    settings.ENABLE_SUBSCRIPTIONS = original_val
