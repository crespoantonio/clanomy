import pytest
from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import AsyncMock, patch

from sqlmodel import SQLModel, Session, select, create_engine
from sqlalchemy.pool import StaticPool
from src.db.models import User, Family, Transaction
from src.core.encryption import EncryptionService
from src.services.extraction.fallback import fallback_regex_classify, fallback_regex_extract
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

def test_currency_detection_default_ars():
    """Verify that '$' without explicit USD markers defaults to ARS when workspace currency is ARS."""
    res = fallback_regex_extract("$1606932 ingresaron de sueldo también", default_currency="ARS")
    assert res.amount == 1606932.0
    assert res.currency == "ARS"
    assert res.type == "income"

def test_currency_detection_explicit_usd():
    """Verify that explicit 'dolares' forces USD even when workspace currency is ARS."""
    res = fallback_regex_extract("2568 dolares es mi primer sueldo", default_currency="ARS")
    assert res.amount == 2568.0
    assert res.currency == "USD"
    assert res.type == "income"

def test_contextual_currency_correction_classification():
    """Verify that messages specifying currency for a past item are classified as edit_last."""
    res1 = fallback_regex_classify("el salario de 1606932 es ARS", default_currency="ARS")
    assert res1.action == "edit_last"
    assert res1.target_amount == 1606932.0
    assert res1.new_currency == "ARS"

    res2 = fallback_regex_classify("era en pesos", default_currency="ARS")
    assert res2.action == "edit_last"
    assert res2.new_currency == "ARS"

    res3 = fallback_regex_classify("el de 2568 era en dolares", default_currency="ARS")
    assert res3.action == "edit_last"
    assert res3.target_amount == 2568.0
    assert res3.new_currency == "USD"

def test_targeted_undo_classification():
    """Verify that targeted undo messages extract amount and currency criteria."""
    res = fallback_regex_classify("eliminar el ingreso de 1606932 en dolares", default_currency="ARS")
    assert res.action == "undo_last"
    assert res.target_amount == 1606932.0
    assert res.target_currency == "USD"

@pytest.mark.anyio
async def test_targeted_correction_and_multi_currency_snapshot(setup_db):
    """
    End-to-end test mimicking the user's exact conversation:
    1. User logs: '2568 dolares es mi primer sueldo' -> 2568 USD logged
    2. User logs: '$1606932 ingresaron de sueldo también' -> 1606932 ARS logged (with default_currency=ARS)
    3. User says: 'el salario de 1606932 es ARS' -> targeted edit updates that specific transaction
    4. Snapshot displays both currencies in balance card
    """
    enc = EncryptionService()
    family_id = uuid4()
    user_id = uuid4()

    with Session(setup_db) as session:
        fam = Family(id=family_id, name="Tony's Family", plan_type="family_pro", default_currency="ARS")
        user = User(id=user_id, telegram_id=9999, family_id=family_id, username="tony", full_name="Tony Crespo")
        session.add(fam)
        session.add(user)
        session.commit()

    orchestrator = AIOrchestrator()
    mock_telegram = AsyncMock()

    with patch("src.services.ai_orchestrator.TelegramService") as mock_tg_cls:
        mock_tg_cls.return_value.send_message = mock_telegram

        # Step 1: Log USD income
        await orchestrator.orchestrate(user_id=str(user_id), text="2568 dolares es mi primer sueldo", audio_file_id=None, chat_id=9999)
        mock_telegram.assert_called_once()
        rep1 = mock_telegram.call_args[1]["text"]
        assert "2,568.00 USD" in rep1

        # Step 2: Log ARS income using '$' symbol
        mock_telegram.reset_mock()
        await orchestrator.orchestrate(user_id=str(user_id), text="$1606932 ingresaron de sueldo también", audio_file_id=None, chat_id=9999)
        mock_telegram.assert_called_once()
        rep2 = mock_telegram.call_args[1]["text"]
        assert "1,606,932.00 ARS" in rep2

        # Step 3: Targeted correction: 'el salario de 1606932 es ARS'
        mock_telegram.reset_mock()
        await orchestrator.orchestrate(user_id=str(user_id), text="el salario de 1606932 es ARS", audio_file_id=None, chat_id=9999)
        mock_telegram.assert_called_once()
        rep3 = mock_telegram.call_args[1]["text"]
        assert "Updated transaction" in rep3
        assert "1,606,932.00 ARS" in rep3

        # Step 4: Verify DB records: Exactly 2 transactions exist (no duplicates!)
        with Session(setup_db) as session:
            txs = session.exec(select(Transaction).where(Transaction.family_id == family_id)).all()
            assert len(txs) == 2
            amounts = [enc.decrypt(tx.amount) for tx in txs]
            assert any("2568" in a and "USD" in a for a in amounts)
            assert any("1606932" in a and "ARS" in a for a in amounts)

@pytest.mark.anyio
async def test_targeted_undo_specific_currency_and_amount(setup_db):
    """
    Verify that if a user has multiple transactions, specifying amount and currency
    targets and deletes that exact transaction.
    """
    enc = EncryptionService()
    family_id = uuid4()
    user_id = uuid4()

    with Session(setup_db) as session:
        fam = Family(id=family_id, name="Test Fam", plan_type="family_pro", default_currency="ARS")
        user = User(id=user_id, telegram_id=8888, family_id=family_id, username="tony")
        session.add(fam)
        session.add(user)

        # Seed 3 transactions:
        # TX1: 2568 USD
        # TX2: 1606932 ARS
        # TX3: 1606932 USD (unwanted erroneous duplicate)
        t1 = Transaction(family_id=family_id, user_id=user_id, amount=enc.encrypt("2568.00 USD"), concept=enc.encrypt("Salary USD"), category="Salary", type="income", timestamp=datetime.now(timezone.utc))
        t2 = Transaction(family_id=family_id, user_id=user_id, amount=enc.encrypt("1606932.00 ARS"), concept=enc.encrypt("Salary ARS"), category="Salary", type="income", timestamp=datetime.now(timezone.utc))
        t3 = Transaction(family_id=family_id, user_id=user_id, amount=enc.encrypt("1606932.00 USD"), concept=enc.encrypt("Salary Wrong USD"), category="Salary", type="income", timestamp=datetime.now(timezone.utc))
        session.add(t1)
        session.add(t2)
        session.add(t3)
        session.commit()

    orchestrator = AIOrchestrator()
    mock_telegram = AsyncMock()

    with patch("src.services.ai_orchestrator.TelegramService") as mock_tg_cls:
        mock_tg_cls.return_value.send_message = mock_telegram

        # Targeted undo: delete the 1606932 USD transaction
        await orchestrator.orchestrate(user_id=str(user_id), text="eliminar el ingreso de 1606932 en dolares", audio_file_id=None, chat_id=8888)
        mock_telegram.assert_called_once()
        reply = mock_telegram.call_args[1]["text"]
        assert "Removed transaction" in reply
        assert "1,606,932.00 USD" in reply

        # Verify DB: Only TX1 (2568 USD) and TX2 (1606932 ARS) remain!
        with Session(setup_db) as session:
            txs = session.exec(select(Transaction).where(Transaction.family_id == family_id)).all()
            assert len(txs) == 2
            amounts = [enc.decrypt(tx.amount) for tx in txs]
            assert any("2568" in a and "USD" in a for a in amounts)
            assert any("1606932" in a and "ARS" in a for a in amounts)
            assert not any("1606932" in a and "USD" in a for a in amounts)
