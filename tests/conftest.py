import os

# Set required test environment variables before Settings() is instantiated
os.environ.setdefault("ENCRYPTION_KEY", "MDEyMzQ1Njc4OTAxMjM0NTY3ODkwMTIzNDU2Nzg5MDE=")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "ci_test_telegram_bot_token")
os.environ.setdefault("MESSAGING_WEBHOOK_SECRET", "ci_test_secret")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("OLLAMA_BASE_URL", "http://127.0.0.1:9")

import pytest
from src.core.config import settings

def pytest_configure(config):
    config.addinivalue_line(
        "markers", "ollama: marks tests that require a live Ollama instance (skipped in CI)"
    )
    config.addinivalue_line(
        "markers", "live_ai: marks tests that interact with live external AI services (skipped in CI)"
    )

def pytest_collection_modifyitems(config, items):
    """
    Ensure tests requiring a live Ollama instance or live external AI are never run in CI
    or when live AI is not explicitly requested via RUN_LIVE_AI=true.
    """
    is_ci = os.environ.get("CI") == "true" or os.environ.get("GITHUB_ACTIONS") == "true"
    run_live_ai = os.environ.get("RUN_LIVE_AI") == "true"

    skip_ollama_ci = pytest.mark.skip(reason="Ollama is not available in GitHub Actions / CI pipeline")
    skip_live_ai = pytest.mark.skip(reason="Live AI tests are skipped during CI pipeline runs")

    for item in items:
        if item.get_closest_marker("ollama"):
            if is_ci or not run_live_ai:
                item.add_marker(skip_ollama_ci)
        elif item.get_closest_marker("live_ai"):
            if is_ci or not run_live_ai:
                item.add_marker(skip_live_ai)

@pytest.fixture(autouse=True)
def test_environment_isolation():
    """Default ENABLE_SUBSCRIPTIONS=True, AI_API_KEY=None, and isolated OLLAMA_BASE_URL for unit test isolation, while allowing overrides."""
    original_subs = settings.ENABLE_SUBSCRIPTIONS
    original_ai_key = settings.AI_API_KEY
    original_ollama_url = settings.OLLAMA_BASE_URL
    settings.ENABLE_SUBSCRIPTIONS = True
    settings.AI_API_KEY = None
    settings.OLLAMA_BASE_URL = "http://127.0.0.1:9"
    from src.services.query.service import QueryService
    from src.services.family_service import FamilyService
    from src.services.extraction.service import ExtractionService
    QueryService._instance = None
    FamilyService._instance = None
    ExtractionService._instance = None
    yield
    settings.ENABLE_SUBSCRIPTIONS = original_subs
    settings.AI_API_KEY = original_ai_key
    settings.OLLAMA_BASE_URL = original_ollama_url
    QueryService._instance = None
    FamilyService._instance = None
    ExtractionService._instance = None
