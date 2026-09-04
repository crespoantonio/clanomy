import pytest

def test_webhook_invalid_secret(app_client, telegram_payload_factory):
    """[P0] Webhook should reject requests with invalid secret token."""
    payload = telegram_payload_factory(text="/start")
    response = app_client.post(
        "/api/v1/telegram/webhook",
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"}
    )
    assert response.status_code == 403
    assert response.json() == {"detail": "Invalid secret token"}

def test_webhook_success_registration(app_client, mock_telegram, telegram_payload_factory):
    """[P0] Webhook should register a new user on /start command."""
    payload = telegram_payload_factory(text="/start", user_id=999, first_name="Bruce")
    
    response = app_client.post(
        "/api/v1/telegram/webhook",
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    
    # Verify the welcome message was sent
    assert len(mock_telegram.messages) == 1
    welcome = mock_telegram.messages[0]["text"]
    assert "Welcome to Clanomy" in welcome
    assert "60-Day Duo Pro Trial" in welcome
    assert "Send a voice note" in welcome
    assert "Type an expense" in welcome
    assert "Type an income" in welcome
    assert "Ask a question" in welcome

def test_webhook_log_text_expense(app_client, mock_telegram, telegram_payload_factory):
    """[P0] Webhook should process text expense and extract via LLM."""
    # First register the user
    app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/start", user_id=888),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    mock_telegram.messages.clear()
    
    # Log an expense
    payload = telegram_payload_factory(text="Spent 25.50 on dinner at McDonald's", user_id=888)
    
    response = app_client.post(
        "/api/v1/telegram/webhook",
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    
    assert len(mock_telegram.messages) > 0
    response_text = mock_telegram.messages[-1]["text"]
    assert "25.5" in response_text
    # We expect 'dinner' or 'McDonald' to be in the concept
    assert "dinner" in response_text.lower() or "mcdonald" in response_text.lower()

def test_webhook_zero_spending_fallback(app_client, mock_telegram, telegram_payload_factory):
    """[P3] Webhook should handle queries with zero spending gracefully."""
    app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/start", user_id=777),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    mock_telegram.messages.clear()
    
    payload = telegram_payload_factory(text="How much did I spend yesterday?", user_id=777)
    
    response = app_client.post(
        "/api/v1/telegram/webhook",
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    
    assert response.status_code == 200
    assert len(mock_telegram.messages) > 0
    response_text = mock_telegram.messages[-1]["text"]
    assert "0.00" in response_text or "haven't logged any expenses" in response_text.lower() or "zero" in response_text.lower()

def test_webhook_log_text_income(app_client, mock_telegram, telegram_payload_factory):
    """[P0] Webhook should process text income and reply with income badge & cash flow snapshot."""
    # First register the user
    app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/start", user_id=666),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    mock_telegram.messages.clear()
    
    # Log an income
    payload = telegram_payload_factory(text="Got paid 3500 salary from Acme Corp", user_id=666)
    
    response = app_client.post(
        "/api/v1/telegram/webhook",
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    
    assert len(mock_telegram.messages) > 0
    response_text = mock_telegram.messages[-1]["text"]
    assert "💰 Income Logged:" in response_text
    assert "3,500.00" in response_text
    assert "Salary" in response_text
    assert "Snapshot:" in response_text
    assert "Total In:" in response_text
    assert "Net Savings:" in response_text

def test_webhook_upgrade_command_general(app_client, mock_telegram, telegram_payload_factory):
    """[P0] Webhook should handle /upgrade and dispatch tier explanation and both invoices."""
    # Register user
    app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/start", user_id=4441),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    mock_telegram.messages.clear()

    # Trigger /upgrade
    payload = telegram_payload_factory(text="/upgrade", user_id=4441)
    response = app_client.post(
        "/api/v1/telegram/webhook",
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    # Verify intro message with interactive checkout buttons
    assert len(mock_telegram.messages) == 1
    intro = mock_telegram.messages[0]["text"]
    assert "Upgrade to Clanomy Pro" in intro
    assert "Solo Pro ($4.99 / month)" in intro
    assert "Duo Pro ($7.99 / month)" in intro
    assert "Family Pro ($11.99 / month)" in intro

    reply_markup = mock_telegram.messages[0].get("reply_markup")
    assert reply_markup is not None
    buttons = reply_markup["inline_keyboard"]
    assert len(buttons) == 3
    assert "Solo Pro" in buttons[0][0]["text"]
    assert "Duo Pro" in buttons[1][0]["text"]
    assert "Family Pro" in buttons[2][0]["text"]

def test_webhook_upgrade_command_solo_tier(app_client, mock_telegram, telegram_payload_factory, monkeypatch):
    """[P1] Webhook should handle '/upgrade solo' and dispatch Solo Pro checkout button directly."""
    from src.core.config import settings
    monkeypatch.setattr(settings, "ENABLE_SUBSCRIPTIONS", True)

    app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/start", user_id=4442),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    mock_telegram.messages.clear()

    payload = telegram_payload_factory(text="/upgrade solo", user_id=4442)
    response = app_client.post(
        "/api/v1/telegram/webhook",
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert response.status_code == 200
    assert len(mock_telegram.messages) == 1
    msg = mock_telegram.messages[0]
    assert "Solo Pro" in msg["text"]
    assert msg.get("reply_markup") is not None
    assert "Solo Pro" in msg["reply_markup"]["inline_keyboard"][0][0]["text"]

def test_webhook_upgrade_command_family_tier(app_client, mock_telegram, telegram_payload_factory, monkeypatch):
    """[P1] Webhook should handle '/upgrade family' and dispatch Family Pro checkout button directly."""
    from src.core.config import settings
    monkeypatch.setattr(settings, "ENABLE_SUBSCRIPTIONS", True)

    app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/start", user_id=4443),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    mock_telegram.messages.clear()

    payload = telegram_payload_factory(text="/upgrade family", user_id=4443)
    response = app_client.post(
        "/api/v1/telegram/webhook",
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert response.status_code == 200
    assert len(mock_telegram.messages) == 1
    msg = mock_telegram.messages[0]
    assert "Family Pro" in msg["text"]
    assert msg.get("reply_markup") is not None
    assert "Family Pro" in msg["reply_markup"]["inline_keyboard"][0][0]["text"]

def test_webhook_solo_pro_invite_blocked(app_client, mock_telegram, telegram_payload_factory):
    """[P0] If a Solo Pro subscriber attempts /invite, inform them Family Pro is required."""
    from src.db.session import engine
    from sqlmodel import Session, select
    from src.db.models import Family, User

    user_id = 4444
    app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/start", user_id=user_id),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )

    # Set workspace plan to solo_pro
    with Session(engine) as session:
        user = session.exec(select(User).where(User.telegram_id == user_id)).first()
        family = session.get(Family, user.family_id)
        family.plan_type = "solo_pro"
        session.add(family)
        session.commit()

    mock_telegram.messages.clear()

    # Attempt to invite
    payload = telegram_payload_factory(text="/invite", user_id=user_id)
    response = app_client.post(
        "/api/v1/telegram/webhook",
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert response.status_code == 200
    assert len(mock_telegram.messages) > 0
    resp_text = mock_telegram.messages[-1]["text"]
    assert "Solo Pro" in resp_text
    assert "Family Pro" in resp_text
    assert "/upgrade" in resp_text

def test_webhook_upgrade_command_saas(app_client, mock_telegram, telegram_payload_factory, monkeypatch):
    """[P0] /upgrade command returns interactive tier buttons with Lemon Squeezy checkout URLs."""
    from src.core.config import settings
    monkeypatch.setattr(settings, "ENABLE_SUBSCRIPTIONS", True)

    payload = telegram_payload_factory(
        text="/upgrade",
        user_id=9001
    )
    response = app_client.post(
        "/api/v1/telegram/webhook",
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert response.status_code == 200
    assert len(mock_telegram.messages) == 1
    msg = mock_telegram.messages[0]
    assert "Solo Pro" in msg["text"]
    assert "Duo Pro" in msg["text"]
    assert "Family Pro" in msg["text"]
    assert msg.get("reply_markup") is not None
    assert "inline_keyboard" in msg["reply_markup"]

def test_webhook_tier_command_alias(app_client, mock_telegram, telegram_payload_factory, monkeypatch):
    """[P0] /tier and /plan commands alias to upgrade menu with 3 tier buttons."""
    from src.core.config import settings
    monkeypatch.setattr(settings, "ENABLE_SUBSCRIPTIONS", True)

    payload = telegram_payload_factory(
        text="/tier",
        user_id=9002
    )
    response = app_client.post(
        "/api/v1/telegram/webhook",
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert response.status_code == 200
    assert len(mock_telegram.messages) == 1
    msg = mock_telegram.messages[0]
    assert "Duo Pro" in msg["text"]
    buttons = msg["reply_markup"]["inline_keyboard"]
    assert len(buttons) == 3
    assert "Solo Pro" in buttons[0][0]["text"]
    assert "Duo Pro" in buttons[1][0]["text"]
    assert "Family Pro" in buttons[2][0]["text"]

def test_webhook_billing_command(app_client, mock_telegram, telegram_payload_factory, monkeypatch):
    """[P0] /billing command returns customer portal link when configured."""
    from src.core.config import settings
    from src.db.session import engine
    from sqlmodel import Session, select
    from src.db.models import Family, User

    monkeypatch.setattr(settings, "ENABLE_SUBSCRIPTIONS", True)
    user_id = 9005

    # First register user
    app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/start", user_id=user_id),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    mock_telegram.messages.clear()

    # Attach portal URL
    with Session(engine) as session:
        user = session.exec(select(User).where(User.telegram_id == user_id)).first()
        family = session.get(Family, user.family_id)
        family.customer_portal_url = "https://billing.example.com/portal/test-cust-9005"
        session.add(family)
        session.commit()

    # Send /billing command
    payload = telegram_payload_factory(text="/billing", user_id=user_id)
    response = app_client.post(
        "/api/v1/telegram/webhook",
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert response.status_code == 200
    assert len(mock_telegram.messages) == 1
    msg = mock_telegram.messages[0]
    assert "Manage Your Subscription" in msg["text"]
    assert msg["reply_markup"]["inline_keyboard"][0][0]["url"] == "https://billing.example.com/portal/test-cust-9005"


def test_webhook_lifecycle_renewal(app_client):
    """[P0] Webhook processes renewal and extends current_period_end."""
    from src.db.session import engine
    from sqlmodel import Session
    from src.db.models import Family
    from datetime import datetime, timezone, timedelta
    
    with Session(engine) as session:
        family = Family(name="Test Renewal", plan_type="solo_pro", subscription_status="active", max_members=1)
        family.current_period_end = datetime.now(timezone.utc) + timedelta(days=5)
        session.add(family)
        session.commit()
        session.refresh(family)
        fam_id = str(family.id)
        old_end = family.current_period_end
        
    payload = {"family_id": fam_id, "charge_id": "charge_ren_123"}
    response = app_client.post(
        "/api/v1/telegram/webhook/renewal",
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert response.status_code == 200
    
    with Session(engine) as session:
        family = session.get(Family, family.id)
        assert family.subscription_status == "active"
        assert family.telegram_payment_charge_id == "charge_ren_123"
        assert family.current_period_end > old_end

def test_webhook_lifecycle_cancellation(app_client):
    """[P0] Webhook processes cancellation and sets subscription_status to cancelled."""
    from src.db.session import engine
    from sqlmodel import Session
    from src.db.models import Family
    
    with Session(engine) as session:
        family = Family(name="Test Cancel", plan_type="family_pro", subscription_status="active", max_members=5)
        session.add(family)
        session.commit()
        session.refresh(family)
        fam_id = str(family.id)
        
    payload = {"family_id": fam_id}
    response = app_client.post(
        "/api/v1/telegram/webhook/cancellation",
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert response.status_code == 200
    
    with Session(engine) as session:
        family = session.get(Family, family.id)
        assert family.subscription_status == "cancelled"

def test_webhook_lifecycle_failure(app_client, mock_telegram, telegram_payload_factory):
    """[P0] Webhook processes failure, transitions to free, and notifies admin."""
    from src.db.session import engine
    from sqlmodel import Session
    from src.db.models import Family, User
    
    admin_id = 9501
    app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/start", user_id=admin_id),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    mock_telegram.messages.clear()
    
    with Session(engine) as session:
        from sqlmodel import select
        user = session.exec(select(User).where(User.telegram_id == admin_id)).first()
        family = session.get(Family, user.family_id)
        family.plan_type = "solo_pro"
        family.subscription_status = "active"
        session.add(family)
        session.commit()
        fam_id = str(family.id)

    payload = {"family_id": fam_id}
    response = app_client.post(
        "/api/v1/telegram/webhook/failure",
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert response.status_code == 200
    
    with Session(engine) as session:
        family = session.get(Family, family.id)
        assert family.plan_type == "free"
        assert family.subscription_status == "expired"
        
    assert len(mock_telegram.messages) == 1
    failure_msg = mock_telegram.messages[0]["text"]
    assert "Subscription Expired/Failed" in failure_msg
    assert "Free tier" in failure_msg

def test_webhook_rejects_unsupported_media(app_client, mock_telegram, telegram_payload_factory):
    """[P0] Webhook rejects unsupported media (photo, doc, audio, video) before any AI processing."""
    app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/start", user_id=9801),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    mock_telegram.messages.clear()

    # Send a document attachment
    doc_payload = telegram_payload_factory(user_id=9801)
    doc_payload["message"]["document"] = {"file_id": "doc_123", "file_name": "receipt.pdf"}

    response = app_client.post(
        "/api/v1/telegram/webhook",
        json=doc_payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert len(mock_telegram.messages) == 1
    assert "Unsupported Format" in mock_telegram.messages[0]["text"]

    mock_telegram.messages.clear()

    # Send a photo attachment
    photo_payload = telegram_payload_factory(user_id=9801)
    photo_payload["message"]["photo"] = [{"file_id": "photo_123"}]

    response = app_client.post(
        "/api/v1/telegram/webhook",
        json=photo_payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert response.status_code == 200
    assert len(mock_telegram.messages) == 1
    assert "Unsupported Format" in mock_telegram.messages[0]["text"]

def test_webhook_rejects_excessive_text_length(app_client, mock_telegram, telegram_payload_factory):
    """[P0] Webhook fast-fails when text length exceeds MAX_TEXT_LENGTH before Ollama inference."""
    app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/start", user_id=9802),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    mock_telegram.messages.clear()

    long_text = "Spent 50 dollars on groceries " * 20  # 600 characters > 350 limit
    payload = telegram_payload_factory(text=long_text, user_id=9802)

    response = app_client.post(
        "/api/v1/telegram/webhook",
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert response.status_code == 200
    assert len(mock_telegram.messages) == 1
    alert_msg = mock_telegram.messages[0]["text"]
    assert "Message Too Long" in alert_msg
    assert "350 characters" in alert_msg

def test_webhook_rejects_excessive_voice_duration(app_client, mock_telegram, telegram_payload_factory):
    """[P0] Webhook fast-fails when voice duration exceeds MAX_VOICE_DURATION_SECONDS before Whisper download."""
    app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/start", user_id=9803),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    mock_telegram.messages.clear()

    voice_payload = telegram_payload_factory(user_id=9803)
    voice_payload["message"]["voice"] = {
        "file_id": "long_voice_file_id",
        "duration": 120,  # 120s > 60s limit
        "mime_type": "audio/ogg"
    }

    response = app_client.post(
        "/api/v1/telegram/webhook",
        json=voice_payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert response.status_code == 200
    assert len(mock_telegram.messages) == 1
    alert_msg = mock_telegram.messages[0]["text"]
    assert "Voice Note Too Long" in alert_msg
    assert "60 seconds" in alert_msg

def test_webhook_rejects_excessive_voice_file_size(app_client, mock_telegram, telegram_payload_factory):
    """[P0] Webhook fast-fails when voice file size exceeds MAX_AUDIO_SIZE_BYTES before download."""
    app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/start", user_id=9804),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    mock_telegram.messages.clear()

    voice_payload = telegram_payload_factory(user_id=9804)
    voice_payload["message"]["voice"] = {
        "file_id": "huge_voice_file_id",
        "duration": 30,  # 30s is under 60s limit
        "file_size": 4 * 1024 * 1024,  # 4 MB > 3 MB limit
        "mime_type": "audio/ogg"
    }

    response = app_client.post(
        "/api/v1/telegram/webhook",
        json=voice_payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert response.status_code == 200
    assert len(mock_telegram.messages) == 1
    alert_msg = mock_telegram.messages[0]["text"]
    assert "Voice File Too Large" in alert_msg
    assert "3.0 MB" in alert_msg


def test_webhook_currency_command_get_and_set(app_client, mock_telegram, telegram_payload_factory):

    """[P1] Webhook processes /currency to view and /currency ARS to update default currency."""
    app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/start", user_id=9805),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    mock_telegram.messages.clear()

    # 1. Check current currency
    payload_get = telegram_payload_factory(text="/currency", user_id=9805)
    resp = app_client.post(
        "/api/v1/telegram/webhook",
        json=payload_get,
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert resp.status_code == 200
    assert len(mock_telegram.messages) == 1
    assert "Household Default Currency" in mock_telegram.messages[0]["text"]
    assert "USD" in mock_telegram.messages[0]["text"]
    mock_telegram.messages.clear()

    # 2. Update currency to ARS
    payload_set = telegram_payload_factory(text="/currency ARS", user_id=9805)
    resp = app_client.post(
        "/api/v1/telegram/webhook",
        json=payload_set,
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert resp.status_code == 200
    assert len(mock_telegram.messages) == 1
    assert "Default Currency Updated to ARS" in mock_telegram.messages[0]["text"]
    mock_telegram.messages.clear()

    # 3. Check currency again
    resp = app_client.post(
        "/api/v1/telegram/webhook",
        json=payload_get,
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert resp.status_code == 200
    assert "ARS" in mock_telegram.messages[0]["text"]


def test_webhook_timezone_commands_and_location(app_client, mock_telegram, telegram_payload_factory):
    """Test /timezone slash command and location pin automatic calibration."""
    # 1. Register user
    app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/start", user_id=9820),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    mock_telegram.messages.clear()

    # 2. Check current timezone
    resp = app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/timezone", user_id=9820),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert resp.status_code == 200
    assert len(mock_telegram.messages) == 1
    assert "Timezone Settings" in mock_telegram.messages[0]["text"]
    mock_telegram.messages.clear()

    # 3. Update timezone via text
    resp = app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/timezone Madrid", user_id=9820),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert resp.status_code == 200
    assert len(mock_telegram.messages) == 1
    assert "Personal Timezone Updated!" in mock_telegram.messages[0]["text"]
    assert "Europe/Madrid" in mock_telegram.messages[0]["text"]
    mock_telegram.messages.clear()

    # 4. Update timezone via location pin (Buenos Aires coords)
    location_payload = {
        "update_id": 982001,
        "message": {
            "message_id": 501,
            "date": 1725235200,
            "chat": {"id": 9820, "type": "private"},
            "from": {"id": 9820, "is_bot": False, "first_name": "Tony"},
            "location": {"latitude": -34.6037, "longitude": -58.3816}
        }
    }
    resp = app_client.post(
        "/api/v1/telegram/webhook",
        json=location_payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert resp.status_code == 200
    assert len(mock_telegram.messages) == 1
    assert "Location Detected & Calibrated!" in mock_telegram.messages[0]["text"]
    assert "America/Argentina/Buenos_Aires" in mock_telegram.messages[0]["text"]






