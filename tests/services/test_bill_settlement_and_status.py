import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from unittest.mock import AsyncMock, patch

from sqlmodel import SQLModel, Session, select, create_engine
from sqlalchemy.pool import StaticPool
from src.db.models import User, Family, Transaction, ScheduledBill
from src.core.encryption import EncryptionService
from src.services.extraction.fallback import fallback_regex_classify
from src.services.ai_orchestrator import AIOrchestrator
from src.services.query.service import QueryService
from src.services.family_service import FamilyService

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
    monkeypatch.setattr("src.services.handlers.bill_handler.engine", test_engine)
    monkeypatch.setattr("src.services.handlers.transaction_handler.engine", test_engine)
    monkeypatch.setattr("src.services.handlers.notion_handler.engine", test_engine)
    monkeypatch.setattr("src.services.query.service.engine", test_engine)
    FamilyService._instance = None
    QueryService._instance = None
    yield test_engine
    FamilyService._instance = None
    QueryService._instance = None

def test_fallback_regex_classify_zero_amount_payment():
    res = fallback_regex_classify("Pagué la tarjeta visa", default_currency="ARS")
    assert res.action == "log_transaction"
    assert res.amount is None
    assert "visa" in res.concept.lower()

@pytest.mark.anyio
async def test_settle_bill_without_amount_own_user(setup_db):
    enc = EncryptionService()
    family_id = uuid4()
    user_id = uuid4()

    with Session(setup_db) as session:
        fam = Family(id=family_id, name="Tony's Family", plan_type="family_pro", default_currency="ARS")
        user = User(id=user_id, telegram_id=7777, family_id=family_id, username="tony", full_name="Tony Crespo")
        session.add(fam)
        session.add(user)

        bill = ScheduledBill(
            family_id=family_id,
            user_id=user_id,
            amount=enc.encrypt("1247000.00 ARS"),
            concept=enc.encrypt("Tarjeta Visa"),
            category="Rent/Bills",
            due_date=datetime.now(timezone.utc) + timedelta(days=2),
            status="pending"
        )
        session.add(bill)
        session.commit()
        bill_id = bill.id

    orchestrator = AIOrchestrator()
    mock_telegram = AsyncMock()

    with patch("src.services.ai_orchestrator.TelegramService") as mock_tg_cls:
        mock_tg_cls.return_value.send_message = mock_telegram

        await orchestrator.orchestrate(
            user_id=str(user_id),
            text="Pagué la tarjeta visa",
            audio_file_id=None,
            chat_id=7777
        )

        mock_telegram.assert_called_once()
        rep = mock_telegram.call_args[1]["text"]
        assert ("Marcado como pagado" in rep or "Factura registrada como pagada" in rep)
        assert "Tarjeta Visa" in rep
        assert "1,247,000.00 ARS" in rep

        # Verify ScheduledBill is marked paid
        with Session(setup_db) as session:
            updated_bill = session.get(ScheduledBill, bill_id)
            assert updated_bill.status == "paid"
            assert updated_bill.paid_transaction_id is not None

            # Verify Transaction exists
            tx = session.get(Transaction, updated_bill.paid_transaction_id)
            assert tx is not None
            assert tx.user_id == user_id
            assert "1247000" in enc.decrypt(tx.amount)

@pytest.mark.anyio
async def test_settle_bill_without_amount_user_precedence(setup_db):
    enc = EncryptionService()
    family_id = uuid4()
    tony_id = uuid4()
    marian_id = uuid4()

    with Session(setup_db) as session:
        fam = Family(id=family_id, name="Family", plan_type="family_pro", default_currency="ARS")
        tony = User(id=tony_id, telegram_id=7777, family_id=family_id, username="tony", full_name="Tony Crespo")
        marian = User(id=marian_id, telegram_id=8888, family_id=family_id, username="marian", full_name="Marian Crespo")
        session.add(fam)
        session.add(tony)
        session.add(marian)

        tony_bill = ScheduledBill(
            family_id=family_id,
            user_id=tony_id,
            amount=enc.encrypt("1247000.00 ARS"),
            concept=enc.encrypt("Tarjeta Visa Tony"),
            category="Rent/Bills",
            due_date=datetime.now(timezone.utc) + timedelta(days=3),
            status="pending"
        )
        marian_bill = ScheduledBill(
            family_id=family_id,
            user_id=marian_id,
            amount=enc.encrypt("800000.00 ARS"),
            concept=enc.encrypt("Tarjeta Visa Marian"),
            category="Rent/Bills",
            due_date=datetime.now(timezone.utc) + timedelta(days=3),
            status="pending"
        )
        session.add(tony_bill)
        session.add(marian_bill)
        session.commit()
        tony_bill_id = tony_bill.id
        marian_bill_id = marian_bill.id

    orchestrator = AIOrchestrator()
    mock_telegram = AsyncMock()

    with patch("src.services.ai_orchestrator.TelegramService") as mock_tg_cls:
        mock_tg_cls.return_value.send_message = mock_telegram

        # Tony sends: "Pagué la visa"
        await orchestrator.orchestrate(
            user_id=str(tony_id),
            text="Pagué la visa",
            audio_file_id=None,
            chat_id=7777
        )

        # Tony's bill must be marked paid, Marian's bill must remain pending!
        with Session(setup_db) as session:
            b_tony = session.get(ScheduledBill, tony_bill_id)
            b_marian = session.get(ScheduledBill, marian_bill_id)
            assert b_tony.status == "paid"
            assert b_marian.status == "pending"

@pytest.mark.anyio
async def test_settle_bill_without_amount_family_fallback(setup_db):
    enc = EncryptionService()
    family_id = uuid4()
    tony_id = uuid4()
    marian_id = uuid4()

    with Session(setup_db) as session:
        fam = Family(id=family_id, name="Family", plan_type="family_pro", default_currency="ARS")
        tony = User(id=tony_id, telegram_id=7777, family_id=family_id, username="tony", full_name="Tony Crespo")
        marian = User(id=marian_id, telegram_id=8888, family_id=family_id, username="marian", full_name="Marian Crespo")
        session.add(fam)
        session.add(tony)
        session.add(marian)

        # Only Marian has a bill for "Luz"
        marian_bill = ScheduledBill(
            family_id=family_id,
            user_id=marian_id,
            amount=enc.encrypt("50000.00 ARS"),
            concept=enc.encrypt("Luz Edenor"),
            category="Rent/Bills",
            due_date=datetime.now(timezone.utc) + timedelta(days=2),
            status="pending"
        )
        session.add(marian_bill)
        session.commit()
        marian_bill_id = marian_bill.id

    orchestrator = AIOrchestrator()
    mock_telegram = AsyncMock()

    with patch("src.services.ai_orchestrator.TelegramService") as mock_tg_cls:
        mock_tg_cls.return_value.send_message = mock_telegram

        # Tony sends: "Pagué la luz"
        await orchestrator.orchestrate(
            user_id=str(tony_id),
            text="Pagué la luz",
            audio_file_id=None,
            chat_id=7777
        )

        with Session(setup_db) as session:
            b_marian = session.get(ScheduledBill, marian_bill_id)
            assert b_marian.status == "paid"
            # Transaction is logged under Tony (who paid it)
            tx = session.get(Transaction, b_marian.paid_transaction_id)
            assert tx.user_id == tony_id

@pytest.mark.anyio
async def test_settle_bill_without_amount_not_found(setup_db):
    family_id = uuid4()
    tony_id = uuid4()

    with Session(setup_db) as session:
        fam = Family(id=family_id, name="Family", plan_type="family_pro", default_currency="ARS")
        tony = User(id=tony_id, telegram_id=7777, family_id=family_id, username="tony", full_name="Tony Crespo")
        session.add(fam)
        session.add(tony)
        session.commit()

    orchestrator = AIOrchestrator()
    mock_telegram = AsyncMock()

    with patch("src.services.ai_orchestrator.TelegramService") as mock_tg_cls:
        mock_tg_cls.return_value.send_message = mock_telegram

        await orchestrator.orchestrate(
            user_id=str(tony_id),
            text="Pagué el gas",
            audio_file_id=None,
            chat_id=7777
        )

        mock_telegram.assert_called_once()
        rep = mock_telegram.call_args[1]["text"]
        assert "No encontré ninguna factura pendiente" in rep
        assert "¿Cuánto fue el monto que pagaste?" in rep

@pytest.mark.anyio
async def test_status_query_includes_overdue_bills(setup_db):
    enc = EncryptionService()
    family_id = uuid4()
    tony_id = uuid4()

    with Session(setup_db) as session:
        fam = Family(id=family_id, name="Tony's Family", plan_type="family_pro", default_currency="ARS")
        tony = User(id=tony_id, telegram_id=7777, family_id=family_id, username="tony", full_name="Tony Crespo")
        session.add(fam)
        session.add(tony)

        # Add an overdue bill (due yesterday)
        overdue_bill = ScheduledBill(
            family_id=family_id,
            user_id=tony_id,
            amount=enc.encrypt("1247000.00 ARS"),
            concept=enc.encrypt("Tarjeta Visa"),
            category="Rent/Bills",
            due_date=datetime.now(timezone.utc) - timedelta(days=1),
            status="pending"
        )
        session.add(overdue_bill)
        session.commit()

    orchestrator = AIOrchestrator()
    mock_telegram = AsyncMock()

    with patch("src.services.ai_orchestrator.TelegramService") as mock_tg_cls:
        mock_tg_cls.return_value.send_message = mock_telegram

        await orchestrator.orchestrate(
            user_id=str(tony_id),
            text="como venimos este mes?",
            audio_file_id=None,
            chat_id=7777
        )

        mock_telegram.assert_called_once()
        rep = mock_telegram.call_args[1]["text"]
        assert "Recordatorio de Vencimientos" in rep
        assert "Tarjeta Visa" in rep
        assert "1,247,000.00 ARS" in rep
        assert "Pagué [nombre]" in rep
