import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch
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
    mock_extract_result.transaction_date = None
    mock_extract_result.to_datetime.return_value = datetime.datetime.now(datetime.timezone.utc)
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
async def test_orchestrator_success_text_retroactive(orchestrator, monkeypatch):
    user_id = "00000000-0000-0000-0000-000000000000"
    
    mock_extract = AsyncMock()
    mock_extract_result = MagicMock()
    mock_extract_result.amount = 15.0
    mock_extract_result.currency = "USD"
    mock_extract_result.concept = "Starbucks"
    mock_extract_result.category = "Food/Drink"
    mock_extract_result.transaction_date = "2026-08-11"
    
    dt = datetime.datetime(2026, 8, 11, 12, 0, 0, tzinfo=datetime.timezone.utc)
    mock_extract_result.to_datetime.return_value = dt
    mock_extract_result.model_dump.return_value = {
        "amount": 15.0,
        "currency": "USD",
        "concept": "Starbucks",
        "category": "Food/Drink",
        "transaction_date": "2026-08-11"
    }
    mock_extract.return_value = mock_extract_result

    class MockExtractionService:
        extract = mock_extract

    monkeypatch.setattr("src.services.ai_orchestrator.QueryService", create_mock_query_service())
    monkeypatch.setattr("src.services.ai_orchestrator.ExtractionService", MockExtractionService)
    
    mock_send_message = AsyncMock()
    class MockTelegramService:
        send_message = mock_send_message
    monkeypatch.setattr("src.services.ai_orchestrator.TelegramService", MockTelegramService)

    mock_session = MagicMock()
    mock_session_class = MagicMock()
    mock_session_class.return_value.__enter__.return_value = mock_session
    monkeypatch.setattr("src.services.ai_orchestrator.Session", mock_session_class)
    
    class MockEncryptionService:
        def encrypt(self, text): return text
    monkeypatch.setattr(orchestrator, "encryption_service", MockEncryptionService())

    await orchestrator.orchestrate(user_id=user_id, text="last week 15 for Starbucks", audio_file_id=None, chat_id=12345)
    
    mock_send_message.assert_called_once()
    call_args = mock_send_message.call_args
    assert "Saved 15.0 USD for 'Starbucks' under category 'Food/Drink' (logged for Aug 11, 2026)." in call_args[1]["text"]

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
    mock_extract_result.transaction_date = None
    mock_extract_result.to_datetime.return_value = datetime.datetime.now(datetime.timezone.utc)
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

    mock_session.get.assert_called_with(User, UUID(user_id))
    
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

@pytest.mark.anyio
async def test_orchestrator_create_family(orchestrator, monkeypatch):
    user_id = "00000000-0000-0000-0000-000000000000"
    
    mock_query_service = create_mock_query_service("create_family")
    mock_query_service.parse_intent.return_value.family_name = "New Fam"
    monkeypatch.setattr("src.services.ai_orchestrator.QueryService", mock_query_service)
    
    mock_send_message = AsyncMock()
    class MockTelegramService:
        send_message = mock_send_message
    monkeypatch.setattr("src.services.ai_orchestrator.TelegramService", MockTelegramService)
    
    class MockFamilyService:
        def create_family(self, uid, name):
            pass
    monkeypatch.setattr("src.services.ai_orchestrator.FamilyService", MockFamilyService)
    
    await orchestrator.orchestrate(user_id=user_id, text="create family New Fam", audio_file_id=None, chat_id=12345)
    
    mock_send_message.assert_called_once()
    assert "New Fam" in mock_send_message.call_args[1]["text"]
    assert "created" in mock_send_message.call_args[1]["text"]

@pytest.mark.anyio
async def test_orchestrator_generate_invite(orchestrator, monkeypatch):
    user_id = "00000000-0000-0000-0000-000000000000"
    
    monkeypatch.setattr("src.services.ai_orchestrator.QueryService", create_mock_query_service("generate_invite"))
    
    mock_send_message = AsyncMock()
    class MockTelegramService:
        send_message = mock_send_message
        async def get_bot_username(self):
            return "bot"
    monkeypatch.setattr("src.services.ai_orchestrator.TelegramService", MockTelegramService)
    
    class MockFamilyService:
        def create_invite(self, fid, uid, bot_username=None):
            return type("Invite", (), {}), f"https://t.me/{bot_username or 'bot'}?start=join_xyz"
    monkeypatch.setattr("src.services.ai_orchestrator.FamilyService", MockFamilyService)
    
    monkeypatch.setattr(orchestrator, "_get_user_family_id", lambda x: UUID("11111111-1111-1111-1111-111111111111"))
    
    await orchestrator.orchestrate(user_id=user_id, text="invite link", audio_file_id=None, chat_id=12345)
    
    mock_send_message.assert_called_once()
    assert "https://t.me/bot?start=join_xyz" in mock_send_message.call_args[1]["text"]

@pytest.mark.anyio
async def test_orchestrator_family_info(orchestrator, monkeypatch):
    user_id = "00000000-0000-0000-0000-000000000000"
    
    monkeypatch.setattr("src.services.ai_orchestrator.QueryService", create_mock_query_service("family_info"))
    
    mock_send_message = AsyncMock()
    class MockTelegramService:
        send_message = mock_send_message
    monkeypatch.setattr("src.services.ai_orchestrator.TelegramService", MockTelegramService)
    
    class MockFamilyService:
        def get_family_info(self, uid):
            return {
                "name": "Test Family",
                "members": [{"full_name": "Tony", "username": "tony"}],
                "transactions_count": 5,
                "active_invites_count": 1
            }
    monkeypatch.setattr("src.services.ai_orchestrator.FamilyService", MockFamilyService)
    
    await orchestrator.orchestrate(user_id=user_id, text="family info", audio_file_id=None, chat_id=12345)
    
    mock_send_message.assert_called_once()
    assert "Test Family" in mock_send_message.call_args[1]["text"]
    assert "Tony" in mock_send_message.call_args[1]["text"]

@pytest.mark.anyio
async def test_orchestrator_familytotal_command(orchestrator, monkeypatch):
    user_id = "00000000-0000-0000-0000-000000000000"
    
    mock_send_message = AsyncMock()
    class MockTelegramService:
        send_message = mock_send_message
    monkeypatch.setattr("src.services.ai_orchestrator.TelegramService", MockTelegramService)
    
    class MockFamilyService:
        def get_family_info(self, uid):
            return {
                "id": UUID("11111111-1111-1111-1111-111111111111"),
                "name": "Test Family",
                "members": [{"full_name": "Tony", "username": "tony"}]
            }
    monkeypatch.setattr("src.services.ai_orchestrator.FamilyService", MockFamilyService)

    mock_get_spending_summary = AsyncMock(return_value="Family summary")
    class MockQueryService:
        get_spending_summary = mock_get_spending_summary
    monkeypatch.setattr("src.services.ai_orchestrator.QueryService", MockQueryService)

    await orchestrator.orchestrate(user_id=user_id, text="/familytotal this_week", audio_file_id=None, chat_id=12345)
    
    mock_send_message.assert_called_once()
    assert "Family summary" in mock_send_message.call_args[1]["text"]
    
    call_args = mock_get_spending_summary.call_args
    assert call_args[1]["timeframe"] == "this_week"
    assert call_args[1]["family_name"] == "Test Family"

@pytest.mark.anyio
@patch("src.services.notion_service.NotionService")
async def test_orchestrator_notion_commands(mock_notion_cls, orchestrator, monkeypatch):
    user_id = "00000000-0000-0000-0000-000000000000"
    
    mock_query_service = create_mock_query_service("notion_manage")
    monkeypatch.setattr("src.services.ai_orchestrator.QueryService", mock_query_service)
    
    mock_send_message = AsyncMock()
    class MockTelegramService:
        send_message = mock_send_message
    monkeypatch.setattr("src.services.ai_orchestrator.TelegramService", MockTelegramService)
    
    monkeypatch.setattr(orchestrator, "_get_user_family_id", lambda x: UUID("11111111-1111-1111-1111-111111111111"))
    
    # Mock Session so it doesn't try to access real DB
    mock_session = MagicMock()
    mock_session_class = MagicMock()
    mock_session_class.return_value.__enter__.return_value = mock_session
    monkeypatch.setattr("src.services.ai_orchestrator.Session", mock_session_class)
    
    mock_notion = mock_notion_cls.return_value
    mock_notion.validate_token = AsyncMock(return_value=True)
    mock_notion.search_databases = AsyncMock(return_value=[{"id": "db1", "title": "Budget"}])
    mock_notion.get_family_notion_status.return_value = {
        "is_connected": True, 
        "database_name": "Budget", 
        "database_id": "db1",
        "connected_at": datetime.datetime.now(),
        "has_valid_token": True
    }
    
    await orchestrator.orchestrate(user_id=user_id, text="/notion", audio_file_id=None, chat_id=12345)
    assert "Connect your Notion Workspace" in mock_send_message.call_args[1]["text"]

    await orchestrator.orchestrate(user_id=user_id, text="/notion status", audio_file_id=None, chat_id=12345)
    assert "Connected" in mock_send_message.call_args[1]["text"]

@pytest.mark.anyio
@patch("src.services.ai_orchestrator.NotionService")
async def test_orchestrator_expense_mirroring(mock_notion_cls, orchestrator, monkeypatch):
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
    monkeypatch.setattr("src.services.ai_orchestrator.QueryService", create_mock_query_service("log_expense"))
    monkeypatch.setattr("src.services.ai_orchestrator.ExtractionService", MockExtractionService)

    mock_send_message = AsyncMock()
    class MockTelegramService:
        send_message = mock_send_message
    monkeypatch.setattr("src.services.ai_orchestrator.TelegramService", MockTelegramService)

    mock_session = MagicMock()
    mock_session_class = MagicMock()
    mock_session_class.return_value.__enter__.return_value = mock_session
    monkeypatch.setattr("src.services.ai_orchestrator.Session", mock_session_class)

    mock_user = MagicMock(family_id=UUID(family_id), full_name="Tony", username="tony")
    mock_session.get.return_value = mock_user

    class MockEncryptionService:
        def encrypt(self, text): return f"encrypted_{text}"
    monkeypatch.setattr(orchestrator, "encryption_service", MockEncryptionService())
    
    # Enable Notion status mock
    mock_notion = mock_notion_cls.return_value
    mock_notion.get_family_notion_status.return_value = {"is_connected": True}
    mock_notion.mirror_transaction = AsyncMock(return_value={"status": "mirrored"})
    
    # Mock create_task to await directly for test
    import asyncio
    original_create_task = asyncio.create_task
    def mock_create_task(coro):
        return original_create_task(coro)
    monkeypatch.setattr(asyncio, "create_task", mock_create_task)

    await orchestrator.orchestrate(user_id=user_id, text="15 for Starbucks", audio_file_id=None, chat_id=12345)
    
    # Allow background tasks to run
    await asyncio.sleep(0.1)

    mock_notion.mirror_transaction.assert_called_once()
    kwargs = mock_notion.mirror_transaction.call_args[1]
    assert kwargs["amount"] == 15.0
    assert kwargs["concept"] == "Starbucks"
    assert kwargs["user_name"] == "Tony"
    assert "transaction_id" in kwargs

@pytest.mark.anyio
@patch("src.services.ai_orchestrator.NotionService")
async def test_orchestrator_expense_mirroring_error(mock_notion_cls, orchestrator, monkeypatch):
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
    monkeypatch.setattr("src.services.ai_orchestrator.QueryService", create_mock_query_service("log_expense"))
    monkeypatch.setattr("src.services.ai_orchestrator.ExtractionService", MockExtractionService)

    mock_send_message = AsyncMock()
    class MockTelegramService:
        send_message = mock_send_message
    monkeypatch.setattr("src.services.ai_orchestrator.TelegramService", MockTelegramService)

    mock_session = MagicMock()
    mock_session_class = MagicMock()
    mock_session_class.return_value.__enter__.return_value = mock_session
    monkeypatch.setattr("src.services.ai_orchestrator.Session", mock_session_class)

    mock_user = MagicMock(family_id=UUID(family_id), full_name="Tony")
    mock_session.get.return_value = mock_user

    class MockEncryptionService:
        def encrypt(self, text): return f"encrypted_{text}"
    monkeypatch.setattr(orchestrator, "encryption_service", MockEncryptionService())
    
    mock_notion = mock_notion_cls.return_value
    mock_notion.get_family_notion_status.return_value = {"is_connected": True}
    mock_notion.mirror_transaction = AsyncMock(side_effect=Exception("API Error"))
    
    import asyncio
    
    await orchestrator.orchestrate(user_id=user_id, text="15 for Starbucks", audio_file_id=None, chat_id=12345)
    await asyncio.sleep(0.1)
    
    # Should not crash and should send telegram message
    mock_send_message.assert_called_once()
    mock_session.commit.assert_called_once()

@pytest.mark.anyio
@patch("src.services.ai_orchestrator.NotionService")
async def test_orchestrator_notion_test_sync_commands(mock_notion_cls, orchestrator, monkeypatch):
    user_id = "00000000-0000-0000-0000-000000000000"
    
    mock_query_service = create_mock_query_service("notion_manage")
    monkeypatch.setattr("src.services.ai_orchestrator.QueryService", mock_query_service)
    
    mock_send_message = AsyncMock()
    class MockTelegramService:
        send_message = mock_send_message
    monkeypatch.setattr("src.services.ai_orchestrator.TelegramService", MockTelegramService)
    monkeypatch.setattr(orchestrator, "_get_user_family_id", lambda x: UUID("11111111-1111-1111-1111-111111111111"))
    
    mock_session = MagicMock()
    mock_session_class = MagicMock()
    mock_session_class.return_value.__enter__.return_value = mock_session
    monkeypatch.setattr("src.services.ai_orchestrator.Session", mock_session_class)
    
    mock_notion = mock_notion_cls.return_value
    mock_notion.get_family_notion_status.return_value = {"is_connected": True}
    mock_notion.test_connection_mirror = AsyncMock(return_value={"database_name": "My DB", "page_url": "http://notion"})
    
    await orchestrator.orchestrate(user_id=user_id, text="/notion test", audio_file_id=None, chat_id=12345)
    assert "Test Successful" in mock_send_message.call_args[1]["text"]

    mock_notion.sync_pending_transactions = AsyncMock(return_value={"status": "completed", "synced": 2, "failed": 0, "total_pending": 2})
    await orchestrator.orchestrate(user_id=user_id, text="/notion sync", audio_file_id=None, chat_id=12345)
    assert "Successfully synchronized" in mock_send_message.call_args[1]["text"]
    assert "2" in mock_send_message.call_args[1]["text"]

    mock_notion.sync_pending_transactions = AsyncMock(return_value={"status": "completed", "synced": 0, "failed": 0, "total_pending": 0})
    await orchestrator.orchestrate(user_id=user_id, text="/notion sync", audio_file_id=None, chat_id=12345)
    assert "Up to Date" in mock_send_message.call_args[1]["text"]

    mock_notion.sync_pending_transactions = AsyncMock(return_value={"status": "completed", "synced": 0, "failed": 1, "total_pending": 1})
    await orchestrator.orchestrate(user_id=user_id, text="/notion sync", audio_file_id=None, chat_id=12345)
    assert "Sync Failed" in mock_send_message.call_args[1]["text"]
