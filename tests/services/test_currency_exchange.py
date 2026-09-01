import pytest
from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import AsyncMock, patch

from sqlmodel import SQLModel, Session, select, create_engine
from sqlalchemy.pool import StaticPool
from src.db.models import User, Family, Transaction
from src.core.encryption import EncryptionService
from src.services.extraction.fallback import fallback_regex_classify
from src.services.ai_orchestrator import AIOrchestrator

@pytest.fixture(autouse=True)
def setup_db(monkeypatch):
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    SQLModel.metadata.create_all(test_engine)
    monkeypatch.setattr("src.db.session.engine", test_engine)
    monkeypatch.setattr("src.services.ai_orchestrator.engine", test_engine)
    monkeypatch.setattr("src.services.query.service.engine", test_engine)
    yield test_engine

def test_exchange_extraction_spanish_amount_for_amount():
    res = fallback_regex_classify("Cambie 200 dolares por 300000 pesos", default_currency="ARS")
    assert res.action == "log_transaction"
    assert res.is_exchange is True
    assert res.exchange_rate == 1500.0
    items = res.get_all_items()
    assert len(items) == 2

    sold = next(i for i in items if i.type == "expense")
    recv = next(i for i in items if i.type == "income")

    assert sold.amount == 200.0
    assert sold.currency == "USD"
    assert sold.category == "Exchange"

    assert recv.amount == 300000.0
    assert recv.currency == "ARS"
    assert recv.category == "Exchange"

def test_exchange_extraction_english():
    res = fallback_regex_classify("I change 200 USD for 300000 ARS", default_currency="ARS")
    assert res.action == "log_transaction"
    assert res.is_exchange is True
    assert res.exchange_rate == 1500.0
    items = res.get_all_items()
    assert len(items) == 2

    sold = next(i for i in items if i.type == "expense")
    recv = next(i for i in items if i.type == "income")

    assert sold.amount == 200.0
    assert sold.currency == "USD"
    assert sold.category == "Exchange"

    assert recv.amount == 300000.0
    assert recv.currency == "ARS"
    assert recv.category == "Exchange"

def test_exchange_extraction_rate_based():
    res = fallback_regex_classify("Cambie 200 dolares a 1500", default_currency="ARS")
    assert res.action == "log_transaction"
    assert res.is_exchange is True
    assert res.exchange_rate == 1500.0
    items = res.get_all_items()
    assert len(items) == 2

    sold = next(i for i in items if i.type == "expense")
    recv = next(i for i in items if i.type == "income")

    assert sold.amount == 200.0
    assert sold.currency == "USD"
    assert recv.amount == 300000.0
    assert recv.currency == "ARS"

def test_exchange_reverse_direction():
    res = fallback_regex_classify("Compre 100 dolares por 150000 pesos", default_currency="ARS")
    assert res.action == "log_transaction"
    assert res.is_exchange is True
    items = res.get_all_items()
    assert len(items) == 2

    sold = next(i for i in items if i.type == "expense")
    recv = next(i for i in items if i.type == "income")

    assert sold.amount == 150000.0
    assert sold.currency == "ARS"
    assert recv.amount == 100.0
    assert recv.currency == "USD"

@pytest.mark.anyio
async def test_orchestrator_exchange_end_to_end(setup_db):
    enc = EncryptionService()
    family_id = uuid4()
    user_id = uuid4()

    with Session(setup_db) as session:
        fam = Family(id=family_id, name="Tony's Family", plan_type="family_pro", default_currency="ARS")
        user = User(id=user_id, telegram_id=7777, family_id=family_id, username="tony", full_name="Tony Crespo")
        session.add(fam)
        session.add(user)
        session.commit()

    orchestrator = AIOrchestrator()
    mock_telegram = AsyncMock()

    with patch("src.services.ai_orchestrator.TelegramService") as mock_tg_cls:
        mock_tg_cls.return_value.send_message = mock_telegram

        await orchestrator.orchestrate(
            user_id=str(user_id),
            text="Cambie 200 dolares por 300000 pesos",
            audio_file_id=None,
            chat_id=7777
        )

        mock_telegram.assert_called_once()
        rep = mock_telegram.call_args[1]["text"]
        assert "Cambio de Moneda Registrado:" in rep
        assert "200.00 USD" in rep
        assert "300,000.00 ARS" in rep
        assert "Exchange" in rep

        # Verify DB has exactly 2 transactions with category "Exchange"
        with Session(setup_db) as session:
            txs = session.exec(select(Transaction).where(Transaction.family_id == family_id)).all()
            assert len(txs) == 2
            assert all(t.category == "Exchange" for t in txs)
            types = {t.tx_type for t in txs}
            assert types == {"expense", "income"}

@pytest.mark.anyio
async def test_orchestrator_exchange_coupled_undo(setup_db):
    enc = EncryptionService()
    family_id = uuid4()
    user_id = uuid4()

    with Session(setup_db) as session:
        fam = Family(id=family_id, name="Tony's Family", plan_type="family_pro", default_currency="ARS")
        user = User(id=user_id, telegram_id=7777, family_id=family_id, username="tony", full_name="Tony Crespo")
        session.add(fam)
        session.add(user)
        session.commit()

    orchestrator = AIOrchestrator()
    mock_telegram = AsyncMock()

    with patch("src.services.ai_orchestrator.TelegramService") as mock_tg_cls:
        mock_tg_cls.return_value.send_message = mock_telegram

        # 1. Log exchange
        await orchestrator.orchestrate(
            user_id=str(user_id),
            text="Cambie 200 dolares por 300000 pesos",
            audio_file_id=None,
            chat_id=7777
        )

        with Session(setup_db) as session:
            txs = session.exec(select(Transaction).where(Transaction.family_id == family_id)).all()
            assert len(txs) == 2

        # 2. Revert with undo
        mock_telegram.reset_mock()
        await orchestrator.orchestrate(
            user_id=str(user_id),
            text="/undo",
            audio_file_id=None,
            chat_id=7777
        )

        mock_telegram.assert_called_once()
        rep = mock_telegram.call_args[1]["text"]
        assert "Removed currency exchange" in rep

        # 3. Verify BOTH legs were atomically deleted from the database
        with Session(setup_db) as session:
            txs = session.exec(select(Transaction).where(Transaction.family_id == family_id)).all()
            assert len(txs) == 0
