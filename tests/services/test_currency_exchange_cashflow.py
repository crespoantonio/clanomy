import pytest
from datetime import datetime, timezone
from uuid import uuid4

from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy.pool import StaticPool
from src.db.models import User, Family, Transaction
from src.core.encryption import EncryptionService
from src.services.handlers.transaction_handler import get_monthly_cash_flow_snapshot
from src.services.query.models import DecryptedTransaction, QueryResult, ParsedQueryIntent
from src.services.query.aggregator import (
    aggregate_transactions,
    aggregate_by_category,
    aggregate_by_member,
)
from src.services.query.formatters import (
    format_month_summary,
    format_me_summary,
    format_balance_summary,
)


@pytest.fixture
def setup_db():
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    SQLModel.metadata.create_all(test_engine)
    yield test_engine


def test_monthly_cash_flow_snapshot_excludes_currency_exchange(setup_db):
    """
    Verifies that dual-leg currency exchange transactions do NOT distort monthly cash flow.
    - USD salary: +$1,000 USD
    - Exchange: -200 USD -> +345,999 ARS
    - ARS grocery expense: -$45,999 ARS
    """
    enc = EncryptionService()
    family_id = uuid4()
    user_id = uuid4()
    target_date = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)

    with Session(setup_db) as session:
        fam = Family(id=family_id, name="Tony's Family", plan_type="family_pro", default_currency="ARS")
        user = User(id=user_id, telegram_id=7777, family_id=family_id, username="tony", full_name="Tony Crespo")
        session.add(fam)
        session.add(user)

        # 1. Salary in USD
        tx_salary = Transaction(
            family_id=family_id,
            user_id=user_id,
            amount=enc.encrypt("1000.0 USD"),
            concept=enc.encrypt("Salary"),
            category="Salary",
            timestamp=target_date,
            type="income"
        )
        session.add(tx_salary)

        # 2. Exchange leg 1: 200 USD expense
        tx_ex_usd = Transaction(
            family_id=family_id,
            user_id=user_id,
            amount=enc.encrypt("200.0 USD"),
            concept=enc.encrypt("Currency Exchange"),
            category="Exchange",
            timestamp=target_date,
            type="expense"
        )
        session.add(tx_ex_usd)

        # 3. Exchange leg 2: 345,999 ARS income
        tx_ex_ars = Transaction(
            family_id=family_id,
            user_id=user_id,
            amount=enc.encrypt("345999.0 ARS"),
            concept=enc.encrypt("Currency Exchange"),
            category="Exchange",
            timestamp=target_date,
            type="income"
        )
        session.add(tx_ex_ars)

        # 4. Expense in ARS: 45,999 ARS on groceries
        tx_groceries = Transaction(
            family_id=family_id,
            user_id=user_id,
            amount=enc.encrypt("45999.0 ARS"),
            concept=enc.encrypt("Supermercado"),
            category="Food/Drink",
            timestamp=target_date,
            type="expense"
        )
        session.add(tx_groceries)
        session.commit()

    # Verify USD snapshot:
    # Total In must be 1,000 USD (Salary only, exchange ignored).
    # Total Out must be 0 USD (Exchange ignored).
    # Net savings must be 1,000 USD (100% saved).
    usd_snapshot = get_monthly_cash_flow_snapshot(
        family_id=family_id,
        target_date=target_date,
        primary_currency="USD",
        encryption_service=enc,
        session_factory=lambda eng: Session(setup_db)
    )
    assert usd_snapshot["total_in"] == 1000.0
    assert usd_snapshot["total_out"] == 0.0
    assert usd_snapshot["net_savings"] == 1000.0
    assert usd_snapshot["savings_pct"] == 100

    # Verify ARS snapshot:
    # Total In must be 0 ARS (Exchange ignored, not counted as income).
    # Total Out must be 45,999 ARS (Groceries only).
    # Net savings must be -45,999 ARS.
    ars_snapshot = get_monthly_cash_flow_snapshot(
        family_id=family_id,
        target_date=target_date,
        primary_currency="ARS",
        encryption_service=enc,
        session_factory=lambda eng: Session(setup_db)
    )
    assert ars_snapshot["total_in"] == 0.0
    assert ars_snapshot["total_out"] == 45999.0
    assert ars_snapshot["net_savings"] == -45999.0


def test_aggregate_transactions_excludes_exchange_from_operational_totals():
    family_id = uuid4()
    user_id = uuid4()
    ts = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)

    transactions = [
        # USD salary
        DecryptedTransaction(
            id=uuid4(), family_id=family_id, user_id=user_id,
            amount=1000.0, currency="USD", concept="Salary", category="Salary",
            type="income", timestamp=ts
        ),
        # Exchange leg 1 (sold USD)
        DecryptedTransaction(
            id=uuid4(), family_id=family_id, user_id=user_id,
            amount=200.0, currency="USD", concept="Currency Exchange", category="Exchange",
            type="expense", timestamp=ts
        ),
        # Exchange leg 2 (received ARS)
        DecryptedTransaction(
            id=uuid4(), family_id=family_id, user_id=user_id,
            amount=345999.0, currency="ARS", concept="Currency Exchange", category="Exchange",
            type="income", timestamp=ts
        ),
        # ARS groceries
        DecryptedTransaction(
            id=uuid4(), family_id=family_id, user_id=user_id,
            amount=50000.0, currency="ARS", concept="Coto", category="Food/Drink",
            type="expense", timestamp=ts
        ),
    ]

    # Aggregate with primary_currency="ARS"
    agg_ars = aggregate_transactions(transactions, "this_month", primary_currency="ARS")
    assert agg_ars.total_income == 0.0  # 345,999 ARS exchange not counted as income
    assert agg_ars.total_expenses == 50000.0
    assert agg_ars.net_balance == -50000.0
    assert agg_ars.income_currency_totals == {"USD": 1000.0}
    assert "ARS" not in agg_ars.income_currency_totals
    assert agg_ars.expense_currency_totals == {"ARS": 50000.0}
    assert "USD" not in agg_ars.expense_currency_totals
    assert agg_ars.exchange_count == 2
    assert agg_ars.exchange_sold_totals == {"USD": 200.0}
    assert agg_ars.exchange_received_totals == {"ARS": 345999.0}
    assert agg_ars.net_currency_positions == {"USD": 800.0, "ARS": 295999.0}
    assert "Exchange" not in agg_ars.expense_category_breakdown
    assert "Exchange" not in agg_ars.income_category_breakdown

    # Aggregate with primary_currency="USD"
    agg_usd = aggregate_transactions(transactions, "this_month", primary_currency="USD")
    assert agg_usd.total_income == 1000.0
    assert agg_usd.total_expenses == 0.0  # 200 USD exchange not counted as expense
    assert agg_usd.net_balance == 1000.0
    assert agg_usd.savings_rate == 100.0
    assert agg_usd.income_currency_totals == {"USD": 1000.0}
    assert agg_usd.expense_currency_totals == {"ARS": 50000.0}
    assert agg_usd.exchange_count == 2
    assert agg_usd.exchange_sold_totals == {"USD": 200.0}
    assert agg_usd.exchange_received_totals == {"ARS": 345999.0}
    assert agg_usd.net_currency_positions == {"USD": 800.0, "ARS": 295999.0}


def test_aggregate_by_category_excludes_exchange_from_spending():
    family_id = uuid4()
    user_id = uuid4()
    ts = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)

    transactions = [
        DecryptedTransaction(
            id=uuid4(), family_id=family_id, user_id=user_id,
            amount=100.0, currency="USD", concept="Dinner", category="Food/Drink",
            type="expense", timestamp=ts
        ),
        DecryptedTransaction(
            id=uuid4(), family_id=family_id, user_id=user_id,
            amount=500.0, currency="USD", concept="Currency Exchange", category="Exchange",
            type="expense", timestamp=ts
        ),
    ]

    cb = aggregate_by_category(transactions, "this_month", primary_currency="USD")
    # Top category must be Food/Drink, not Exchange!
    assert cb.top_category == "Food/Drink"
    assert cb.top_category_amount == 100.0
    assert "Exchange" not in cb.categories
    assert cb.total_spending == 100.0


def test_aggregate_by_member_excludes_exchange_from_operational():
    family_id = uuid4()
    user_id = uuid4()
    ts = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)

    transactions = [
        DecryptedTransaction(
            id=uuid4(), family_id=family_id, user_id=user_id, user_name="Tony",
            amount=100.0, currency="USD", concept="Lunch", category="Food/Drink",
            type="expense", timestamp=ts
        ),
        DecryptedTransaction(
            id=uuid4(), family_id=family_id, user_id=user_id, user_name="Tony",
            amount=500.0, currency="USD", concept="Currency Exchange", category="Exchange",
            type="expense", timestamp=ts
        ),
    ]

    mb = aggregate_by_member(transactions, "this_month", primary_currency="USD")
    tony = next(iter(mb.members.values()))
    assert tony.total_spent == 100.0  # Exchange 500 USD excluded
    assert tony.total_earned == 0.0
    assert tony.net_balance == -100.0
    assert tony.top_category == "Food/Drink"
    assert tony.exchange_sold_totals == {"USD": 500.0}
    assert tony.net_currency_positions == {"USD": -600.0}


def test_format_month_summary_includes_currency_exchange():
    family_id = uuid4()
    user_id = uuid4()
    ts = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)

    transactions = [
        DecryptedTransaction(
            id=uuid4(), family_id=family_id, user_id=user_id, user_name="Tony",
            amount=1000.0, currency="USD", concept="Salary", category="Salary",
            type="income", timestamp=ts
        ),
        DecryptedTransaction(
            id=uuid4(), family_id=family_id, user_id=user_id, user_name="Tony",
            amount=200.0, currency="USD", concept="Currency Exchange", category="Exchange",
            type="expense", timestamp=ts
        ),
        DecryptedTransaction(
            id=uuid4(), family_id=family_id, user_id=user_id, user_name="Tony",
            amount=345999.0, currency="ARS", concept="Currency Exchange", category="Exchange",
            type="income", timestamp=ts
        ),
        DecryptedTransaction(
            id=uuid4(), family_id=family_id, user_id=user_id, user_name="Tony",
            amount=45999.0, currency="ARS", concept="Groceries", category="Food/Drink",
            type="expense", timestamp=ts
        ),
    ]

    agg = aggregate_transactions(transactions, "this_month", primary_currency="USD")
    mb = aggregate_by_member(transactions, "this_month", primary_currency="USD")
    qr = QueryResult(
        intent=ParsedQueryIntent(intent="spending_summary", timeframe="this_month", scope="family"),
        transactions=transactions,
        total_count=len(transactions),
        aggregation=agg,
        member_breakdown=mb
    )

    summary = format_month_summary(qr, family_name="Tony's Family", timeframe_label="September 2026")
    assert "Currency Converted:" in summary
    assert "Sold: 200.00 USD ➔ Received: 345,999.00 ARS" in summary
    assert "Net Family Position:" in summary
    assert "+800.00 USD" in summary
    assert "+300,000.00 ARS" in summary
    assert "1,000.00 USD" in summary  # Household Income
    assert "45,999.00 ARS" in summary  # Household Expenses
    # Verify member breakdown does NOT show individual Net or Converted
    mb_section = summary[summary.find("Member Breakdown"):]
    assert "Converted:" not in mb_section
    assert "Net:" not in mb_section
    assert "Incomes:" in mb_section
    assert "Expenses:" in mb_section


def test_format_me_summary_includes_currency_exchange():
    family_id = uuid4()
    user_id = uuid4()
    ts = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)

    transactions = [
        DecryptedTransaction(
            id=uuid4(), family_id=family_id, user_id=user_id, user_name="Tony",
            amount=1000.0, currency="USD", concept="Salary", category="Salary",
            type="income", timestamp=ts
        ),
        DecryptedTransaction(
            id=uuid4(), family_id=family_id, user_id=user_id, user_name="Tony",
            amount=200.0, currency="USD", concept="Currency Exchange", category="Exchange",
            type="expense", timestamp=ts
        ),
        DecryptedTransaction(
            id=uuid4(), family_id=family_id, user_id=user_id, user_name="Tony",
            amount=345999.0, currency="ARS", concept="Currency Exchange", category="Exchange",
            type="income", timestamp=ts
        ),
        DecryptedTransaction(
            id=uuid4(), family_id=family_id, user_id=user_id, user_name="Tony",
            amount=45999.0, currency="ARS", concept="Groceries", category="Food/Drink",
            type="expense", timestamp=ts
        ),
    ]

    agg = aggregate_transactions(transactions, "this_month", primary_currency="USD")
    cb = aggregate_by_category(transactions, "this_month", primary_currency="USD")
    qr = QueryResult(
        intent=ParsedQueryIntent(intent="spending_summary", timeframe="this_month", scope="personal"),
        transactions=transactions,
        total_count=len(transactions),
        aggregation=agg,
        category_breakdown=cb
    )

    me_summary = format_me_summary(qr, user_name="Tony", timeframe_label="September 2026")
    assert "Currency Converted:" in me_summary
    assert "Sold: 200.00 USD ➔ Received: 345,999.00 ARS" in me_summary
    assert "Net Cash Position:" in me_summary
    assert "+800.00 USD" in me_summary
    assert "+300,000.00 ARS" in me_summary
    assert "Top Categories:" in me_summary
    assert "Food/Drink" in me_summary


def test_format_balance_summary_includes_currency_exchange():
    family_id = uuid4()
    user_id = uuid4()
    ts = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)

    transactions = [
        DecryptedTransaction(
            id=uuid4(), family_id=family_id, user_id=user_id, user_name="Tony",
            amount=1000.0, currency="USD", concept="Salary", category="Salary",
            type="income", timestamp=ts
        ),
        DecryptedTransaction(
            id=uuid4(), family_id=family_id, user_id=user_id, user_name="Tony",
            amount=200.0, currency="USD", concept="Currency Exchange", category="Exchange",
            type="expense", timestamp=ts
        ),
        DecryptedTransaction(
            id=uuid4(), family_id=family_id, user_id=user_id, user_name="Tony",
            amount=345999.0, currency="ARS", concept="Currency Exchange", category="Exchange",
            type="income", timestamp=ts
        ),
    ]

    agg = aggregate_transactions(transactions, "this_month", primary_currency="USD")
    qr = QueryResult(
        intent=ParsedQueryIntent(intent="net_cash_flow", timeframe="this_month", scope="family"),
        transactions=transactions,
        total_count=len(transactions),
        aggregation=agg
    )

    bal_summary = format_balance_summary(qr)
    assert "Currency Converted:" in bal_summary
    assert "Sold: 200.00 USD ➔ Received: 345,999.00 ARS" in bal_summary
    assert "Net Family Position:" in bal_summary
    assert "+800.00 USD" in bal_summary
    assert "+345,999.00 ARS" in bal_summary
