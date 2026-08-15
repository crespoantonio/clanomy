import pytest
from fastapi.testclient import TestClient
from src.main import app
from src.core.config import settings
from src.db.session import get_session
from sqlmodel import Session, create_engine, SQLModel, select
from src.db.models import User
from sqlalchemy.pool import StaticPool

client = TestClient(app)

# Setup in-memory SQLite for testing
test_engine = create_engine(
    "sqlite://", 
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)

def get_test_session():
    with Session(test_engine) as session:
        yield session

app.dependency_overrides[get_session] = get_test_session

@pytest.fixture(autouse=True)
def setup_db():
    SQLModel.metadata.create_all(test_engine)
    yield
    SQLModel.metadata.drop_all(test_engine)

def test_webhook_invalid_secret():
    response = client.post(
        "/api/v1/telegram/webhook",
        json={
            "message": {
                "chat": {"id": 12345, "type": "private"},
                "from": {"id": 12345, "username": "tony_test", "first_name": "Tony"},
                "text": "/start"
            }
        },
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"}
    )
    assert response.status_code == 403
    assert response.json() == {"detail": "Invalid secret token"}

def test_webhook_missing_secret():
    response = client.post(
        "/api/v1/telegram/webhook",
        json={
            "message": {
                "chat": {"id": 12345, "type": "private"},
                "from": {"id": 12345, "username": "tony_test", "first_name": "Tony"},
                "text": "/start"
            }
        }
    )
    assert response.status_code == 403
    assert response.json() == {"detail": "Invalid secret token"}

def test_webhook_success_registration(monkeypatch):
    # Mock settings secret
    monkeypatch.setattr(settings, "MESSAGING_WEBHOOK_SECRET", "valid-secret")
    
    # Mock TelegramService
    class MockTelegramService:
        async def send_message(self, chat_id, text):
            pass
    monkeypatch.setattr("src.api.routes.telegram.TelegramService", MockTelegramService)
    
    # Mock payload for Telegram Update
    payload = {
        "message": {
            "chat": {"id": 12345, "type": "private"},
            "from": {
                "id": 12345,
                "username": "tony_test",
                "first_name": "Tony",
                "last_name": "Crespo"
            },
            "text": "/start"
        }
    }
    
    # We expect a success response with ok status
    response = client.post(
        "/api/v1/telegram/webhook",
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["status"] == "ok"
    
    # Verify DB record creation
    with Session(test_engine) as session:
        user = session.exec(select(User).where(User.telegram_id == 12345)).first()
        assert user is not None
        assert user.username == "tony_test"
        assert user.full_name == "Tony Crespo"

def test_webhook_transaction_processing(monkeypatch):
    monkeypatch.setattr(settings, "MESSAGING_WEBHOOK_SECRET", "valid-secret")
    
    # Mock AIOrchestrator
    class MockOrchestrator:
        async def orchestrate(self, user_id, text, audio_file_id, chat_id):
            pass
    monkeypatch.setattr("src.api.routes.telegram.AIOrchestrator", MockOrchestrator)
    
    payload = {
        "message": {
            "chat": {"id": 12345, "type": "private"},
            "from": {
                "id": 12345,
                "username": "tony_test"
            },
            "text": "50 for lunch"
        }
    }
    
    response = client.post(
        "/api/v1/telegram/webhook",
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["status"] == "ok"
