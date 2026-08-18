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
    assert "Welcome to FamFin-AI" in mock_telegram.messages[0]["text"]

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
