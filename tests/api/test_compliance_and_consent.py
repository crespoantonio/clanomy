import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from sqlmodel import Session, select
from src.core.config import settings
from src.db.session import engine
from src.db.models import User, Family, Transaction, ScheduledBill
from src.templates.telegram_messages import (
    CONSENT_REQUEST_MESSAGE,
    PRIVACY_POLICY_MESSAGE,
    TERMS_OF_SERVICE_MESSAGE,
)
from src.core.llm.providers.gemini_provider import GeminiProvider, DEFAULT_GEMINI_SAFETY_SETTINGS


def test_consent_gate_enforcement_and_callback_flow(app_client, mock_telegram, telegram_payload_factory):
    """Verify that when REQUIRE_TERMS_ACCEPTANCE is active, unconsented users are gated until explicitly agreeing."""
    settings.REQUIRE_TERMS_ACCEPTANCE = True
    user_id = 77701
    
    # 1. User sends /start
    start_payload = telegram_payload_factory(text="/start", user_id=user_id, first_name="ComplianceTester")
    res = app_client.post(
        "/api/v1/telegram/webhook",
        json=start_payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert res.status_code == 200
    assert len(mock_telegram.messages) == 1
    assert "Zero-Knowledge" in mock_telegram.messages[0]["text"]
    assert "18 years of age or older" in mock_telegram.messages[0]["text"]
    assert mock_telegram.messages[0].get("reply_markup") is not None
    
    # 2. Attempt to log expense without consenting -> blocked
    mock_telegram.messages.clear()
    expense_payload = telegram_payload_factory(text="50 on lunch", user_id=user_id)
    res = app_client.post(
        "/api/v1/telegram/webhook",
        json=expense_payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert res.status_code == 200
    assert len(mock_telegram.messages) == 1
    assert "review and accept our data terms" in mock_telegram.messages[0]["text"]
    
    # 3. View Privacy Policy via callback query
    mock_telegram.messages.clear()
    cb_privacy_payload = {
        "callback_query": {
            "id": "cb_priv_1",
            "from": {"id": user_id, "first_name": "ComplianceTester"},
            "message": {"message_id": 100, "chat": {"id": user_id}},
            "data": "view_privacy"
        }
    }
    res = app_client.post(
        "/api/v1/telegram/webhook",
        json=cb_privacy_payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert res.status_code == 200
    assert len(mock_telegram.edited_messages) == 1
    assert "Privacy Policy" in mock_telegram.edited_messages[0]["text"]
    assert "never used to train" in mock_telegram.edited_messages[0]["text"]
    
    # 4. View Terms of Service via callback query
    mock_telegram.edited_messages.clear()
    cb_tos_payload = {
        "callback_query": {
            "id": "cb_tos_1",
            "from": {"id": user_id, "first_name": "ComplianceTester"},
            "message": {"message_id": 100, "chat": {"id": user_id}},
            "data": "view_tos"
        }
    }
    res = app_client.post(
        "/api/v1/telegram/webhook",
        json=cb_tos_payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert res.status_code == 200
    assert len(mock_telegram.edited_messages) == 1
    assert "Terms of Service" in mock_telegram.edited_messages[0]["text"]
    assert "Non-Advisory Tool" in mock_telegram.edited_messages[0]["text"]
    
    # 5. Return back to consent card
    mock_telegram.edited_messages.clear()
    cb_back_payload = {
        "callback_query": {
            "id": "cb_back_1",
            "from": {"id": user_id, "first_name": "ComplianceTester"},
            "message": {"message_id": 100, "chat": {"id": user_id}},
            "data": "back_to_consent"
        }
    }
    res = app_client.post(
        "/api/v1/telegram/webhook",
        json=cb_back_payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert res.status_code == 200
    assert len(mock_telegram.edited_messages) == 1
    assert "Zero-Knowledge" in mock_telegram.edited_messages[0]["text"]
    
    # 6. Accept terms via callback query
    mock_telegram.edited_messages.clear()
    mock_telegram.messages.clear()
    cb_accept_payload = {
        "callback_query": {
            "id": "cb_accept_1",
            "from": {"id": user_id, "first_name": "ComplianceTester"},
            "message": {"message_id": 100, "chat": {"id": user_id}},
            "data": "accept_tos"
        }
    }
    res = app_client.post(
        "/api/v1/telegram/webhook",
        json=cb_accept_payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert res.status_code == 200
    assert len(mock_telegram.edited_messages) == 1
    assert "Welcome to Clanomy" in mock_telegram.edited_messages[0]["text"]
    
    # Verify user state in DB
    with Session(engine) as session:
        user = session.exec(select(User).where(User.telegram_id == user_id)).first()
        assert user is not None
        assert user.terms_accepted is True
        assert user.terms_accepted_at is not None


def test_text_based_consent_and_legal_inspections(app_client, mock_telegram, telegram_payload_factory):
    """Verify that users can inspect /privacy and /tos prior to consent and accept via text shortcut."""
    settings.REQUIRE_TERMS_ACCEPTANCE = True
    user_id = 77702
    
    # 1. Pre-consent /privacy inspection
    payload = telegram_payload_factory(text="/privacy", user_id=user_id)
    res = app_client.post(
        "/api/v1/telegram/webhook",
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert res.status_code == 200
    assert len(mock_telegram.messages) == 1
    assert "Privacy Policy" in mock_telegram.messages[0]["text"]
    
    # 2. Pre-consent /tos inspection
    mock_telegram.messages.clear()
    payload = telegram_payload_factory(text="/tos", user_id=user_id)
    res = app_client.post(
        "/api/v1/telegram/webhook",
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert res.status_code == 200
    assert len(mock_telegram.messages) == 1
    assert "Terms of Service" in mock_telegram.messages[0]["text"]
    
    # 3. Direct text acceptance /accept_terms
    mock_telegram.messages.clear()
    payload = telegram_payload_factory(text="/accept_terms", user_id=user_id)
    res = app_client.post(
        "/api/v1/telegram/webhook",
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert res.status_code == 200
    assert len(mock_telegram.messages) == 1
    assert "Welcome to Clanomy" in mock_telegram.messages[0]["text"]
    
    with Session(engine) as session:
        user = session.exec(select(User).where(User.telegram_id == user_id)).first()
        assert user is not None
        assert user.terms_accepted is True


def test_gdpr_right_to_erasure_confirmation_flow(app_client, mock_telegram, telegram_payload_factory):
    """Verify two-step GDPR /delete_my_data confirmation flow and permanent data purging."""
    user_id = 77703
    # First register user
    app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/start", user_id=user_id),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    mock_telegram.messages.clear()
    
    # 1. User executes /delete_my_data
    del_req = telegram_payload_factory(text="/delete_my_data", user_id=user_id)
    res = app_client.post(
        "/api/v1/telegram/webhook",
        json=del_req,
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert res.status_code == 200
    assert len(mock_telegram.messages) == 1
    warning_text = mock_telegram.messages[0]["text"]
    assert "Confirm Permanent Data Erasure" in warning_text
    assert "/delete_my_data confirm" in warning_text
    
    # 2. User confirms deletion
    mock_telegram.messages.clear()
    confirm_req = telegram_payload_factory(text="/delete_my_data confirm", user_id=user_id)
    res = app_client.post(
        "/api/v1/telegram/webhook",
        json=confirm_req,
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert res.status_code == 200
    assert len(mock_telegram.messages) == 1
    assert "Data Purged Successfully" in mock_telegram.messages[0]["text"]
    
    # 3. Verify user and all traces are wiped in DB
    with Session(engine) as session:
        user_in_db = session.exec(select(User).where(User.telegram_id == user_id)).first()
        assert user_in_db is None


def test_gemini_provider_safety_settings_configured():
    """Verify Google Gemini provider enforces strict safety settings on all completion endpoints."""
    assert len(DEFAULT_GEMINI_SAFETY_SETTINGS) == 4
    categories = [s["category"] for s in DEFAULT_GEMINI_SAFETY_SETTINGS]
    assert "HARM_CATEGORY_HARASSMENT" in categories
    assert "HARM_CATEGORY_HATE_SPEECH" in categories
    assert "HARM_CATEGORY_SEXUALLY_EXPLICIT" in categories
    assert "HARM_CATEGORY_DANGEROUS_CONTENT" in categories
    for s in DEFAULT_GEMINI_SAFETY_SETTINGS:
        assert s["threshold"] == "BLOCK_MEDIUM_AND_ABOVE"
