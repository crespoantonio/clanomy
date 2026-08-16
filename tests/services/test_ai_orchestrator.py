import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock
from src.services.ai_orchestrator import AIOrchestrator
from src.core.config import settings
from src.db.models import Transaction, User
from uuid import UUID
import datetime

@pytest.fixture
def orchestrator():
    return AIOrchestrator()

def create_mock_query_service(intent="log_expense"):
    mock_parse = AsyncMock()
    mock_result = MagicMock()
    mock_result.intent = intent
    mock_parse.return_value = mock_result
    class MockQueryService:
        parse_intent = mock_parse
    return MockQueryService

@pytest.mark.anyio
async def test_orchestrator_success_text(orchestrator, monkeypatch):
    user_id = "00000000-0000-0000-0000-000000000000"
    
    mock_extract = AsyncMock()
    mock_extract_result = MagicMock()
    mock_extract_result.amount = 15.0
    mock_extract_result.currency = "USD"
    mock_extract_result.concept = "Starbucks"
    mock_extract_result.category = "Food/Drink"
    mock_extract_result.model_dump.return_value = {
        "amount": 15.0,
        "currency": "USD",
        "concept": "Starbucks",
        "category": "Food/Drink"
    }
    mock_extract.return_value = mock_extract_result

    class MockExtractionService:
        extract = mock_extract

    monkeypatch.setattr("src.services.ai_orchestrator.QueryService", create_mock_query_service())
    monkeypatch.setattr("src.services.ai_orchestrator.ExtractionService", MockExtractionService)
    
    # Mock TelegramService
    mock_send_message = AsyncMock()
    class MockTelegramService:
        send_message = mock_send_message
    monkeypatch.setattr("src.services.ai_orchestrator.TelegramService", MockTelegramService)

    # Mock Session and EncryptionService
    mock_session = MagicMock()
    mock_session_class = MagicMock()
    mock_session_class.return_value.__enter__.return_value = mock_session
    monkeypatch.setattr("src.services.ai_orchestrator.Session", mock_session_class)
    
    class MockEncryptionService:
        def encrypt(self, text): return text
    monkeypatch.setattr(orchestrator, "encryption_service", MockEncryptionService())

    await orchestrator.orchestrate(user_id=user_id, text="15 for Starbucks", audio_file_id=None, chat_id=12345)
    
    # Extract service was called
    mock_extract.assert_called_once_with(text="15 for Starbucks")
    
    # TelegramService was called
    mock_send_message.assert_called_once()
    call_args = mock_send_message.call_args
    assert call_args[1]["chat_id"] == 12345
    assert "Saved 15.0 USD for 'Starbucks' under category 'Food/Drink'." in call_args[1]["text"]

@pytest.mark.anyio
async def test_orchestrator_audio_success(orchestrator, monkeypatch):
    user_id = "00000000-0000-0000-0000-000000000000"
    
    mock_transcribe = AsyncMock(return_value=("20 for taxi", "en"))
    class MockWhisperService:
        transcribe = mock_transcribe
    monkeypatch.setattr("src.services.ai_orchestrator.WhisperService", MockWhisperService)
    
    mock_extract = AsyncMock()
    mock_extract_result = MagicMock()
    mock_extract_result.amount = 20.0
    mock_extract_result.currency = "USD"
    mock_extract_result.concept = "Taxi"
    mock_extract_result.category = "Transport"
    mock_extract_result.model_dump.return_value = {"amount": 20.0}
    mock_extract.return_value = mock_extract_result

    class MockExtractionService:
        extract = mock_extract
    monkeypatch.setattr("src.services.ai_orchestrator.QueryService", create_mock_query_service())
    monkeypatch.setattr("src.services.ai_orchestrator.ExtractionService", MockExtractionService)
    
    # Mock TelegramService
    mock_send_message = AsyncMock()
    mock_get_file = AsyncMock(return_value="https://api.telegram.org/file/bot123/voice.ogg")
    class MockTelegramService:
        send_message = mock_send_message
        get_file_url = mock_get_file
    monkeypatch.setattr("src.services.ai_orchestrator.TelegramService", MockTelegramService)

    # Mock Session and EncryptionService
    mock_session = MagicMock()
    mock_session_class = MagicMock()
    mock_session_class.return_value.__enter__.return_value = mock_session
    monkeypatch.setattr("src.services.ai_orchestrator.Session", mock_session_class)
    
    class MockEncryptionService:
        def encrypt(self, text): return text
    monkeypatch.setattr(orchestrator, "encryption_service", MockEncryptionService())

    await orchestrator.orchestrate(user_id=user_id, text=None, audio_file_id="file_123", chat_id=1)
    
    mock_get_file.assert_called_once_with("file_123")
    mock_transcribe.assert_called_once_with(audio_url="https://api.telegram.org/file/bot123/voice.ogg")
    mock_extract.assert_called_once_with(text="20 for taxi")
    mock_send_message.assert_called_once()
    assert "Saved 20.0" in mock_send_message.call_args[1]["text"]

@pytest.mark.anyio
async def test_orchestrator_transcription_failure(orchestrator, monkeypatch):
    user_id = "00000000-0000-0000-0000-000000000000"
    
    mock_transcribe = AsyncMock(return_value=("", "en")) # triggers empty error
    class MockWhisperService:
        transcribe = mock_transcribe
    monkeypatch.setattr("src.services.ai_orchestrator.WhisperService", MockWhisperService)
    
    mock_send_message = AsyncMock()
    mock_get_file = AsyncMock(return_value="https://api.telegram.org/file/bot123/voice.ogg")
    class MockTelegramService:
        send_message = mock_send_message
        get_file_url = mock_get_file
    monkeypatch.setattr("src.services.ai_orchestrator.TelegramService", MockTelegramService)

    await orchestrator.orchestrate(user_id=user_id, text=None, audio_file_id="file_123", chat_id=1)
    
    mock_send_message.assert_called_once()
    assert "understand the audio" in mock_send_message.call_args[1]["text"]

@pytest.mark.anyio
async def test_orchestrator_extraction_timeout(orchestrator, monkeypatch):
    user_id = "00000000-0000-0000-0000-000000000000"
    
    mock_extract = AsyncMock(side_effect=Exception("Ollama timed out"))
    class MockExtractionService:
        extract = mock_extract
    monkeypatch.setattr("src.services.ai_orchestrator.QueryService", create_mock_query_service())
    monkeypatch.setattr("src.services.ai_orchestrator.ExtractionService", MockExtractionService)
    
    mock_send_message = AsyncMock()
    class MockTelegramService:
        send_message = mock_send_message
    monkeypatch.setattr("src.services.ai_orchestrator.TelegramService", MockTelegramService)

    await orchestrator.orchestrate(user_id=user_id, text="15 for Starbucks", audio_file_id=None, chat_id=12345)
    
    mock_send_message.assert_called_once()
    assert "couldn't extract the details" in mock_send_message.call_args[1]["text"]

@pytest.mark.anyio
async def test_orchestrator_callback_failure(orchestrator, monkeypatch):
    user_id = "00000000-0000-0000-0000-000000000000"
    
    mock_extract = AsyncMock()
    mock_extract_result = MagicMock()
    mock_extract_result.amount = 15.0
    mock_extract_result.currency = "USD"
    mock_extract_result.concept = "Starbucks"
    mock_extract_result.category = "Food/Drink"
    mock_extract_result.model_dump.return_value = {"amount": 15.0}
    mock_extract.return_value = mock_extract_result
    class MockExtractionService:
        extract = mock_extract
    monkeypatch.setattr("src.services.ai_orchestrator.QueryService", create_mock_query_service())
    monkeypatch.setattr("src.services.ai_orchestrator.ExtractionService", MockExtractionService)
    
    # Mock client post raising error in TelegramService
    mock_send_message = AsyncMock(side_effect=Exception("Telegram connection failed"))
    class MockTelegramService:
        send_message = mock_send_message
    monkeypatch.setattr("src.services.ai_orchestrator.TelegramService", MockTelegramService)

    # This should not raise an exception because the orchestrator catches it
    await orchestrator.orchestrate(user_id=user_id, text="15 for Starbucks", audio_file_id=None, chat_id=12345)
    mock_send_message.assert_called_once()

@pytest.mark.anyio
async def test_orchestrator_persistence_success(orchestrator, monkeypatch):
    user_id = "00000000-0000-0000-0000-000000000000"
    family_id = "11111111-1111-1111-1111-111111111111"
    
    mock_extract = AsyncMock()
    mock_extract_result = MagicMock()
    mock_extract_result.amount = 15.0
    mock_extract_result.currency = "USD"
    mock_extract_result.concept = "Starbucks"
    mock_extract_result.category = "Food/Drink"
    mock_extract_result.model_dump.return_value = {"amount": 15.0}
    mock_extract.return_value = mock_extract_result
    
    class MockExtractionService:
        extract = mock_extract
    monkeypatch.setattr("src.services.ai_orchestrator.QueryService", create_mock_query_service())
    monkeypatch.setattr("src.services.ai_orchestrator.ExtractionService", MockExtractionService)

    mock_send_message = AsyncMock()
    class MockTelegramService:
        send_message = mock_send_message
    monkeypatch.setattr("src.services.ai_orchestrator.TelegramService", MockTelegramService)

    # Mock DB Session
    mock_session = MagicMock()
    mock_session_class = MagicMock()
    mock_session_class.return_value.__enter__.return_value = mock_session
    monkeypatch.setattr("src.services.ai_orchestrator.Session", mock_session_class)

    # Mock User query
    mock_user = MagicMock(family_id=UUID(family_id))
    mock_session.get.return_value = mock_user

    # Mock Encryption
    mock_encrypt = MagicMock()
    mock_encrypt.side_effect = lambda text: f"encrypted_{text}"
    class MockEncryptionService:
        def encrypt(self, text): return mock_encrypt(text)
    monkeypatch.setattr(orchestrator, "encryption_service", MockEncryptionService())

    await orchestrator.orchestrate(user_id=user_id, text="15 for Starbucks", audio_file_id=None, chat_id=12345)

    mock_session.get.assert_called_once_with(User, UUID(user_id))
    
    mock_session.add.assert_called_once()
    added_transaction = mock_session.add.call_args[0][0]
    assert isinstance(added_transaction, Transaction)
    assert added_transaction.user_id == UUID(user_id)
    assert added_transaction.family_id == UUID(family_id)
    assert added_transaction.amount == "encrypted_15.0 USD"
    assert added_transaction.concept == "encrypted_Starbucks"
    
    mock_session.commit.assert_called_once()

@pytest.mark.anyio
async def test_orchestrator_persistence_failure_rollback(orchestrator, monkeypatch):
    user_id = "00000000-0000-0000-0000-000000000000"
    
    mock_extract = AsyncMock()
    mock_extract_result = MagicMock()
    mock_extract_result.amount = 15.0
    mock_extract_result.currency = "USD"
    mock_extract_result.concept = "Starbucks"
    mock_extract_result.category = "Food/Drink"
    mock_extract.return_value = mock_extract_result
    class MockExtractionService:
        extract = mock_extract
    monkeypatch.setattr("src.services.ai_orchestrator.QueryService", create_mock_query_service())
    monkeypatch.setattr("src.services.ai_orchestrator.ExtractionService", MockExtractionService)

    mock_send_message = AsyncMock()
    class MockTelegramService:
        send_message = mock_send_message
    monkeypatch.setattr("src.services.ai_orchestrator.TelegramService", MockTelegramService)

    # Mock DB Session with commit failure
    mock_session = MagicMock()
    mock_session.commit.side_effect = Exception("DB Error")
    mock_session_class = MagicMock()
    mock_session_class.return_value.__enter__.return_value = mock_session
    monkeypatch.setattr("src.services.ai_orchestrator.Session", mock_session_class)

    # Mock Encryption
    class MockEncryptionService:
        def encrypt(self, text): return f"encrypted_{text}"
    monkeypatch.setattr(orchestrator, "encryption_service", MockEncryptionService())

    await orchestrator.orchestrate(user_id=user_id, text="15 for Starbucks", audio_file_id=None, chat_id=12345)

    mock_session.rollback.assert_called_once()
    
    mock_send_message.assert_called_once()
    assert "Failed to save transaction" in mock_send_message.call_args[1]["text"] or "An unexpected error occurred" in mock_send_message.call_args[1]["text"]


@pytest.mark.anyio
async def test_orchestrator_delete_account_intent(orchestrator, monkeypatch):
    user_id = "00000000-0000-0000-0000-000000000000"
    
    monkeypatch.setattr("src.services.ai_orchestrator.QueryService", create_mock_query_service("delete_account"))
    
    mock_send_message = AsyncMock()
    class MockTelegramService:
        send_message = mock_send_message
    monkeypatch.setattr("src.services.ai_orchestrator.TelegramService", MockTelegramService)
    
    await orchestrator.orchestrate(user_id=user_id, text="delete my account", audio_file_id=None, chat_id=12345)
    
    mock_send_message.assert_called_once()
    assert "Are you sure you want to permanently delete your account" in mock_send_message.call_args[1]["text"]

@pytest.mark.anyio
async def test_orchestrator_confirm_delete(orchestrator, monkeypatch):
    user_id = "00000000-0000-0000-0000-000000000000"
    
    mock_delete = AsyncMock(return_value=True)
    class MockAccountService:
        delete_account = mock_delete
    monkeypatch.setattr("src.services.ai_orchestrator.AccountService", MockAccountService)
    
    mock_send_message = AsyncMock()
    class MockTelegramService:
        send_message = mock_send_message
    monkeypatch.setattr("src.services.ai_orchestrator.TelegramService", MockTelegramService)
    
    await orchestrator.orchestrate(user_id=user_id, text="CONFIRM DELETE", audio_file_id=None, chat_id=12345)
    
    mock_delete.assert_called_once_with(UUID(user_id))
    mock_send_message.assert_called_once()
    assert "permanently deleted" in mock_send_message.call_args[1]["text"]
