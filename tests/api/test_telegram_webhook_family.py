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


def test_webhook_family_info_command(app_client, mock_telegram, telegram_payload_factory):
    """Webhook should handle /family command and return member list with admin badge."""
    user_id = 9101
    app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/start", user_id=user_id, username="admin_9101"),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    mock_telegram.messages.clear()

    response = app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/family", user_id=user_id),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert response.status_code == 200
    assert len(mock_telegram.messages) > 0
    text = mock_telegram.messages[-1]["text"]
    assert "Family Workspace" in text
    assert "Admin" in text


def test_webhook_remove_member_and_leave_family(app_client, mock_telegram, telegram_payload_factory):
    """Webhook should allow admin to remove members and members to leave."""
    admin_id = 9201
    app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/start", user_id=admin_id, username="admin_9201"),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    # Generate invite
    app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/invite", user_id=admin_id),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    import re
    match = re.search(r'start=(join_[a-zA-Z0-9_-]+)', mock_telegram.messages[-1]["text"])
    join_token = match.group(1)

    # Member joins
    member_id = 9202
    app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text=f"/start {join_token}", user_id=member_id, username="member_9202"),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    mock_telegram.messages.clear()

    # Admin removes member
    response = app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/removemember @member_9202", user_id=admin_id),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert response.status_code == 200
    assert len(mock_telegram.messages) > 0
    assert any("Removed @member_9202" in m["text"] for m in mock_telegram.messages)

    # Member leaves family when back in personal
    mock_telegram.messages.clear()
    response = app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/leavefamily", user_id=member_id),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert response.status_code == 200
    assert "already in your own personal workspace" in mock_telegram.messages[-1]["text"].lower()


def test_webhook_quota_limit_admin(app_client, mock_telegram, telegram_payload_factory):
    """Webhook should reject logging on free tier when monthly limit reached for admin."""
    from src.db.session import engine
    from sqlmodel import Session, select
    from src.db.models import Family, User
    
    admin_id = 9301
    app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/start", user_id=admin_id, username="admin_9301"),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )

    # Manually set plan to free with count = 30
    with Session(engine) as session:
        user = session.exec(select(User).where(User.telegram_id == admin_id)).first()
        family = session.get(Family, user.family_id)
        family.plan_type = "free"
        family.monthly_tx_count = 30
        from datetime import datetime, timezone
        family.last_reset_month = datetime.now(timezone.utc).strftime("%Y-%m")
        session.add(family)
        session.commit()

    mock_telegram.messages.clear()

    # Try logging transaction
    response = app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="Spent 15 on lunch", user_id=admin_id),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert response.status_code == 200
    assert len(mock_telegram.messages) == 1
    assert "Monthly Free Limit Reached" in mock_telegram.messages[0]["text"]
    assert "Type /upgrade" in mock_telegram.messages[0]["text"]


def test_webhook_quota_limit_member(app_client, mock_telegram, telegram_payload_factory):
    """Webhook should advise invited member to ask admin to upgrade when limit reached."""
    from src.db.session import engine
    from sqlmodel import Session, select
    from src.db.models import Family, User
    
    admin_id = 9401
    app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/start", user_id=admin_id, username="admin_9401"),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/invite", user_id=admin_id),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    import re
    match = re.search(r'start=(join_[a-zA-Z0-9_-]+)', mock_telegram.messages[-1]["text"])
    join_token = match.group(1)

    member_id = 9402
    app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text=f"/start {join_token}", user_id=member_id, username="member_9402"),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )

    # Set family to free and count = 30
    with Session(engine) as session:
        user = session.exec(select(User).where(User.telegram_id == member_id)).first()
        family = session.get(Family, user.family_id)
        family.plan_type = "free"
        family.monthly_tx_count = 30
        from datetime import datetime, timezone
        family.last_reset_month = datetime.now(timezone.utc).strftime("%Y-%m")
        session.add(family)
        session.commit()

    mock_telegram.messages.clear()

    # Member tries to log transaction
    response = app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="Spent 20 on coffee", user_id=member_id),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert response.status_code == 200
    assert len(mock_telegram.messages) == 1
    assert "Monthly Free Limit Reached" in mock_telegram.messages[0]["text"]
    assert "ask your family admin" in mock_telegram.messages[0]["text"]

