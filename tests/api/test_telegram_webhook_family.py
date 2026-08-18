import pytest
from sqlmodel import select
from src.db.models import User, Transaction
from src.db.session import get_session

def test_webhook_create_family(app_client, mock_telegram, telegram_payload_factory):
    """[P1] Webhook should handle family group creation and return invite link."""
    user_id = 333
    app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/start", user_id=user_id),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    mock_telegram.messages.clear()
    
    response = app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/createfamily", user_id=user_id),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    
    assert response.status_code == 200
    assert len(mock_telegram.messages) > 0
    response_text = mock_telegram.messages[-1]["text"]
    assert "has been created" in response_text

def test_webhook_join_family(app_client, mock_telegram, telegram_payload_factory):
    """[P1] Webhook should allow users to join a family via invite link."""
    user1_id = 111
    app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/start", user_id=user1_id),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    
    # User 1 creates family
    app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/createfamily", user_id=user1_id),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )

    # User 1 generates invite
    app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/invite", user_id=user1_id),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    
    # Extract token
    response_text = mock_telegram.messages[-1]["text"]
    import re
    match = re.search(r'start=(join_[a-zA-Z0-9_-]+)', response_text)
    assert match is not None
    join_token = match.group(1)
    
    mock_telegram.messages.clear()
    
    # User 2 joins
    user2_id = 222
    response = app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text=f"/start {join_token}", user_id=user2_id, first_name="User2"),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    
    assert response.status_code == 200
    assert len(mock_telegram.messages) > 0
    join_response = mock_telegram.messages[-1]["text"]
    # Check if we get a welcome to the family message
    assert "family" in join_response.lower()

def test_webhook_export_data(app_client, mock_telegram, telegram_payload_factory):
    """[P1] Webhook should handle data export requests."""
    user_id = 898
    app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/start", user_id=user_id),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    mock_telegram.messages.clear()
    
    response = app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="export my data to csv", user_id=user_id),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    
    assert response.status_code == 200
    # Expected to send a document
    document_messages = [msg for msg in mock_telegram.messages if "document" in msg]
    assert len(document_messages) > 0
    assert document_messages[-1].get("file_path") is not None

def test_webhook_account_deletion(app_client, mock_telegram, telegram_payload_factory):
    """[P2] Webhook should process account deletion flow."""
    user_id = 456
    app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/start", user_id=user_id),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    mock_telegram.messages.clear()
    
    # Initiate deletion
    response = app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="delete my account", user_id=user_id),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert response.status_code == 200
    response_text = mock_telegram.messages[-1]["text"]
    assert "CONFIRM DELETE" in response_text
    
    # Confirm deletion
    mock_telegram.messages.clear()
    response = app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="CONFIRM DELETE", user_id=user_id),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert response.status_code == 200
    confirm_text = mock_telegram.messages[-1]["text"]
    assert "permanently deleted" in confirm_text.lower()
