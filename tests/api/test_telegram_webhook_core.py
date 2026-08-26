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
    assert "60-Day Family Pro Trial" in welcome
    assert "Voice & Text Logging" in welcome
    assert "Dual Income & Expense Tracking" in welcome
    assert "Ask AI & Cash Flow Queries" in welcome
    assert "Notion Mirroring" in welcome
    assert "Family Sharing" in welcome

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

    # Verify intro message + both invoices
    assert len(mock_telegram.messages) == 3
    intro = mock_telegram.messages[0]["text"]
    assert "Upgrade to Clanomy Pro" in intro
    assert "Solo Pro (150 Stars / month)" in intro
    assert "Family Pro (300 Stars / month)" in intro

    invoices = [m for m in mock_telegram.messages if m.get("type") == "invoice"]
    assert len(invoices) == 2
    plans = {inv["plan_type"] for inv in invoices}
    assert plans == {"solo_pro", "family_pro"}
    for inv in invoices:
        assert inv["payload"].startswith(f"sub_{inv['plan_type']}_")

def test_webhook_upgrade_command_solo_tier(app_client, mock_telegram, telegram_payload_factory):
    """[P1] Webhook should handle '/upgrade solo' and dispatch Solo Pro invoice directly."""
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
    assert mock_telegram.messages[0].get("type") == "invoice"
    assert mock_telegram.messages[0]["plan_type"] == "solo_pro"
    assert mock_telegram.messages[0]["payload"].startswith("sub_solo_pro_")

def test_webhook_upgrade_command_family_tier(app_client, mock_telegram, telegram_payload_factory):
    """[P1] Webhook should handle '/upgrade family' and dispatch Family Pro invoice directly."""
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
    assert mock_telegram.messages[0].get("type") == "invoice"
    assert mock_telegram.messages[0]["plan_type"] == "family_pro"
    assert mock_telegram.messages[0]["payload"].startswith("sub_family_pro_")

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


