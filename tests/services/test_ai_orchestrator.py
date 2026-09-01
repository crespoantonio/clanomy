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
    mock_extract.assert_called_once_with(text="15 for Starbucks", default_currency="USD")
    
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
    mock_extract.assert_called_once_with(text="20 for taxi", default_currency="USD")
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
    
    assert mock_session.add.call_count >= 1
    added_transaction = next((call[0][0] for call in mock_session.add.call_args_list if isinstance(call[0][0], Transaction)), None)
    assert added_transaction is not None
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
    
    mock_family = MagicMock(plan_type="trial", subscription_status="active", trial_ends_at=None, notion_api_key="encrypted_key", notion_database_id="db1")
    mock_session.get.return_value = mock_family
    
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
    mock_family = MagicMock(plan_type="trial", subscription_status="active", trial_ends_at=None, notion_api_key="encrypted_key", notion_database_id="db1")
    def mock_get_1(model_cls, pk):
        if getattr(model_cls, "__name__", "") == "Family":
            return mock_family
        return mock_user
    mock_session.get.side_effect = mock_get_1

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
    mock_family = MagicMock(plan_type="trial", subscription_status="active", trial_ends_at=None, notion_api_key="encrypted_key", notion_database_id="db1")
    def mock_get_2(model_cls, pk):
        if getattr(model_cls, "__name__", "") == "Family":
            return mock_family
        return mock_user
    mock_session.get.side_effect = mock_get_2

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
    
    mock_family = MagicMock(plan_type="trial", subscription_status="active", trial_ends_at=None, notion_api_key="encrypted_key", notion_database_id="db1")
    mock_session.get.return_value = mock_family
    
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

@pytest.mark.anyio
async def test_persist_transaction_with_type(orchestrator, monkeypatch):
    user_id = "00000000-0000-0000-0000-000000000000"
    family_id = "11111111-1111-1111-1111-111111111111"
    
    mock_session = MagicMock()
    mock_session_class = MagicMock()
    mock_session_class.return_value.__enter__.return_value = mock_session
    monkeypatch.setattr("src.services.ai_orchestrator.Session", mock_session_class)
    
    mock_user = MagicMock(family_id=UUID(family_id))
    mock_session.get.return_value = mock_user

    # Test persisting income
    orchestrator._persist_transaction(
        user_uuid=UUID(user_id),
        amount="enc_3500.0 USD",
        concept="enc_Acme Corp",
        category="Salary",
        tx_type="income"
    )
    
    assert mock_session.add.call_count >= 1
    added_tx = next((call[0][0] for call in mock_session.add.call_args_list if isinstance(call[0][0], Transaction)), None)
    assert added_tx is not None
    assert added_tx.type == "income"
    assert added_tx.amount == "enc_3500.0 USD"
    assert added_tx.concept == "enc_Acme Corp"
    assert added_tx.category == "Salary"

@pytest.mark.anyio
async def test_orchestrator_income_text_success(orchestrator, monkeypatch):
    user_id = "00000000-0000-0000-0000-000000000000"
    family_id = "11111111-1111-1111-1111-111111111111"
    
    mock_extract = AsyncMock()
    mock_extract_result = MagicMock()
    mock_extract_result.type = "income"
    mock_extract_result.amount = 3500.0
    mock_extract_result.currency = "USD"
    mock_extract_result.concept = "Acme Corp"
    mock_extract_result.category = "Salary"
    mock_extract_result.transaction_date = None
    fixed_now = datetime.datetime(2026, 8, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)
    mock_extract_result.to_datetime.return_value = fixed_now
    mock_extract_result.model_dump.return_value = {
        "type": "income",
        "amount": 3500.0,
        "currency": "USD",
        "concept": "Acme Corp",
        "category": "Salary"
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

    mock_user = MagicMock(family_id=UUID(family_id), full_name="Tony", username="tony")
    mock_session.get.return_value = mock_user

    # Mock past transactions in the session for cash flow calculation ($1200 expense)
    t_exp = MagicMock(
        amount="enc_1200.0 USD",
        concept="enc_Rent",
        category="Rent/Bills",
        tx_type="expense",
        timestamp=fixed_now
    )
    t_inc = MagicMock(
        amount="enc_3500.0 USD",
        concept="enc_Acme Corp",
        category="Salary",
        tx_type="income",
        timestamp=fixed_now
    )
    # session.exec().all() returns existing + new
    mock_session.exec.return_value.all.return_value = [t_exp, t_inc]

    class MockEncryptionService:
        def encrypt(self, text): return f"enc_{text}"
        def decrypt(self, text): return text.replace("enc_", "")
    monkeypatch.setattr(orchestrator, "encryption_service", MockEncryptionService())

    await orchestrator.orchestrate(user_id=user_id, text="Got paid 3500 salary from Acme Corp", audio_file_id=None, chat_id=12345)

    # Verify message format
    mock_send_message.assert_called_once()
    msg_text = mock_send_message.call_args[1]["text"]
    assert "💰 Income Logged: +$3,500.00 USD (Salary - Acme Corp)" in msg_text
    assert "📊 August Snapshot:" in msg_text
    assert "• Total In: $3,500.00 USD" in msg_text
    assert "• Total Out: $1,200.00 USD" in msg_text
    assert "• Net Savings: +$2,300.00 USD (66%)" in msg_text or "(65%)" in msg_text

@pytest.mark.anyio
async def test_orchestrator_income_audio_success(orchestrator, monkeypatch):
    user_id = "00000000-0000-0000-0000-000000000000"
    family_id = "11111111-1111-1111-1111-111111111111"

    mock_transcribe = AsyncMock(return_value=("earned 500 freelance consulting", "en"))
    class MockWhisperService:
        transcribe = mock_transcribe
    monkeypatch.setattr("src.services.ai_orchestrator.WhisperService", MockWhisperService)

    mock_extract = AsyncMock()
    mock_extract_result = MagicMock()
    mock_extract_result.type = "income"
    mock_extract_result.amount = 500.0
    mock_extract_result.currency = "USD"
    mock_extract_result.concept = "Consulting"
    mock_extract_result.category = "Freelance"
    mock_extract_result.transaction_date = None
    mock_extract_result.to_datetime.return_value = datetime.datetime(2026, 8, 20, tzinfo=datetime.timezone.utc)
    mock_extract_result.model_dump.return_value = {"type": "income", "amount": 500.0}
    mock_extract.return_value = mock_extract_result

    class MockExtractionService:
        extract = mock_extract
    monkeypatch.setattr("src.services.ai_orchestrator.QueryService", create_mock_query_service())
    monkeypatch.setattr("src.services.ai_orchestrator.ExtractionService", MockExtractionService)

    mock_send_message = AsyncMock()
    mock_get_file = AsyncMock(return_value="https://api.telegram.org/file/bot123/voice.ogg")
    class MockTelegramService:
        send_message = mock_send_message
        get_file_url = mock_get_file
    monkeypatch.setattr("src.services.ai_orchestrator.TelegramService", MockTelegramService)

    mock_session = MagicMock()
    mock_session_class = MagicMock()
    mock_session_class.return_value.__enter__.return_value = mock_session
    monkeypatch.setattr("src.services.ai_orchestrator.Session", mock_session_class)

    mock_user = MagicMock(family_id=UUID(family_id))
    mock_session.get.return_value = mock_user
    mock_session.exec.return_value.all.return_value = []

    class MockEncryptionService:
        def encrypt(self, text): return f"enc_{text}"
        def decrypt(self, text): return text.replace("enc_", "")
    monkeypatch.setattr(orchestrator, "encryption_service", MockEncryptionService())

    await orchestrator.orchestrate(user_id=user_id, text=None, audio_file_id="audio_income_123", chat_id=12345)

    mock_transcribe.assert_called_once()
    mock_extract.assert_called_once_with(text="earned 500 freelance consulting", default_currency="USD")
    mock_send_message.assert_called_once()
    assert "💰 Income Logged: +$500.00 USD" in mock_send_message.call_args[1]["text"]

@pytest.mark.anyio
async def test_orchestrator_income_retroactive(orchestrator, monkeypatch):
    user_id = "00000000-0000-0000-0000-000000000000"
    family_id = "11111111-1111-1111-1111-111111111111"

    mock_extract = AsyncMock()
    mock_extract_result = MagicMock()
    mock_extract_result.type = "income"
    mock_extract_result.amount = 2000.0
    mock_extract_result.currency = "USD"
    mock_extract_result.concept = "Acme Corp"
    mock_extract_result.category = "Salary"
    mock_extract_result.transaction_date = "2026-08-10"
    mock_extract_result.to_datetime.return_value = datetime.datetime(2026, 8, 10, 12, 0, 0, tzinfo=datetime.timezone.utc)
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

    mock_user = MagicMock(family_id=UUID(family_id))
    mock_session.get.return_value = mock_user
    mock_session.exec.return_value.all.return_value = []

    class MockEncryptionService:
        def encrypt(self, text): return f"enc_{text}"
        def decrypt(self, text): return text.replace("enc_", "")
    monkeypatch.setattr(orchestrator, "encryption_service", MockEncryptionService())

    await orchestrator.orchestrate(user_id=user_id, text="last week 2000 salary from Acme Corp", audio_file_id=None, chat_id=12345)

    mock_send_message.assert_called_once()
    msg = mock_send_message.call_args[1]["text"]
    assert "💰 Income Logged: +$2,000.00 USD (Salary - Acme Corp) (logged for Aug 10, 2026)" in msg
    assert "📊 August Snapshot:" in msg

@pytest.mark.anyio
async def test_orchestrator_income_concept_equals_category(orchestrator, monkeypatch):
    user_id = "00000000-0000-0000-0000-000000000000"
    family_id = "11111111-1111-1111-1111-111111111111"

    mock_extract = AsyncMock()
    mock_extract_result = MagicMock()
    mock_extract_result.type = "income"
    mock_extract_result.amount = 4000.0
    mock_extract_result.currency = "USD"
    mock_extract_result.concept = "Salary"
    mock_extract_result.category = "Salary"
    mock_extract_result.transaction_date = None
    mock_extract_result.to_datetime.return_value = datetime.datetime(2026, 8, 1, tzinfo=datetime.timezone.utc)
    mock_extract_result.model_dump.return_value = {"type": "income", "amount": 4000.0}
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

    mock_user = MagicMock(family_id=UUID(family_id))
    mock_session.get.return_value = mock_user
    mock_session.exec.return_value.all.return_value = []

    class MockEncryptionService:
        def encrypt(self, text): return f"enc_{text}"
        def decrypt(self, text): return text.replace("enc_", "")
    monkeypatch.setattr(orchestrator, "encryption_service", MockEncryptionService())

    await orchestrator.orchestrate(user_id=user_id, text="Salary 4000", audio_file_id=None, chat_id=12345)

    mock_send_message.assert_called_once()
    msg = mock_send_message.call_args[1]["text"]
    assert "💰 Income Logged: +$4,000.00 USD (Salary)\n" in msg

@pytest.mark.anyio
async def test_orchestrator_income_negative_net_savings(orchestrator, monkeypatch):
    user_id = "00000000-0000-0000-0000-000000000000"
    family_id = "11111111-1111-1111-1111-111111111111"
    now_dt = datetime.datetime(2026, 8, 15, tzinfo=datetime.timezone.utc)

    mock_extract = AsyncMock()
    mock_extract_result = MagicMock()
    mock_extract_result.type = "income"
    mock_extract_result.amount = 1000.0
    mock_extract_result.currency = "USD"
    mock_extract_result.concept = "Bonus"
    mock_extract_result.category = "Bonus"
    mock_extract_result.transaction_date = None
    mock_extract_result.to_datetime.return_value = now_dt
    mock_extract_result.model_dump.return_value = {"type": "income", "amount": 1000.0}
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

    mock_user = MagicMock(family_id=UUID(family_id))
    mock_session.get.return_value = mock_user

    # $1500 in expense, $1000 in income -> Net: -$500.00
    t_exp = MagicMock(amount="enc_1500.0 USD", tx_type="expense", timestamp=now_dt)
    t_inc = MagicMock(amount="enc_1000.0 USD", tx_type="income", timestamp=now_dt)
    mock_session.exec.return_value.all.return_value = [t_exp, t_inc]

    class MockEncryptionService:
        def encrypt(self, text): return f"enc_{text}"
        def decrypt(self, text): return text.replace("enc_", "")
    monkeypatch.setattr(orchestrator, "encryption_service", MockEncryptionService())

    await orchestrator.orchestrate(user_id=user_id, text="Bonus 1000", audio_file_id=None, chat_id=12345)

    mock_send_message.assert_called_once()
    msg = mock_send_message.call_args[1]["text"]
    assert "• Total In: $1,000.00 USD" in msg
    assert "• Total Out: $1,500.00 USD" in msg
    assert "• Net Savings: -$500.00 USD (-50%)" in msg

@pytest.mark.anyio
async def test_orchestrator_income_eur_currency(orchestrator, monkeypatch):
    user_id = "00000000-0000-0000-0000-000000000000"
    family_id = "11111111-1111-1111-1111-111111111111"
    now_dt = datetime.datetime(2026, 8, 15, tzinfo=datetime.timezone.utc)

    mock_extract = AsyncMock()
    mock_extract_result = MagicMock()
    mock_extract_result.type = "income"
    mock_extract_result.amount = 2500.0
    mock_extract_result.currency = "EUR"
    mock_extract_result.concept = "Acme Europe"
    mock_extract_result.category = "Salary"
    mock_extract_result.transaction_date = None
    mock_extract_result.to_datetime.return_value = now_dt
    mock_extract_result.model_dump.return_value = {"type": "income", "amount": 2500.0, "currency": "EUR"}
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

    mock_user = MagicMock(family_id=UUID(family_id))
    mock_session.get.return_value = mock_user

    # EUR expense and USD expense (USD should be ignored for EUR snapshot)
    t_exp_eur = MagicMock(amount="enc_500.0 EUR", tx_type="expense", timestamp=now_dt)
    t_exp_usd = MagicMock(amount="enc_300.0 USD", tx_type="expense", timestamp=now_dt)
    t_inc_eur = MagicMock(amount="enc_2500.0 EUR", tx_type="income", timestamp=now_dt)
    mock_session.exec.return_value.all.return_value = [t_exp_eur, t_exp_usd, t_inc_eur]

    class MockEncryptionService:
        def encrypt(self, text): return f"enc_{text}"
        def decrypt(self, text): return text.replace("enc_", "")
    monkeypatch.setattr(orchestrator, "encryption_service", MockEncryptionService())

    await orchestrator.orchestrate(user_id=user_id, text="Earned 2500 euros salary from Acme Europe", audio_file_id=None, chat_id=12345)

    mock_send_message.assert_called_once()
    msg = mock_send_message.call_args[1]["text"]
    assert "💰 Income Logged: +€2,500.00 EUR (Salary - Acme Europe)" in msg
    assert "• Total In: €2,500.00 EUR" in msg
    assert "• Total Out: €500.00 EUR" in msg
    assert "• Net Savings: +€2,000.00 EUR (80%)" in msg

@pytest.mark.anyio
async def test_orchestrator_unified_edit_last_spanish(orchestrator, monkeypatch):
    from src.services.extraction import UnifiedResult
    user_id = "00000000-0000-0000-0000-000000000000"

    mock_classify = AsyncMock()
    mock_classify.return_value = UnifiedResult(
        action="edit_last",
        new_amount=250.0
    )

    class MockExtractionService:
        classify_and_extract = mock_classify

    monkeypatch.setattr("src.services.ai_orchestrator.ExtractionService", MockExtractionService)

    mock_correction = MagicMock(return_value="✏️ Updated latest transaction:\n• 💸 -$250.00 ARS")
    monkeypatch.setattr(orchestrator, "_handle_transaction_correction", mock_correction)

    mock_send = AsyncMock()
    class MockTelegramService:
        send_message = mock_send
    monkeypatch.setattr("src.services.ai_orchestrator.TelegramService", MockTelegramService)

    # Mock family currency fetch
    monkeypatch.setattr(orchestrator, "_get_user_family_id", MagicMock(return_value=UUID(user_id)))
    class MockFamilyService:
        def get_family_default_currency(self, fid): return "ARS"
    monkeypatch.setattr("src.services.ai_orchestrator.FamilyService", MockFamilyService)

    await orchestrator.orchestrate(
        user_id=user_id,
        text="El último importe necesito actualizarlo a 250",
        audio_file_id=None,
        chat_id=12345
    )

    mock_classify.assert_called_once()
    mock_correction.assert_called_once()
    assert mock_correction.call_args[0][1].new_amount == 250.0
    mock_send.assert_called_once()
    assert "Updated latest transaction" in mock_send.call_args[1]["text"]

@pytest.mark.anyio
async def test_orchestrator_unified_undo_last_spanish(orchestrator, monkeypatch):
    from src.services.extraction import UnifiedResult
    user_id = "00000000-0000-0000-0000-000000000000"

    mock_classify = AsyncMock()
    mock_classify.return_value = UnifiedResult(
        action="undo_last"
    )

    class MockExtractionService:
        classify_and_extract = mock_classify

    monkeypatch.setattr("src.services.ai_orchestrator.ExtractionService", MockExtractionService)

    mock_undo = MagicMock(return_value="🗑️ Removed latest transaction")
    monkeypatch.setattr(orchestrator, "_handle_transaction_undo", mock_undo)

    mock_send = AsyncMock()
    class MockTelegramService:
        send_message = mock_send
    monkeypatch.setattr("src.services.ai_orchestrator.TelegramService", MockTelegramService)

    monkeypatch.setattr(orchestrator, "_get_user_family_id", MagicMock(return_value=UUID(user_id)))
    class MockFamilyService:
        def get_family_default_currency(self, fid): return "ARS"
    monkeypatch.setattr("src.services.ai_orchestrator.FamilyService", MockFamilyService)

    await orchestrator.orchestrate(
        user_id=user_id,
        text="Elimina esos ultimos 250",
        audio_file_id=None,
        chat_id=12345
    )

    mock_classify.assert_called_once()
    mock_undo.assert_called_once()
    mock_send.assert_called_once()
    assert "Removed latest transaction" in mock_send.call_args[1]["text"]



