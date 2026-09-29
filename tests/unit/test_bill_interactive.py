import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from uuid import uuid4
import datetime

from src.db.models import ScheduledBill, Transaction, User, Family
from src.core.encryption import EncryptionService
from src.services.query.models import DecryptedScheduledBill
from src.services.handlers.bill_handler import (
    build_bills_keyboard,
    build_bill_settlement_card,
    settle_bill_by_id,
    handle_bills_interactive
)


def _make_mock_bill(bill_id=None, concept="Electricity", amount=45.0, currency="USD", status="pending"):
    return DecryptedScheduledBill(
        id=bill_id or uuid4(),
        family_id=uuid4(),
        user_id=uuid4(),
        user_name="Alice",
        amount=amount,
        currency=currency,
        concept=concept,
        category="Rent/Bills",
        due_date=datetime.datetime(2026, 9, 20, 12, 0, tzinfo=datetime.timezone.utc),
        status=status,
        created_at=datetime.datetime(2026, 9, 1, 10, 0, tzinfo=datetime.timezone.utc)
    )


def test_build_bills_keyboard_empty():
    assert build_bills_keyboard([]) is None


def test_build_bills_keyboard_single_page():
    bills = [_make_mock_bill(concept=f"Bill {i}", amount=10.0 * i) for i in range(1, 4)]
    kb = build_bills_keyboard(bills, page=1, timeframe="this_month", page_size=4)
    assert kb is not None
    rows = kb["inline_keyboard"]
    # 3 bills <= 4 page_size -> exactly 3 rows, no pagination nav row
    assert len(rows) == 3
    assert rows[0][0]["callback_data"].startswith("bill_v:")
    assert "Bill 1" in rows[0][0]["text"]


def test_build_bills_keyboard_multi_page():
    bills = [_make_mock_bill(concept=f"Bill {i}", amount=10.0 * i) for i in range(1, 10)]
    # 9 bills with page_size=4 -> 3 pages
    kb = build_bills_keyboard(bills, page=1, timeframe="this_month", page_size=4)
    assert kb is not None
    rows = kb["inline_keyboard"]
    assert len(rows) == 5  # 4 bill rows + 1 nav row
    nav_row = rows[4]
    assert len(nav_row) == 3
    assert nav_row[0]["callback_data"] == "bills_p:3:this"
    assert "Page 1/3" in nav_row[1]["text"]
    assert nav_row[2]["callback_data"] == "bills_p:2:this"

    # Page 2
    kb_p2 = build_bills_keyboard(bills, page=2, timeframe="this_month", page_size=4)
    rows_p2 = kb_p2["inline_keyboard"]
    assert len(rows_p2) == 5
    nav_row_p2 = rows_p2[4]
    assert nav_row_p2[0]["callback_data"] == "bills_p:1:this"
    assert "Page 2/3" in nav_row_p2[1]["text"]
    assert nav_row_p2[2]["callback_data"] == "bills_p:3:this"


def test_build_bills_keyboard_long_concept_truncated():
    bill = _make_mock_bill(concept="Very Super Long Service Name That Exceeds Limit")
    kb = build_bills_keyboard([bill], page=1)
    btn = kb["inline_keyboard"][0][0]
    assert "…" in btn["text"]


def test_build_bill_settlement_card_not_found():
    mock_session = MagicMock()
    mock_session.get.return_value = None
    mock_factory = MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=mock_session), __exit__=MagicMock()))

    text, kb = build_bill_settlement_card(
        bill_id=uuid4(),
        family_id=uuid4(),
        session_factory=mock_factory
    )
    assert "not found" in text.lower()
    assert kb["inline_keyboard"][0][0]["callback_data"] == "bills_p:1:this"


def test_build_bill_settlement_card_pending():
    bill_id = uuid4()
    family_id = uuid4()
    enc_service = EncryptionService()

    bill = ScheduledBill(
        id=bill_id,
        family_id=family_id,
        user_id=uuid4(),
        concept=enc_service.encrypt("Internet Fibra"),
        amount=enc_service.encrypt("50.00 USD"),
        category="Rent/Bills",
        due_date=datetime.datetime(2026, 9, 25, 12, 0, tzinfo=datetime.timezone.utc),
        status="pending"
    )

    mock_session = MagicMock()
    mock_session.get.return_value = bill
    mock_factory = MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=mock_session), __exit__=MagicMock()))

    text, kb = build_bill_settlement_card(
        bill_id=bill_id,
        family_id=family_id,
        encryption_service=enc_service,
        session_factory=mock_factory
    )

    assert "Internet Fibra" in text
    assert "$50.00" in text or "50.00 USD" in text
    rows = kb["inline_keyboard"]
    assert len(rows) == 3
    assert rows[0][0]["callback_data"] == f"bill_pay:{bill_id}:this"
    assert rows[1][0]["callback_data"] == f"bill_edit:{bill_id}"
    assert rows[2][0]["callback_data"] == "bills_p:1:this"


@patch("src.services.handlers.bill_handler.safe_mirror_to_notion", return_value=AsyncMock()())
@patch("src.services.handlers.bill_handler.create_logged_task")
def test_settle_bill_by_id_saved_amount(mock_task, mock_mirror):
    bill_id = uuid4()
    family_id = uuid4()
    user_id = uuid4()
    enc_service = EncryptionService()

    bill = ScheduledBill(
        id=bill_id,
        family_id=family_id,
        user_id=user_id,
        concept=enc_service.encrypt("Netflix"),
        amount=enc_service.encrypt("15.99 USD"),
        category="Subscriptions",
        due_date=datetime.datetime(2026, 9, 15, 12, 0, tzinfo=datetime.timezone.utc),
        status="pending"
    )

    mock_session = MagicMock()
    mock_session.get.side_effect = lambda model, obj_id: bill if model == ScheduledBill else None
    mock_session.exec.return_value.all.return_value = []
    mock_factory = MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=mock_session), __exit__=MagicMock()))

    success, msg = settle_bill_by_id(
        bill_id=bill_id,
        user_id=user_id,
        family_id=family_id,
        encryption_service=enc_service,
        session_factory=mock_factory
    )

    assert success is True
    assert "Netflix" in msg
    assert bill.status == "paid"
    assert mock_session.commit.called


@patch("src.services.handlers.bill_handler.safe_mirror_to_notion", return_value=AsyncMock()())
@patch("src.services.handlers.bill_handler.create_logged_task")
def test_settle_bill_by_id_override_amount(mock_task, mock_mirror):
    bill_id = uuid4()
    family_id = uuid4()
    user_id = uuid4()
    enc_service = EncryptionService()

    bill = ScheduledBill(
        id=bill_id,
        family_id=family_id,
        user_id=user_id,
        concept=enc_service.encrypt("Electricity"),
        amount=enc_service.encrypt("40.00 USD"),
        category="Rent/Bills",
        due_date=datetime.datetime(2026, 9, 18, 12, 0, tzinfo=datetime.timezone.utc),
        status="pending"
    )

    mock_session = MagicMock()
    mock_session.get.side_effect = lambda model, obj_id: bill if model == ScheduledBill else None
    mock_session.exec.return_value.all.return_value = []
    mock_factory = MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=mock_session), __exit__=MagicMock()))

    success, msg = settle_bill_by_id(
        bill_id=bill_id,
        user_id=user_id,
        family_id=family_id,
        override_amount=52.50,
        encryption_service=enc_service,
        session_factory=mock_factory
    )

    assert success is True
    assert "Electricity" in msg
    assert "52.50" in msg
    assert "updated amount" in msg
    assert bill.status == "paid"
    # Verify updated amount in bill
    dec_amt = enc_service.decrypt(bill.amount)
    assert "52.50" in dec_amt


def test_settle_bill_by_id_already_paid():
    bill_id = uuid4()
    family_id = uuid4()
    user_id = uuid4()
    enc_service = EncryptionService()

    bill = ScheduledBill(
        id=bill_id,
        family_id=family_id,
        user_id=user_id,
        concept=enc_service.encrypt("Gym"),
        amount=enc_service.encrypt("30.00 USD"),
        category="Leisure",
        due_date=datetime.datetime(2026, 9, 10, 12, 0, tzinfo=datetime.timezone.utc),
        status="paid"
    )

    mock_session = MagicMock()
    mock_session.get.return_value = bill
    mock_factory = MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=mock_session), __exit__=MagicMock()))

    success, msg = settle_bill_by_id(
        bill_id=bill_id,
        user_id=user_id,
        family_id=family_id,
        encryption_service=enc_service,
        session_factory=mock_factory
    )

    assert success is False
    assert "already marked as paid" in msg.lower()
