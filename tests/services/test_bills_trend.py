import pytest
import datetime
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.pool import StaticPool
from uuid import uuid4

from src.core.encryption import EncryptionService
from src.db.models import User, Family, ScheduledBill
from src.services.query.service import QueryService
from src.services.query.models import MonthFixedCommitment, BillsTrendSummary
from src.services.query.formatters import (
    format_bills_trend_badge,
    format_bills_trend_card,
    format_bills_summary,
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
    monkeypatch.setattr("src.services.query.service.engine", test_engine)
    monkeypatch.setattr("src.services.handlers.bill_handler.engine", test_engine)
    return test_engine


def test_bills_trend_empty_database(db_setup):
    enc = EncryptionService()
    qs = QueryService(encryption_service=enc)
    family_id = uuid4()
    ref_time = datetime.datetime(2026, 9, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)

    trend = qs.get_bills_trend_data(family_id, reference_time=ref_time, tz_name="UTC")

    assert len(trend.months) == 3
    assert [m.month for m in trend.months] == [7, 8, 9]
    assert [m.month_name for m in trend.months] == ["Jul", "Aug", "Sep"]
    assert all(not m.has_data for m in trend.months)
    assert all(m.total_amount == 0.0 for m in trend.months)
    assert all(m.delta_pct is None for m in trend.months)
    assert trend.trailing_average is None
    assert not trend.has_any_data

    # Verify badge formatting with static label and "No info"
    badge_en = format_bills_trend_badge(trend, is_spanish=False)
    assert "3-Mo Fixed:" in badge_en
    assert "Jul (No info) ➔ Aug (No info) ➔ Sep (No info)" in badge_en

    badge_es = format_bills_trend_badge(trend, is_spanish=True)
    assert "Gastos Fijos (3M):" in badge_es
    assert "Jul (Sin datos) ➔ Ago (Sin datos) ➔ Sep (Sin datos)" in badge_es


def test_bills_trend_partial_data_one_month(db_setup):
    with Session(db_setup) as session:
        family = Family(name="Trend Family", monthly_tx_count=0)
        session.add(family)
        session.commit()
        session.refresh(family)

        user = User(telegram_id=12345, full_name="Tester", family_id=family.id)
        session.add(user)
        session.commit()
        session.refresh(user)

        enc = EncryptionService()
        ref_time = datetime.datetime(2026, 9, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)

        # Only add a bill in Sep (current month)
        bill = ScheduledBill(
            family_id=family.id,
            user_id=user.id,
            amount=enc.encrypt("500.00 USD"),
            concept=enc.encrypt("Internet"),
            category="Rent/Bills",
            due_date=datetime.datetime(2026, 9, 10, 10, 0, 0, tzinfo=datetime.timezone.utc),
            status="pending"
        )
        session.add(bill)
        session.commit()

        qs = QueryService(encryption_service=enc)
        trend = qs.get_bills_trend_data(family.id, reference_time=ref_time, tz_name="UTC")

        assert len(trend.months) == 3
        # Month 1 (Jul)
        assert trend.months[0].month == 7
        assert not trend.months[0].has_data
        assert trend.months[0].delta_pct is None

        # Month 2 (Aug)
        assert trend.months[1].month == 8
        assert not trend.months[1].has_data
        assert trend.months[1].delta_pct is None

        # Month 3 (Sep)
        assert trend.months[2].month == 9
        assert trend.months[2].has_data
        assert trend.months[2].total_amount == 500.00
        assert trend.months[2].pending_amount == 500.00
        assert trend.months[2].paid_amount == 0.00
        # Delta should be suppressed because prior month (Aug) has no data
        assert trend.months[2].delta_pct is None

        assert trend.trailing_average == 500.00
        assert trend.has_any_data

        badge = format_bills_trend_badge(trend, is_spanish=False)
        assert "3-Mo Fixed:" in badge
        assert "Jul (No info) ➔ Aug (No info) ➔ Sep 500.00 USD" in badge
        assert "%" not in badge  # Delta suppressed


def test_bills_trend_full_three_months(db_setup):
    with Session(db_setup) as session:
        family = Family(name="Trend Full", monthly_tx_count=0)
        session.add(family)
        session.commit()
        session.refresh(family)

        user = User(telegram_id=98765, full_name="Tester", family_id=family.id)
        session.add(user)
        session.commit()
        session.refresh(user)

        enc = EncryptionService()
        ref_time = datetime.datetime(2026, 9, 20, 12, 0, 0, tzinfo=datetime.timezone.utc)

        # Jul: $1,000 paid
        b1 = ScheduledBill(
            family_id=family.id,
            user_id=user.id,
            amount=enc.encrypt("1000.00 USD"),
            concept=enc.encrypt("Rent Jul"),
            category="Rent/Bills",
            due_date=datetime.datetime(2026, 7, 5, 10, 0, 0, tzinfo=datetime.timezone.utc),
            status="paid"
        )
        # Aug: $1,200 paid
        b2 = ScheduledBill(
            family_id=family.id,
            user_id=user.id,
            amount=enc.encrypt("1200.00 USD"),
            concept=enc.encrypt("Rent Aug"),
            category="Rent/Bills",
            due_date=datetime.datetime(2026, 8, 5, 10, 0, 0, tzinfo=datetime.timezone.utc),
            status="paid"
        )
        # Sep: $600 paid + $800 pending = $1,400
        b3 = ScheduledBill(
            family_id=family.id,
            user_id=user.id,
            amount=enc.encrypt("600.00 USD"),
            concept=enc.encrypt("Rent Sep Part 1"),
            category="Rent/Bills",
            due_date=datetime.datetime(2026, 9, 5, 10, 0, 0, tzinfo=datetime.timezone.utc),
            status="paid"
        )
        b4 = ScheduledBill(
            family_id=family.id,
            user_id=user.id,
            amount=enc.encrypt("800.00 USD"),
            concept=enc.encrypt("Rent Sep Part 2"),
            category="Rent/Bills",
            due_date=datetime.datetime(2026, 9, 25, 10, 0, 0, tzinfo=datetime.timezone.utc),
            status="pending"
        )
        session.add_all([b1, b2, b3, b4])
        session.commit()

        qs = QueryService(encryption_service=enc)
        trend = qs.get_bills_trend_data(family.id, reference_time=ref_time, tz_name="UTC")

        assert len(trend.months) == 3
        # Jul: 1000
        assert trend.months[0].total_amount == 1000.00
        assert trend.months[0].delta_pct is None
        # Aug: 1200 -> delta from Jul is +20.0%
        assert trend.months[1].total_amount == 1200.00
        assert trend.months[1].delta_pct == 20.0
        # Sep: 1400 -> delta from Aug is +16.7%
        assert trend.months[2].total_amount == 1400.00
        assert trend.months[2].paid_amount == 600.00
        assert trend.months[2].pending_amount == 800.00
        assert round(trend.months[2].delta_pct, 1) == 16.7

        # Trailing average: (1000 + 1200 + 1400) / 3 = 1200.00
        assert trend.trailing_average == 1200.00

        badge = format_bills_trend_badge(trend, is_spanish=False)
        assert "3-Mo Fixed:" in badge
        assert "Jul 1,000.00 USD ➔ Aug 1,200.00 USD ➔ Sep 1,400.00 USD (+16.7%)" in badge

        card = format_bills_trend_card(trend, is_spanish=False)
        assert "Fixed Expenses — 3-Month Trend" in card
        assert "1,000.00 USD (100% paid" in card
        assert "1,400.00 USD (600.00 paid / 800.00 pending)" in card
        assert "Trailing Average:</b> 1,200.00 USD / mo" in card


def test_bills_trend_year_boundary(db_setup):
    enc = EncryptionService()
    qs = QueryService(encryption_service=enc)
    family_id = uuid4()
    # Reference time is Jan 10, 2027
    ref_time = datetime.datetime(2027, 1, 10, 12, 0, 0, tzinfo=datetime.timezone.utc)

    trend = qs.get_bills_trend_data(family_id, reference_time=ref_time, tz_name="UTC")

    assert len(trend.months) == 3
    # Should be Nov 2026, Dec 2026, Jan 2027
    assert (trend.months[0].year, trend.months[0].month) == (2026, 11)
    assert (trend.months[1].year, trend.months[1].month) == (2026, 12)
    assert (trend.months[2].year, trend.months[2].month) == (2027, 1)
    assert [m.month_name for m in trend.months] == ["Nov", "Dec", "Jan"]


def test_bills_trend_zero_amount_division_guard():
    # Construct synthetic trend summary where M-1 has total 0.0 and M has total 100.0
    m1 = MonthFixedCommitment(year=2026, month=7, month_name="Jul", total_amount=0.0, has_data=True)
    m2 = MonthFixedCommitment(year=2026, month=8, month_name="Aug", total_amount=0.0, has_data=True)
    m3 = MonthFixedCommitment(year=2026, month=9, month_name="Sep", total_amount=100.0, has_data=True)

    trend = BillsTrendSummary(months=[m1, m2, m3], primary_currency="USD", has_any_data=True)

    # Should not raise ZeroDivisionError and should suppress delta
    badge = format_bills_trend_badge(trend, is_spanish=False)
    assert "3-Mo Fixed:" in badge
    assert "%" not in badge


def test_format_bills_summary_with_trend_badge():
    bills = []
    badge = "📈 <b>3-Mo Fixed:</b> Jul (No info) ➔ Aug (No info) ➔ Sep 500.00 USD"

    # Empty bills with badge
    res_empty = format_bills_summary(bills, timeframe_label="This Month", trend_badge=badge)
    assert "No pending bills due for this period!" in res_empty
    assert badge in res_empty


def test_bills_trend_mixed_currency_segregation(db_setup):
    """Verifies that bills in secondary currencies are not added to primary currency total."""
    with Session(db_setup) as session:
        family = Family(name="Mixed Currency Family", default_currency="USD", monthly_tx_count=0)
        session.add(family)
        session.commit()
        session.refresh(family)

        user = User(telegram_id=55555, full_name="MultiTester", family_id=family.id)
        session.add(user)
        session.commit()
        session.refresh(user)

        enc = EncryptionService()
        ref_time = datetime.datetime(2026, 9, 20, 12, 0, 0, tzinfo=datetime.timezone.utc)

        # In Sep: 100 USD bill and 50,000 ARS bill
        b_usd = ScheduledBill(
            family_id=family.id,
            user_id=user.id,
            amount=enc.encrypt("100.00 USD"),
            concept=enc.encrypt("SaaS subscription"),
            category="Rent/Bills",
            due_date=datetime.datetime(2026, 9, 5, 10, 0, 0, tzinfo=datetime.timezone.utc),
            status="pending"
        )
        b_ars = ScheduledBill(
            family_id=family.id,
            user_id=user.id,
            amount=enc.encrypt("50000.00 ARS"),
            concept=enc.encrypt("Local utility"),
            category="Rent/Bills",
            due_date=datetime.datetime(2026, 9, 10, 10, 0, 0, tzinfo=datetime.timezone.utc),
            status="pending"
        )
        session.add_all([b_usd, b_ars])
        session.commit()

        qs = QueryService(encryption_service=enc)
        trend = qs.get_bills_trend_data(family.id, reference_time=ref_time, tz_name="UTC", primary_currency="USD")

        # Sep is the 3rd month
        sep_m = trend.months[2]
        assert sep_m.currency == "USD"
        assert sep_m.total_amount == 100.00  # ARS must NOT be summed into USD total
        assert sep_m.pending_amount == 100.00

