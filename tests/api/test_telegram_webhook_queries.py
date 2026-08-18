import pytest

def test_webhook_time_based_query(app_client, mock_telegram, telegram_payload_factory):
    """[P1] Webhook should handle time-based aggregation queries."""
    user_id = 666
    app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/start", user_id=user_id),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    
    # Log some expenses
    app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="10 for coffee", user_id=user_id),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    
    mock_telegram.messages.clear()
    
    # Query
    response = app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="How much did I spend this week?", user_id=user_id),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    
    assert response.status_code == 200
    assert len(mock_telegram.messages) > 0
    response_text = mock_telegram.messages[-1]["text"].lower()
    assert "10.00" in response_text or "10" in response_text

def test_webhook_category_filtered_query(app_client, mock_telegram, telegram_payload_factory):
    """[P1] Webhook should handle category-filtered queries."""
    user_id = 555
    app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/start", user_id=user_id),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    
    # Log specific expense
    app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="Spent 45 on groceries at Walmart", user_id=user_id),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    mock_telegram.messages.clear()
    
    # Query by category
    response = app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="What have I spent on groceries this month?", user_id=user_id),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    
    assert response.status_code == 200
    assert len(mock_telegram.messages) > 0
    response_text = mock_telegram.messages[-1]["text"].lower()
    assert "45" in response_text

def test_webhook_period_comparison_query(app_client, mock_telegram, telegram_payload_factory):
    """[P1] Webhook should handle period-over-period comparison queries."""
    user_id = 444
    app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/start", user_id=user_id),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    mock_telegram.messages.clear()
    
    # Query comparison (even with 0 it should respond with comparison logic)
    response = app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="Compare my spending this week to last week", user_id=user_id),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    
    assert response.status_code == 200
    assert len(mock_telegram.messages) > 0
    response_text = mock_telegram.messages[-1]["text"].lower()
    # It should mention "week" or "less than" or "more than" or amounts
    assert "week" in response_text
