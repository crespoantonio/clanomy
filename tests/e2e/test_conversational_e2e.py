"""
End-to-End (E2E) Conversational Lifecycle Tests.
Exercises complete user journeys across the webhook ingress, database, encryption,
AI orchestrator, batch tracking, and outbound messaging:
1. Registration & Terms of Service compliance gate
2. Fast-path deterministic slash commands (/month, /today, /balance, /bills, /help)
3. Natural language spend logging (expense)
4. Natural language income logging (income)
5. Transaction rollback via /undo
6. Conversational queries and period comparisons
"""

import pytest
from sqlmodel import Session, select
from src.core.config import settings
from src.core.encryption import EncryptionService
from src.db.models import User, Family, Transaction
from tests.e2e.conftest import e2e_test_engine


def test_e2e_full_conversational_journey(app_client, mock_telegram, telegram_payload_factory, monkeypatch):
    """
    [E2E] Full sequential user journey from initial /start to commands, spend,
    income, undo, and conversational queries.
    """
    monkeypatch.setattr(settings, "REQUIRE_TERMS_ACCEPTANCE", True)
    encryption = EncryptionService()
    user_id = 91001
    secret_header = {"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}

    # =========================================================================
    # Step 1: Onboarding & Compliance Gate
    # =========================================================================
    start_payload = telegram_payload_factory(text="/start", user_id=user_id, first_name="E2E_Tony")
    res = app_client.post("/api/v1/telegram/webhook", json=start_payload, headers=secret_header)
    assert res.status_code == 200
    assert len(mock_telegram.messages) == 1
    consent_card = mock_telegram.messages[0]["text"]
    assert "Zero-Knowledge" in consent_card or "18 years of age or older" in consent_card
    assert mock_telegram.messages[0].get("reply_markup") is not None

    # Verify user cannot log before accepting TOS
    mock_telegram.messages.clear()
    unconsented_spend = telegram_payload_factory(text="25 on lunch", user_id=user_id)
    res = app_client.post("/api/v1/telegram/webhook", json=unconsented_spend, headers=secret_header)
    assert res.status_code == 200
    assert len(mock_telegram.messages) == 1
    assert "terms" in mock_telegram.messages[0]["text"].lower()

    # User clicks 'accept_tos' callback button
    mock_telegram.messages.clear()
    cb_accept_payload = {
        "callback_query": {
            "id": "cb_tos_91001",
            "from": {"id": user_id, "first_name": "E2E_Tony", "username": "e2e_tony"},
            "message": {"message_id": 102, "chat": {"id": user_id}},
            "data": "accept_tos"
        }
    }
    res = app_client.post("/api/v1/telegram/webhook", json=cb_accept_payload, headers=secret_header)
    assert res.status_code == 200
    assert len(mock_telegram.answered_callbacks) == 1
    assert len(mock_telegram.messages) >= 1
    welcome_msg = mock_telegram.messages[-1]["text"]
    assert "Welcome to Clanomy" in welcome_msg
    assert "60-Day Duo Pro Trial" in welcome_msg

    # Verify User & Family state in database
    with Session(e2e_test_engine) as session:
        db_user = session.exec(select(User).where(User.telegram_id == user_id)).first()
        assert db_user is not None
        assert db_user.terms_accepted is True
        db_family = session.get(Family, db_user.family_id)
        assert db_family is not None
        assert db_family.plan_type in ("duo_pro", "trial")

    # =========================================================================
    # Step 2: Fast-Path Deterministic Slash Commands
    # =========================================================================
    # Test /month
    mock_telegram.messages.clear()
    res = app_client.post("/api/v1/telegram/webhook", json=telegram_payload_factory(text="/month", user_id=user_id), headers=secret_header)
    assert res.status_code == 200
    assert "Summary" in mock_telegram.messages[0]["text"] or "Resumen" in mock_telegram.messages[0]["text"]

    # Test /today
    mock_telegram.messages.clear()
    res = app_client.post("/api/v1/telegram/webhook", json=telegram_payload_factory(text="/today", user_id=user_id), headers=secret_header)
    assert res.status_code == 200
    assert len(mock_telegram.messages) == 1
    assert "Today" in mock_telegram.messages[0]["text"] or "Hoy" in mock_telegram.messages[0]["text"]

    # Test /balance
    mock_telegram.messages.clear()
    res = app_client.post("/api/v1/telegram/webhook", json=telegram_payload_factory(text="/balance", user_id=user_id), headers=secret_header)
    assert res.status_code == 200
    assert len(mock_telegram.messages) == 1
    assert "Cash Flow" in mock_telegram.messages[0]["text"] or "Saldo" in mock_telegram.messages[0]["text"] or "Net" in mock_telegram.messages[0]["text"]

    # Test /help
    mock_telegram.messages.clear()
    res = app_client.post("/api/v1/telegram/webhook", json=telegram_payload_factory(text="/help", user_id=user_id), headers=secret_header)
    assert res.status_code == 200
    assert len(mock_telegram.messages) == 1
    assert "/month" in mock_telegram.messages[0]["text"]
    assert "/undo" in mock_telegram.messages[0]["text"]

    # =========================================================================
    # Step 3: Add a Spend (Expense Logging)
    # =========================================================================
    mock_telegram.messages.clear()
    spend_payload = telegram_payload_factory(text="Spent 45.50 on groceries at Trader Joe's", user_id=user_id)
    res = app_client.post("/api/v1/telegram/webhook", json=spend_payload, headers=secret_header)
    assert res.status_code == 200
    assert len(mock_telegram.messages) > 0
    spend_reply = mock_telegram.messages[-1]["text"]
    assert "45.5" in spend_reply
    assert "groceries" in spend_reply.lower() or "trader joe" in spend_reply.lower()

    # Verify Transaction in Database
    with Session(e2e_test_engine) as session:
        txs = session.exec(select(Transaction).where(Transaction.user_id == db_user.id)).all()
        assert len(txs) == 1
        assert txs[0].type == "expense"
        decrypted_concept = encryption.decrypt(txs[0].concept)
        assert "groceries" in decrypted_concept.lower()
        decrypted_amount = encryption.decrypt(txs[0].amount)
        assert "45.5" in decrypted_amount

    # =========================================================================
    # Step 4: Add an Income (Income Logging)
    # =========================================================================
    mock_telegram.messages.clear()
    income_payload = telegram_payload_factory(text="Got paid 3500 salary from Acme Corp", user_id=user_id)
    res = app_client.post("/api/v1/telegram/webhook", json=income_payload, headers=secret_header)
    assert res.status_code == 200
    assert len(mock_telegram.messages) > 0
    income_reply = mock_telegram.messages[-1]["text"]
    assert "Income Logged" in income_reply or "💰" in income_reply
    assert "3,500.00" in income_reply or "3500" in income_reply

    with Session(e2e_test_engine) as session:
        incomes = session.exec(select(Transaction).where(Transaction.user_id == db_user.id, Transaction.type == "income")).all()
        assert len(incomes) == 1
        assert "3500" in encryption.decrypt(incomes[0].amount)

    # =========================================================================
    # Step 5: Undo Last (/undo)
    # =========================================================================
    mock_telegram.messages.clear()
    undo_payload = telegram_payload_factory(text="/undo", user_id=user_id)
    res = app_client.post("/api/v1/telegram/webhook", json=undo_payload, headers=secret_header)
    assert res.status_code == 200
    assert len(mock_telegram.messages) > 0
    undo_reply = mock_telegram.messages[-1]["text"]
    assert "Removed" in undo_reply or "Deshecho" in undo_reply or "Eliminado" in undo_reply

    # Verify the income transaction was rolled back and deleted from DB
    with Session(e2e_test_engine) as session:
        remaining_txs = session.exec(select(Transaction).where(Transaction.user_id == db_user.id)).all()
        # Only the expense remains, income is deleted
        assert len(remaining_txs) == 1
        assert remaining_txs[0].type == "expense"

    # =========================================================================
    # Step 6: Ask Questions (Conversational Queries)
    # =========================================================================
    mock_telegram.messages.clear()
    query_payload = telegram_payload_factory(text="How much did I spend this month?", user_id=user_id)
    res = app_client.post("/api/v1/telegram/webhook", json=query_payload, headers=secret_header)
    assert res.status_code == 200
    assert len(mock_telegram.messages) > 0
    query_reply = mock_telegram.messages[-1]["text"]
    assert "45.5" in query_reply or "45.50" in query_reply

    # Compare query
    mock_telegram.messages.clear()
    compare_payload = telegram_payload_factory(text="Compare my spending this week to last week", user_id=user_id)
    res = app_client.post("/api/v1/telegram/webhook", json=compare_payload, headers=secret_header)
    assert res.status_code == 200
    assert len(mock_telegram.messages) > 0
    compare_reply = mock_telegram.messages[-1]["text"].lower()
    assert "week" in compare_reply or "spending" in compare_reply or "summary" in compare_reply
