import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4, UUID
from unittest.mock import AsyncMock, patch

from sqlmodel import SQLModel, Session, select, create_engine
from sqlalchemy.pool import StaticPool
from src.db.models import User, Family, Transaction, ScheduledBill
from src.core.encryption import EncryptionService
from src.services.extraction.fallback import fallback_regex_classify
from src.services.query import QueryService
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
    monkeypatch.setattr("src.services.handlers.transaction_handler.engine", test_engine)
    monkeypatch.setattr("src.services.handlers.bill_handler.engine", test_engine)
    monkeypatch.setattr("src.services.handlers.notion_handler.engine", test_engine)
    monkeypatch.setattr("src.services.query.service.engine", test_engine)
    yield test_engine

def test_scheduled_bill_model_crud(setup_db):
    enc = EncryptionService()
    family_id = uuid4()
    user_id = uuid4()

    with Session(setup_db) as session:
        fam = Family(id=family_id, name="Test Family", plan_type="family_pro")
        user = User(id=user_id, telegram_id=1001, family_id=family_id, username="tony", full_name="Tony Crespo")
        session.add(fam)
        session.add(user)
        session.commit()

        bill = ScheduledBill(
            family_id=family_id,
            user_id=user_id,
            amount=enc.encrypt("940246.0 ARS"),
            concept=enc.encrypt("Prestamo"),
            category="Rent/Bills",
            due_date=datetime(2026, 9, 18, 0, 0, tzinfo=timezone.utc),
            status="pending"
        )
        session.add(bill)
        session.commit()
        session.refresh(bill)

        assert bill.id is not None
        assert bill.status == "pending"
        assert enc.decrypt(bill.concept) == "Prestamo"
        assert enc.decrypt(bill.amount) == "940246.0 ARS"

def test_extraction_batch_and_due_dates_spanish():
    text = (
        "Los gastos fijos de este mes son:\n"
        "Prestamo $940246. Con vencimento el 18/09\n"
        "Tarjeta Visa $1247000. Con vencimiento 04/09\n"
        "Tarjeta MasterCard $340000. Con vencimiento el 04/09"
    )
    res = fallback_regex_classify(text, "ARS")
    assert res.action == "log_transaction"
    assert len(res.items) == 3

    p1 = res.items[0]
    assert p1.amount == 940246.0
    assert "prestamo" in p1.concept.lower()
    assert p1.is_scheduled_bill is True
    assert p1.due_date is not None
    assert "09-18" in p1.due_date

    p2 = res.items[1]
    assert p2.amount == 1247000.0
    assert "visa" in p2.concept.lower()
    assert p2.is_scheduled_bill is True
    assert "09-04" in p2.due_date

    p3 = res.items[2]
    assert p3.amount == 340000.0
    assert "mastercard" in p3.concept.lower()
    assert p3.is_scheduled_bill is True
    assert "09-04" in p3.due_date

def test_extraction_batch_and_due_dates_english():
    text = (
        "Fixed expenses for this month:\n"
        "Loan $500. Due on 09/18\n"
        "Visa Card $1200. Due on 09/04\n"
        "MasterCard $350. Due on 09/04"
    )
    res = fallback_regex_classify(text, "USD")
    assert res.action == "log_transaction"
    assert len(res.items) == 3

    assert res.items[0].amount == 500.0
    assert "loan" in res.items[0].concept.lower()
    assert res.items[0].is_scheduled_bill is True
    assert "09-18" in res.items[0].due_date

    assert res.items[1].amount == 1200.0
    assert "visa" in res.items[1].concept.lower()
    assert res.items[1].is_scheduled_bill is True

    assert res.items[2].amount == 350.0
    assert "mastercard" in res.items[2].concept.lower()
    assert res.items[2].is_scheduled_bill is True

def test_regular_expense_without_date_is_immediate():
    text = "Lunch 25"
    res = fallback_regex_classify(text, "USD")
    assert res.action == "log_transaction"
    assert res.is_scheduled_bill is False
    assert res.due_date is None
    assert len(res.items) == 1
    assert res.items[0].is_scheduled_bill is False

@pytest.mark.anyio
async def test_orchestrator_batch_logging_query_and_settlement(setup_db):
    enc = EncryptionService()
    family_id = uuid4()
    user_a_id = uuid4()
    user_b_id = uuid4()

    # Seed Family with 2 members
    with Session(setup_db) as session:
        fam = Family(id=family_id, name="Clanomy Family", plan_type="family_pro")
        user_a = User(id=user_a_id, telegram_id=1002, family_id=family_id, username="tony", full_name="Tony Crespo")
        user_b = User(id=user_b_id, telegram_id=1003, family_id=family_id, username="partner", full_name="Family Partner")
        session.add(fam)
        session.add(user_a)
        session.add(user_b)
        session.commit()

    orchestrator = AIOrchestrator()

    mock_telegram = AsyncMock()
    with patch("src.services.ai_orchestrator.TelegramService") as mock_tg_cls:
        mock_tg_cls.return_value.send_message = mock_telegram

        # 1. User A logs batch of fixed expenses with due dates
        batch_msg = (
            "Los gastos fijos de este mes son:\n"
            "Prestamo $940246. Con vencimento el 18/09\n"
            "Tarjeta Visa $1247000. Con vencimiento 04/09\n"
            "Tarjeta MasterCard $340000. Con vencimiento el 04/09"
        )
        await orchestrator.orchestrate(user_id=str(user_a_id), text=batch_msg, audio_file_id=None, chat_id=1001)

        mock_telegram.assert_called_once()
        reply = mock_telegram.call_args[1]["text"]
        assert "3 Factura(s) Programada(s)" in reply
        assert "Prestamo" in reply
        assert "Tarjeta Visa" in reply
        assert "Tarjeta MasterCard" in reply
        assert "Total pendiente por pagar" in reply

        # Verify DB ScheduledBill rows
        with Session(setup_db) as session:
            bills = session.exec(select(ScheduledBill).where(ScheduledBill.family_id == family_id)).all()
            assert len(bills) == 3
            for b in bills:
                assert b.status == "pending"
                assert b.paid_transaction_id is None

        # 2. User B (Family Member) queries: "¿Qué vence este mes?"
        mock_telegram.reset_mock()
        await orchestrator.orchestrate(user_id=str(user_b_id), text="¿Qué vence este mes?", audio_file_id=None, chat_id=1002)

        mock_telegram.assert_called_once()
        query_reply = mock_telegram.call_args[1]["text"]
        assert "Facturas por pagar" in query_reply
        assert "Prestamo" in query_reply
        assert "Tarjeta Visa" in query_reply
        assert "Tarjeta MasterCard" in query_reply

        # 3. User A logs payment for Visa, but with actual paid amount ($1,200,000 instead of $1,247,000)
        mock_telegram.reset_mock()
        await orchestrator.orchestrate(user_id=str(user_a_id), text="Pagué la tarjeta Visa $1200000", audio_file_id=None, chat_id=1001)

        mock_telegram.assert_called_once()
        pay_reply = mock_telegram.call_args[1]["text"]
        assert "¡Marcado como pagado!" in pay_reply
        assert "Tarjeta Visa" in pay_reply

        # Verify DB: Transaction was recorded with actual paid amount (1200000)
        with Session(setup_db) as session:
            txs = session.exec(select(Transaction).where(Transaction.family_id == family_id)).all()
            assert len(txs) == 1
            paid_tx = txs[0]
            dec_tx_amt = enc.decrypt(paid_tx.amount)
            assert "1200000" in dec_tx_amt

            # Verify ScheduledBill for Visa is now paid and points to the transaction
            visa_bill = session.exec(
                select(ScheduledBill).where(
                    ScheduledBill.family_id == family_id,
                    ScheduledBill.status == "paid"
                )
            ).first()
            assert visa_bill is not None
            assert visa_bill.paid_transaction_id == paid_tx.id

            # Verify only 2 pending bills remain
            pending_bills = session.exec(
                select(ScheduledBill).where(
                    ScheduledBill.family_id == family_id,
                    ScheduledBill.status == "pending"
                )
            ).all()
            assert len(pending_bills) == 2

        # 4. User B queries upcoming bills again: Visa is NO LONGER in the pending list!
        mock_telegram.reset_mock()
        await orchestrator.orchestrate(user_id=str(user_b_id), text="facturas pendientes", audio_file_id=None, chat_id=1002)

        mock_telegram.assert_called_once()
        updated_query_reply = mock_telegram.call_args[1]["text"]
        assert "Tarjeta Visa" not in updated_query_reply
        assert "Prestamo" in updated_query_reply
        assert "Tarjeta MasterCard" in updated_query_reply

@pytest.mark.anyio
async def test_orchestrator_english_query_and_shortcuts(setup_db):
    family_id = uuid4()
    user_id = uuid4()
    enc = EncryptionService()

    with Session(setup_db) as session:
        fam = Family(id=family_id, name="English Family", plan_type="family_pro")
        user = User(id=user_id, telegram_id=1004, family_id=family_id, username="sarah", full_name="Sarah Connor")
        session.add(fam)
        session.add(user)
        session.commit()

    orchestrator = AIOrchestrator()
    mock_telegram = AsyncMock()

    with patch("src.services.ai_orchestrator.TelegramService") as mock_tg_cls:
        mock_tg_cls.return_value.send_message = mock_telegram

        # Ask when there are no bills
        await orchestrator.orchestrate(user_id=str(user_id), text="/bills", audio_file_id=None, chat_id=2001)
        mock_telegram.assert_called_once()
        assert "no upcoming bills" in mock_telegram.call_args[1]["text"].lower() or "no tienes facturas" in mock_telegram.call_args[1]["text"].lower()

        # Add a scheduled bill in English
        mock_telegram.reset_mock()
        batch_en = "Fixed expenses:\nElectric Bill $150. Due on 09/20\nInternet $80. Due on 09/25"
        await orchestrator.orchestrate(user_id=str(user_id), text=batch_en, audio_file_id=None, chat_id=2001)
        assert "Scheduled Bill(s)" in mock_telegram.call_args[1]["text"]
        assert "Electric Bill" in mock_telegram.call_args[1]["text"]

        # Query in English
        mock_telegram.reset_mock()
        await orchestrator.orchestrate(user_id=str(user_id), text="what bills are due this month?", audio_file_id=None, chat_id=2001)
        res = mock_telegram.call_args[1]["text"]
        assert "Electric Bill" in res
        assert "Internet" in res
