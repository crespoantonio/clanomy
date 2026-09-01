import os

# Set required test environment variables before Settings() is instantiated
os.environ.setdefault("ENCRYPTION_KEY", "MDEyMzQ1Njc4OTAxMjM0NTY3ODkwMTIzNDU2Nzg5MDE=")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "ci_test_telegram_bot_token")
os.environ.setdefault("MESSAGING_WEBHOOK_SECRET", "ci_test_secret")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

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
