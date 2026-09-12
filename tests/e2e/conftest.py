import hmac
import hashlib
import time
import json
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine, SQLModel
from sqlalchemy.pool import StaticPool

from src.core.config import settings
settings.USER_COOLDOWN_SECONDS = 0.0

from tests.api.conftest import (
    test_engine as e2e_test_engine,
    app,
    mock_telegram,
    telegram_payload_factory,
    get_test_session,
)

import src.db.session
import src.db.models

@pytest.fixture(autouse=True)
def setup_e2e_db():
    SQLModel.metadata.create_all(e2e_test_engine)
    yield
    SQLModel.metadata.drop_all(e2e_test_engine)

@pytest.fixture(autouse=True)
def mock_e2e_llm_responses(monkeypatch):
    """
    Deterministic LLM extraction mock for hermetic E2E tests.
    Parses amounts, concepts, categories, and query intents reliably.
    """
    async def mock_extract(self, text: str, *args, default_currency="USD", primary_currency=None, **kwargs):
        from src.services.extraction.models import UnifiedResult
        import re

        text_lower = (text or '').lower()
        amount_match = re.search(r'\b\d+(?:\.\d{1,2})?\b', text)
        query_kws = ["how", "what", "show", "tell", "summary", "breakdown", "total", "query", "compare", "list", "export", "delete", "account", "invite", "family", "notion"]
        is_query = any(kw in text_lower for kw in query_kws)
        if is_query and not amount_match:
            return UnifiedResult(action="query", amount=None)

        amount = 25.50
        if amount_match:
            amount = float(amount_match.group(0))
            
        concept = text
        tx_type = "expense"
        category = "Food/Drink"
        if any(w in text_lower for w in ["salary", "earned", "got paid", "income", "freelance"]):
            tx_type = "income"
            category = "Salary" if "salary" in text_lower or "got paid" in text_lower else "Freelance"
            concept = "Acme Corp" if "acme" in text_lower else text
        elif "groceries" in text_lower:
            concept = "groceries at Trader Joe's" if "trader joe" in text_lower else "groceries"
            category = "Groceries"
        elif "dinner" in text_lower:
            concept = "dinner"
            category = "Dining"
        elif "coffee" in text_lower:
            concept = "coffee"
            category = "Food/Drink"
            
        return UnifiedResult(
            action="log_transaction",
            type=tx_type,
            amount=amount,
            category=category,
            concept=concept,
            currency=primary_currency or default_currency or "USD"
        )

    async def mock_parse_intent(self, text: str, reference_time=None):
        from src.services.query import ParsedQueryIntent
        lower_query = (text or "").lower()
        if "export" in lower_query:
            return ParsedQueryIntent(intent="export_data", export_format="csv")
        elif "compare" in lower_query:
            return ParsedQueryIntent(intent="spending_summary", timeframe="this_week")
        elif any(kw in lower_query for kw in ["how", "what", "show", "tell", "summary", "breakdown", "total", "query", "list"]):
            if any(w in lower_query for w in ["earn", "income", "salary", "make", "made"]):
                return ParsedQueryIntent(intent="income_summary", timeframe="this_month")
            elif any(w in lower_query for w in ["net", "cash flow", "balance", "left over", "saved", "surplus"]):
                return ParsedQueryIntent(intent="net_cash_flow", timeframe="this_month")
            else:
                return ParsedQueryIntent(intent="spending_summary", timeframe="this_month")
        elif any(char.isdigit() for char in lower_query):
            return ParsedQueryIntent(intent="log_expense")
        else:
            return ParsedQueryIntent(intent="spending_summary", timeframe="this_month")

    monkeypatch.setattr("src.services.extraction.ExtractionService.extract", mock_extract)
    monkeypatch.setattr("src.services.extraction.ExtractionService.classify_and_extract", mock_extract)
    monkeypatch.setattr("src.services.query.QueryService.parse_intent", mock_parse_intent)

@pytest.fixture
def mock_telegram(monkeypatch):
    """
    Message spy intercepting all outbound TelegramService calls.
    """
    class MockTelegramSpy:
        def __init__(self):
            self.messages = []
            self.edited_messages = []
            self.answered_callbacks = []
            self.deleted_messages = []
            
        async def send_message(self, chat_id, text, **kwargs):
            self.messages.append({"chat_id": chat_id, "text": text, **kwargs})
            return True

        async def edit_message_text(self, chat_id, message_id, text, **kwargs):
            entry = {"chat_id": chat_id, "message_id": message_id, "text": text, **kwargs}
            self.edited_messages.append(entry)
            self.messages.append(entry)
            return True

        async def answer_callback_query(self, callback_query_id, text=None, **kwargs):
            self.answered_callbacks.append({"callback_query_id": callback_query_id, "text": text, **kwargs})
            return True

        async def delete_message(self, chat_id, message_id, **kwargs):
            self.deleted_messages.append({"chat_id": chat_id, "message_id": message_id, **kwargs})
            return True
            
        async def send_document(self, chat_id, document=None, caption=None, **kwargs):
            self.messages.append({"chat_id": chat_id, "document": document, "caption": caption, **kwargs})
            return True

        async def get_bot_username(self) -> str:
            return "clanomy_e2e_bot"
            
    spy = MockTelegramSpy()
    monkeypatch.setattr("src.api.routes.telegram.TelegramService", lambda: spy)
    monkeypatch.setattr("src.services.telegram_service.TelegramService", lambda: spy)
    try:
        monkeypatch.setattr("src.services.billing.billing_service.TelegramService", lambda: spy)
    except (AttributeError, ModuleNotFoundError):
        pass
    try:
        monkeypatch.setattr("src.services.ai_orchestrator.TelegramService", lambda: spy)
    except AttributeError:
        pass
    try:
        monkeypatch.setattr("src.services.family_service.TelegramService", lambda: spy)
    except AttributeError:
        pass
    try:
        monkeypatch.setattr("src.services.export_service.TelegramService", lambda: spy)
    except AttributeError:
        pass
    try:
        monkeypatch.setattr("src.services.messaging_service.TelegramService", lambda: spy)
    except AttributeError:
        pass

    return spy

@pytest.fixture
def app_client(monkeypatch):
    """TestClient configured with standard E2E test secrets."""
    monkeypatch.setattr(settings, "MESSAGING_WEBHOOK_SECRET", "valid-secret")
    monkeypatch.setattr(settings, "PADDLE_WEBHOOK_SECRET_KEY", "pdl_ntfset_test_secret_e2e")
    monkeypatch.setattr(settings, "ENABLE_SUBSCRIPTIONS", True)
    monkeypatch.setattr(settings, "ALLOW_LOCAL_AI_WITH_SUBSCRIPTIONS", True)
    monkeypatch.setattr("src.main.run_migrations", lambda: None)
    with TestClient(app) as client:
        yield client

@pytest.fixture
def telegram_payload_factory():
    """Generates standard Telegram update payloads."""
    def _create(text=None, user_id=90001, first_name="E2E_User", username=None):
        payload = {
            "update_id": int(time.time()),
            "message": {
                "message_id": 101,
                "chat": {"id": user_id, "type": "private"},
                "from": {
                    "id": user_id,
                    "is_bot": False,
                    "first_name": first_name,
                    "username": username or f"user_{user_id}"
                }
            }
        }
        if text:
            payload["message"]["text"] = text
        return payload
    return _create

@pytest.fixture
def paddle_webhook_factory():
    """Generates signed Paddle webhook payloads with valid HMAC-SHA256 headers."""
    def _create(event_type: str, data: dict, event_id: str = None, secret: str = None):
        secret_key = secret or settings.PADDLE_WEBHOOK_SECRET_KEY or "pdl_ntfset_test_secret_e2e"
        evt_id = event_id or f"evt_e2e_{int(time.time())}"
        payload_dict = {
            "event_id": evt_id,
            "event_type": event_type,
            "occurred_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "data": data
        }
        raw_body = json.dumps(payload_dict)
        timestamp = int(time.time())
        signed_payload = f"{timestamp}:{raw_body}"
        h1 = hmac.new(secret_key.encode("utf-8"), signed_payload.encode("utf-8"), hashlib.sha256).hexdigest()
        signature_header = f"ts={timestamp};h1={h1}"
        return raw_body, signature_header
    return _create
