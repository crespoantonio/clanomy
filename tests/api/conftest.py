import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine, SQLModel
from sqlalchemy.pool import StaticPool
import sys

from src.core.config import settings
settings.USER_COOLDOWN_SECONDS = 0.0

# Setup in-memory SQLite for testing to avoid polluting real DB
test_engine = create_engine(
    "sqlite://", 
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)

# Patch the engine globally before importing the app or routes
import src.db.session
src.db.session.engine = test_engine

# Now we can safely import app
from src.main import app
from src.services.query import QueryService, ParsedQueryIntent
from src.services.extraction import ExtractionService

def get_test_session():
    with Session(test_engine) as session:
        yield session

# Override the dependency globally for all API tests
app.dependency_overrides[src.db.session.get_session] = get_test_session

@pytest.fixture(autouse=True)
def setup_db():
    SQLModel.metadata.create_all(test_engine)
    yield
    SQLModel.metadata.drop_all(test_engine)

@pytest.fixture(autouse=True)
def mock_llm_responses(monkeypatch):
    """
    Deterministically mock LLM responses so tests run fast and don't fail due to 
    LLM output variance.
    """
    async def mock_extract(self, text: str, *args, default_currency="USD", primary_currency=None, **kwargs):
        from src.services.extraction.models import UnifiedResult
        import re

        text_lower = (text or '').lower()
        amount_match = re.search(r'\b\d+(?:\.\d{1,2})?\b', text)
        is_query = any(kw in text_lower for kw in ["how", "what", "show", "tell", "summary", "breakdown", "total", "query", "compare", "list"])
        if is_query and not amount_match:
            return UnifiedResult(action="query", amount=None)

        amount = 25.50
        if amount_match:
            amount = float(amount_match.group(0))
            
        concept = text
        tx_type = "expense"
        category = "Food/Drink"
        if "salary" in text_lower or "earned" in text_lower or "got paid" in text_lower or "income" in text_lower or "freelance" in text_lower:
            tx_type = "income"
            category = "Salary" if "salary" in text_lower or "got paid" in text_lower else "Freelance"
            concept = "Acme Corp" if "acme" in text_lower else text
        elif "coffee" in text_lower:
            concept = "coffee"
        elif "groceries" in text_lower:
            concept = "groceries at Walmart"
            
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
        lower_query = text.lower()
        if "export" in lower_query:
            return ParsedQueryIntent(intent="export_data", export_format="csv")
        elif "compare" in lower_query:
            return ParsedQueryIntent(intent="spending_summary", timeframe="this_week")
        elif "create family" in lower_query or "/createfamily" in lower_query:
            return ParsedQueryIntent(intent="create_family", family_name="The Smiths")
        elif "/join_" in lower_query:
            return ParsedQueryIntent(intent="join_family")
        elif "delete" in lower_query:
            return ParsedQueryIntent(intent="delete_account")
        elif "notion" in lower_query:
            return ParsedQueryIntent(intent="notion_manage")
        elif "/invite" in lower_query:
            return ParsedQueryIntent(intent="generate_invite")
        elif any(kw in lower_query for kw in ["how", "what", "show", "tell", "summary", "breakdown", "total", "query", "compare", "list"]):
            if "earn" in lower_query or "income" in lower_query or "salary" in lower_query or "make" in lower_query or "made" in lower_query:
                return ParsedQueryIntent(intent="income_summary", timeframe="this_month")
            elif "net" in lower_query or "cash flow" in lower_query or "balance" in lower_query or "left over" in lower_query or "saved" in lower_query or "surplus" in lower_query:
                return ParsedQueryIntent(intent="net_cash_flow", timeframe="this_month")
            else:
                return ParsedQueryIntent(intent="spending_summary", timeframe="this_month")
        elif any(char.isdigit() for char in lower_query):
            return ParsedQueryIntent(intent="log_expense")
        else:
            if "earn" in lower_query or "income" in lower_query or "salary" in lower_query or "make" in lower_query or "made" in lower_query:
                return ParsedQueryIntent(intent="income_summary", timeframe="this_month")
            elif "net" in lower_query or "cash flow" in lower_query or "balance" in lower_query:
                return ParsedQueryIntent(intent="net_cash_flow", timeframe="this_month")
            return ParsedQueryIntent(intent="spending_summary", timeframe="this_month")

    monkeypatch.setattr("src.services.extraction.ExtractionService.extract", mock_extract)
    monkeypatch.setattr("src.services.extraction.ExtractionService.classify_and_extract", mock_extract)
    monkeypatch.setattr("src.services.query.QueryService.parse_intent", mock_parse_intent)

@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singletons to avoid state bleed between tests."""
    QueryService._instance = None
    ExtractionService._instance = None
    yield
    QueryService._instance = None
    ExtractionService._instance = None

@pytest.fixture
def app_client(monkeypatch):
    # Set the webhook secret to a known value
    monkeypatch.setattr(settings, "MESSAGING_WEBHOOK_SECRET", "valid-secret")
    monkeypatch.setattr("src.main.run_migrations", lambda: None)
    # For tests, we use TestClient
    with TestClient(app) as c:
        yield c

@pytest.fixture
def mock_telegram(monkeypatch):
    """
    Mocks the TelegramService to intercept outbound messages instead of 
    hitting the real Telegram API, allowing us to assert on the bot's responses.
    """
    class MockTelegramService:
        def __init__(self):
            self.messages = []
            
        async def send_message(self, chat_id, text, **kwargs):
            self.messages.append({"chat_id": chat_id, "text": text, **kwargs})
            return True
            
        async def send_document(self, chat_id, document=None, caption=None, **kwargs):
            self.messages.append({"chat_id": chat_id, "document": document, "caption": caption, **kwargs})
            return True

        async def get_bot_username(self) -> str:
            return "mock_bot"
            
    mock_instance = MockTelegramService()
    
    monkeypatch.setattr("src.api.routes.telegram.TelegramService", lambda: mock_instance)
    
    try:
        monkeypatch.setattr("src.services.telegram_service.TelegramService", lambda: mock_instance)
    except AttributeError:
        pass
        
    try:
        monkeypatch.setattr("src.services.billing.billing_service.TelegramService", lambda: mock_instance)
    except (AttributeError, ModuleNotFoundError):
        pass


    try:
        monkeypatch.setattr("src.services.ai_orchestrator.TelegramService", lambda: mock_instance)
    except AttributeError:
        pass
        
    try:
        monkeypatch.setattr("src.services.family_service.TelegramService", lambda: mock_instance)
    except AttributeError:
        pass
        
    try:
        monkeypatch.setattr("src.services.export_service.TelegramService", lambda: mock_instance)
    except AttributeError:
        pass
        
    try:
        monkeypatch.setattr("src.services.messaging_service.TelegramService", lambda: mock_instance)
    except AttributeError:
        pass
        
    return mock_instance

@pytest.fixture
def telegram_payload_factory():
    """Generates standard Telegram webhook payloads."""
    def _create_payload(
        text=None,
        voice_file_id=None,
        user_id=12345,
        first_name="Tony",
        username=None,
        successful_payment=None,
        refunded_payment=None,
        pre_checkout_query=None
    ):
        if pre_checkout_query is not None:
            return {
                "update_id": 10001,
                "pre_checkout_query": pre_checkout_query
            }

        payload = {
            "message": {
                "chat": {"id": user_id, "type": "private"},
                "from": {
                    "id": user_id,
                    "username": username or f"user_{user_id}",
                    "first_name": first_name
                }
            }
        }
        if text:
            payload["message"]["text"] = text
        if voice_file_id:
            payload["message"]["voice"] = {"file_id": voice_file_id}
        if successful_payment:
            payload["message"]["successful_payment"] = successful_payment
        if refunded_payment:
            payload["message"]["refunded_payment"] = refunded_payment
            
        return payload
    return _create_payload

