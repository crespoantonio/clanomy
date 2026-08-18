import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine, SQLModel
from sqlalchemy.pool import StaticPool
import sys

from src.core.config import settings

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
from src.services.query_service import QueryService
from src.services.extraction_service import ExtractionService

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
    async def mock_extraction_call(self, system_prompt: str, text: str) -> str:
        import json, re
        
        # Try to find a number in the text
        amount = 25.50
        amount_match = re.search(r'\b\d+(?:\.\d{1,2})?\b', text)
        if amount_match:
            amount = float(amount_match.group(0))
            
        concept = text
        if "coffee" in text.lower():
            concept = "coffee"
        elif "groceries" in text.lower():
            concept = "groceries at Walmart"
            
        return json.dumps({
            "amount": amount,
            "category": "Food/Drink",
            "concept": concept,
            "currency": "USD"
        })

    async def mock_parse_intent(self, text: str, reference_time=None):
        from src.services.query_service import ParsedQueryIntent
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
        elif any(char.isdigit() for char in lower_query):
            return ParsedQueryIntent(intent="log_expense")
        else:
            return ParsedQueryIntent(intent="spending_summary", timeframe="this_month")

    monkeypatch.setattr("src.services.extraction_service.ExtractionService._call_ollama", mock_extraction_call)
    monkeypatch.setattr("src.services.query_service.QueryService.parse_intent", mock_parse_intent)

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
            self.messages.append({"chat_id": chat_id, "text": text})
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
    def _create_payload(text=None, voice_file_id=None, user_id=12345, first_name="Tony"):
        payload = {
            "message": {
                "chat": {"id": user_id, "type": "private"},
                "from": {
                    "id": user_id,
                    "username": f"user_{user_id}",
                    "first_name": first_name
                }
            }
        }
        if text:
            payload["message"]["text"] = text
        if voice_file_id:
            payload["message"]["voice"] = {"file_id": voice_file_id}
            
        return payload
    return _create_payload
