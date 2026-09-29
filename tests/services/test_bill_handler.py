import pytest
import datetime
from sqlmodel import Session, SQLModel, create_engine, select
from sqlalchemy.pool import StaticPool

from src.core.encryption import EncryptionService
from src.db.models import User, Family, Transaction, ScheduledBill
from src.services.handlers.bill_handler import (
    check_and_settle_bill,
    settle_bill_without_amount,
    get_overdue_bills_reminder
)


@pytest.fixture
def db_setup(monkeypatch):
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    SQLModel.metadata.create_all(test_engine)
    monkeypatch.setattr("src.db.session.engine", test_engine)
    monkeypatch.setattr("src.services.handlers.bill_handler.engine", test_engine)
    return test_engine


def test_bill_handler_reminders_and_settlement(db_setup):
    with Session(db_setup) as session:
        family = Family(name="Bill Family", monthly_tx_count=0)
        session.add(family)
        session.commit()
        session.refresh(family)

        user = User(telegram_id=456789, full_name="Bill Tester", family_id=family.id)
        session.add(user)
        session.commit()
        session.refresh(user)

        enc = EncryptionService()
        now_dt = datetime.datetime.now(datetime.timezone.utc)

        # 1. Create a pending scheduled bill
        bill = ScheduledBill(
            family_id=family.id,
            user_id=user.id,
            amount=enc.encrypt("75.00 USD"),
            concept=enc.encrypt("Electricity"),
            category="Rent/Bills",
            due_date=now_dt + datetime.timedelta(days=1),
            status="pending"
        )
        session.add(bill)
        session.commit()

        # 2. Test get_overdue_bills_reminder
        reminder_en = get_overdue_bills_reminder(family.id, is_spanish=False, encryption_service=enc, ref_time=now_dt)
        assert "Electricity" in reminder_en
        assert "Upcoming / Due Bills Reminder" in reminder_en

        reminder_es = get_overdue_bills_reminder(family.id, is_spanish=True, encryption_service=enc, ref_time=now_dt)
        assert "Electricity" in reminder_es
        assert "Recordatorio de Vencimientos" in reminder_es

        # 3. Test check_and_settle_bill
        dummy_tx_id = user.id
        settle_res = check_and_settle_bill(
            family_id=family.id,
            tx_concept="Electricity bill",
            tx_amount=75.0,
            tx_currency="USD",
            tx_id=dummy_tx_id,
            user_id=user.id,
            encryption_service=enc
        )
        assert settle_res is not None
        matched_concept, remaining_str = settle_res
        assert matched_concept == "Electricity"

        # Verify bill is paid
        session.expire_all()
        updated_bill = session.get(ScheduledBill, bill.id)
        assert updated_bill.status == "paid"

        # 4. Create another bill and test settle_bill_without_amount
        bill2 = ScheduledBill(
            family_id=family.id,
            user_id=user.id,
            amount=enc.encrypt("45.00 USD"),
            concept=enc.encrypt("Internet"),
            category="Rent/Bills",
            due_date=now_dt + datetime.timedelta(days=1),
            status="pending"
        )
        session.add(bill2)
        session.commit()

        msg_es = settle_bill_without_amount(family.id, user.id, "Pagué el internet", is_spanish=True, encryption_service=enc)
        assert msg_es is not None
        assert "Internet" in msg_es

        session.expire_all()
        updated_bill2 = session.get(ScheduledBill, bill2.id)
        assert updated_bill2.status == "paid"
