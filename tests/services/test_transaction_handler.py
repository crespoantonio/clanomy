import pytest
import datetime
from sqlmodel import Session, SQLModel, create_engine, select
from sqlalchemy.pool import StaticPool

from src.core.encryption import EncryptionService
from src.db.models import User, Family, Transaction
from src.services.query.models import ParsedQueryIntent
from src.services.handlers.transaction_handler import (
    handle_transaction_undo,
    handle_transaction_correction,
    find_target_transaction,
    get_monthly_cash_flow_snapshot,
    format_currency
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
    monkeypatch.setattr("src.services.handlers.transaction_handler.engine", test_engine)
    return test_engine


def test_format_currency():
    assert format_currency(1234.56, "USD") == "$1,234.56 USD"
    assert format_currency(-50.0, "EUR") == "-€50.00 EUR"
    assert format_currency(100.0, "USD", show_sign=True) == "+$100.00 USD"


def test_transaction_handler_undo_and_correction(db_setup):
    with Session(db_setup) as session:
        family = Family(name="Test Family", monthly_tx_count=0)
        session.add(family)
        session.commit()
        session.refresh(family)

        user = User(telegram_id=987654, full_name="Handler Tester", family_id=family.id)
        session.add(user)
        session.commit()
        session.refresh(user)

        enc = EncryptionService()
        now_dt = datetime.datetime.now(datetime.timezone.utc)

        # 1. Add transaction
        tx = Transaction(
            user_id=user.id,
            family_id=family.id,
            amount=enc.encrypt("100.00 USD"),
            concept=enc.encrypt("Supermarket"),
            category="Food/Drink",
            type="expense",
            timestamp=now_dt
        )
        session.add(tx)
        session.commit()

        tx_id = tx.id

        # 2. Test find_target_transaction
        found = find_target_transaction(session, user.id, target_amount=100.0, target_currency="USD", encryption_service=enc)
        assert found is not None
        assert found.id == tx_id

        # 3. Test correction (change amount to 120 and concept to Groceries)
        correction_intent = ParsedQueryIntent(
            intent="edit_last",
            new_amount=120.0,
            new_concept="Groceries",
            new_category="Food/Drink"
        )
        edit_res = handle_transaction_correction(user.id, correction_intent, encryption_service=enc)
        assert "Updated" in edit_res or "Groceries" in edit_res

        # Verify DB updated
        session.expire_all()
        updated_tx = session.get(Transaction, tx_id)
        assert enc.decrypt(updated_tx.amount) == "120.00 USD"
        assert enc.decrypt(updated_tx.concept) == "Groceries"

        # 4. Test snapshot calculation
        snap = get_monthly_cash_flow_snapshot(family.id, now_dt, "USD", encryption_service=enc)
        assert snap["total_out"] == 120.0

        # 5. Test undo
        undo_res = handle_transaction_undo(user.id, encryption_service=enc)
        assert "Removed" in undo_res
        session.expire_all()
        deleted_tx = session.get(Transaction, tx_id)
        assert deleted_tx is None
