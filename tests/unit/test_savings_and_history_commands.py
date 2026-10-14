import pytest
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from src.db.models import User, Family
from src.services.query.models import DecryptedTransaction, QueryResult, ParsedQueryIntent
from src.services.handlers.command_handler import CommandHandler
from src.services.query.date_resolver import resolve_trailing_months
from src.services.query.aggregator import aggregate_transactions
from src.services.query.formatters import format_savings_summary, format_history_summary
from src.templates.telegram_messages import format_help_message


def test_resolve_trailing_months():
    ref_time = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
    months = resolve_trailing_months(n=3, reference_time=ref_time, tz_name="UTC")
    
    assert len(months) == 3
    # Chronological: August, September, October
    assert months[0][0] == 2026 and months[0][1] == 8
    assert months[1][0] == 2026 and months[1][1] == 9
    assert months[2][0] == 2026 and months[2][1] == 10

    # Start and end boundaries
    assert months[0][2] == datetime(2026, 8, 1, 0, 0, 0, tzinfo=timezone.utc)
    assert months[2][2] == datetime(2026, 10, 1, 0, 0, 0, tzinfo=timezone.utc)


def test_resolve_trailing_months_year_transition():
    # In January 2026, 3 trailing months should be Nov 2025, Dec 2025, Jan 2026
    ref_time = datetime(2026, 1, 10, 8, 0, 0, tzinfo=timezone.utc)
    months = resolve_trailing_months(n=3, reference_time=ref_time, tz_name="UTC")

    assert len(months) == 3
    assert months[0][0] == 2025 and months[0][1] == 11
    assert months[1][0] == 2025 and months[1][1] == 12
    assert months[2][0] == 2026 and months[2][1] == 1


def test_format_savings_summary_empty():
    qr = QueryResult(
        intent=ParsedQueryIntent(intent="net_cash_flow", timeframe="all_time", scope="family"),
        transactions=[],
        total_count=0,
        aggregation=None
    )
    en_res = format_savings_summary(qr, is_spanish=False)
    assert "Total Savings & Balance" in en_res
    assert "No transactions recorded yet." in en_res

    es_res = format_savings_summary(qr, is_spanish=True)
    assert "Ahorros y Balance Total" in es_res
    assert "No se registraron transacciones aún." in es_res


def test_format_savings_summary_single_currency():
    user_id = uuid.uuid4()
    fam_id = uuid.uuid4()
    t1 = datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 9, 15, 14, 0, tzinfo=timezone.utc)

    txs = [
        DecryptedTransaction(
            id=uuid.uuid4(), family_id=fam_id, user_id=user_id,
            amount=5000.0, currency="USD", concept="Salary",
            category="Salary", type="income", timestamp=t1
        ),
        DecryptedTransaction(
            id=uuid.uuid4(), family_id=fam_id, user_id=user_id,
            amount=3200.0, currency="USD", concept="Rent & Groceries",
            category="Rent", type="expense", timestamp=t2
        )
    ]
    agg = aggregate_transactions(txs, timeframe="all_time", primary_currency="USD", calculate_daily=False)
    qr = QueryResult(
        intent=ParsedQueryIntent(intent="net_cash_flow", timeframe="all_time", scope="family"),
        transactions=txs,
        total_count=len(txs),
        aggregation=agg
    )
    res = format_savings_summary(qr, is_spanish=False)
    assert "5,000.00 USD" in res
    assert "3,200.00 USD" in res
    assert "+1,800.00 USD" in res
    assert "36.0% saved" in res
    assert "Tracking since:" in res


def test_format_savings_summary_multi_currency_and_exchange():
    user_id = uuid.uuid4()
    fam_id = uuid.uuid4()
    now = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)

    txs = [
        DecryptedTransaction(
            id=uuid.uuid4(), family_id=fam_id, user_id=user_id,
            amount=2000.0, currency="USD", concept="Earnings",
            category="Salary", type="income", timestamp=now
        ),
        DecryptedTransaction(
            id=uuid.uuid4(), family_id=fam_id, user_id=user_id,
            amount=500.0, currency="USD", concept="Sold USD",
            category="exchange", type="expense", timestamp=now
        ),
        DecryptedTransaction(
            id=uuid.uuid4(), family_id=fam_id, user_id=user_id,
            amount=600000.0, currency="ARS", concept="Received ARS",
            category="exchange", type="income", timestamp=now
        )
    ]
    agg = aggregate_transactions(txs, timeframe="all_time", primary_currency="USD", calculate_daily=False)
    qr = QueryResult(
        intent=ParsedQueryIntent(intent="net_cash_flow", timeframe="all_time", scope="family"),
        transactions=txs,
        total_count=len(txs),
        aggregation=agg
    )
    res = format_savings_summary(qr, is_spanish=True)
    assert "Ahorros y Balance Total" in res
    assert "ARS" in res and "USD" in res
    assert "Currency Converted" in res or "Sold:" in res


def test_format_history_summary_empty():
    res = format_history_summary(
        monthly_data=[
            {"year": 2026, "month": 8, "transactions": [], "aggregation": None},
            {"year": 2026, "month": 9, "transactions": [], "aggregation": None},
            {"year": 2026, "month": 10, "transactions": [], "aggregation": None}
        ],
        is_spanish=False
    )
    assert "3-Month Financial History" in res
    assert "No transactions recorded in the last 3 months." in res


def test_format_history_summary_populated():
    user_id = uuid.uuid4()
    fam_id = uuid.uuid4()
    t_aug = datetime(2026, 8, 10, 10, 0, tzinfo=timezone.utc)
    t_sep = datetime(2026, 9, 12, 10, 0, tzinfo=timezone.utc)
    t_oct = datetime(2026, 10, 5, 10, 0, tzinfo=timezone.utc)

    tx_aug = [
        DecryptedTransaction(id=uuid.uuid4(), family_id=fam_id, user_id=user_id, amount=1000.0, currency="USD", concept="Salary", category="Salary", type="income", timestamp=t_aug),
        DecryptedTransaction(id=uuid.uuid4(), family_id=fam_id, user_id=user_id, amount=800.0, currency="USD", concept="Food", category="Food", type="expense", timestamp=t_aug),
    ]
    tx_sep = [
        DecryptedTransaction(id=uuid.uuid4(), family_id=fam_id, user_id=user_id, amount=1200.0, currency="USD", concept="Salary", category="Salary", type="income", timestamp=t_sep),
        DecryptedTransaction(id=uuid.uuid4(), family_id=fam_id, user_id=user_id, amount=1000.0, currency="USD", concept="Rent", category="Rent", type="expense", timestamp=t_sep),
    ]
    tx_oct = [
        DecryptedTransaction(id=uuid.uuid4(), family_id=fam_id, user_id=user_id, amount=300.0, currency="USD", concept="Freelance", category="Freelance", type="income", timestamp=t_oct),
        DecryptedTransaction(id=uuid.uuid4(), family_id=fam_id, user_id=user_id, amount=50.0, currency="USD", concept="Dinner", category="Food", type="expense", timestamp=t_oct),
    ]
    all_txs = tx_aug + tx_sep + tx_oct

    agg_aug = aggregate_transactions(tx_aug, timeframe="2026_08", primary_currency="USD", calculate_daily=False)
    agg_sep = aggregate_transactions(tx_sep, timeframe="2026_09", primary_currency="USD", calculate_daily=False)
    agg_oct = aggregate_transactions(tx_oct, timeframe="2026_10", primary_currency="USD", calculate_daily=False)
    overall_agg = aggregate_transactions(all_txs, timeframe="3_months", primary_currency="USD", calculate_daily=False)

    monthly_data = [
        {"year": 2026, "month": 8, "transactions": tx_aug, "aggregation": agg_aug},
        {"year": 2026, "month": 9, "transactions": tx_sep, "aggregation": agg_sep},
        {"year": 2026, "month": 10, "transactions": tx_oct, "aggregation": agg_oct},
    ]

    res = format_history_summary(
        monthly_data=monthly_data,
        overall_agg=overall_agg,
        is_spanish=False,
        primary_currency="USD"
    )
    assert "August 2026" in res
    assert "September 2026" in res
    assert "October 2026</b> (Current)" in res
    assert "3-Month Trailing Totals:" in res
    assert "Total Incomes: 2,500.00 USD" in res or "2,500.00 USD" in res


@pytest.mark.anyio
async def test_handle_savings_command():
    handler = CommandHandler()
    user = User(id=uuid.uuid4(), telegram_id=123, full_name="Tony Crespo", family_id=uuid.uuid4())
    family = Family(id=user.family_id, name="Crespo Household", default_currency="USD")

    now = datetime.now(timezone.utc)
    mock_txs = [
        DecryptedTransaction(
            id=uuid.uuid4(), family_id=family.id, user_id=user.id,
            amount=4000.0, currency="USD", concept="Job",
            category="Salary", type="income", timestamp=now
        ),
        DecryptedTransaction(
            id=uuid.uuid4(), family_id=family.id, user_id=user.id,
            amount=1500.0, currency="USD", concept="Rent",
            category="Housing", type="expense", timestamp=now
        )
    ]

    with patch.object(handler.query_service, "_fetch_and_decrypt_transactions", return_value=mock_txs):
        # Household
        res = await handler.handle_savings(user, family, args="")
        assert "Total Savings & Balance" in res
        assert "+2,500.00 USD" in res

        # Personal (/savings me)
        res_me = await handler.handle_savings(user, family, args="me")
        assert "Tony Crespo" in res_me or "Personal" in res_me

        # Spanish (/ahorros)
        res_es = await handler.handle_savings(user, family, args="", is_spanish=True)
        assert "Ahorros y Balance Total" in res_es


@pytest.mark.anyio
async def test_handle_history_command():
    handler = CommandHandler()
    user = User(id=uuid.uuid4(), telegram_id=123, full_name="Tony", family_id=uuid.uuid4())
    family = Family(id=user.family_id, name="Family", default_currency="USD")

    now = datetime.now(timezone.utc)
    mock_txs = [
        DecryptedTransaction(
            id=uuid.uuid4(), family_id=family.id, user_id=user.id,
            amount=500.0, currency="USD", concept="Groceries",
            category="Food", type="expense", timestamp=now
        )
    ]

    with patch.object(handler.query_service, "_fetch_and_decrypt_transactions", return_value=mock_txs):
        res = await handler.handle_history(user, family, args="")
        assert "3-Month Financial History" in res
        assert "500.00 USD" in res

        res_es = await handler.handle_history(user, family, args="", is_spanish=True)
        assert "Historial Financiero — 3 Meses" in res_es


def test_format_help_message_contains_new_commands():
    help_en = format_help_message(is_spanish=False)
    assert "/savings" in help_en
    assert "/history" in help_en

    help_es = format_help_message(is_spanish=True)
    assert "/savings" in help_es
    assert "/history" in help_es


@pytest.mark.anyio
async def test_parse_intent_savings_natural_language_queries():
    from src.services.query.service import QueryService
    qs = QueryService()

    # The exact query from user experience
    pi1 = await qs.parse_intent("cuantos USD tengo en este momento en total?")
    assert pi1.intent == "savings_summary"
    assert pi1.timeframe == "all_time"
    assert pi1.target_currency == "USD"
    assert pi1.scope == "personal"

    # Household all-time query
    pi2 = await qs.parse_intent("cuanto dinero tenemos en total?")
    assert pi2.intent == "savings_summary"
    assert pi2.timeframe == "all_time"
    assert pi2.scope == "family"

    # English query with currency
    pi3 = await qs.parse_intent("how many dollars do I have right now in total?")
    assert pi3.intent == "savings_summary"
    assert pi3.timeframe == "all_time"
    assert pi3.target_currency == "USD"


def test_format_savings_summary_target_currency_highlight():
    fam_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    txs = [
        DecryptedTransaction(
            id=uuid.uuid4(), family_id=fam_id, user_id=uuid.uuid4(),
            amount=500.0, currency="USD", concept="Freelance", category="Salary", type="income", timestamp=now
        ),
        DecryptedTransaction(
            id=uuid.uuid4(), family_id=fam_id, user_id=uuid.uuid4(),
            amount=50000.0, currency="ARS", concept="Side gig", category="Salary", type="income", timestamp=now
        )
    ]
    agg = aggregate_transactions(txs, timeframe="all_time", primary_currency="USD")
    qr = QueryResult(
        intent=ParsedQueryIntent(intent="savings_summary", timeframe="all_time", target_currency="USD"),
        transactions=txs, total_count=2, aggregation=agg
    )
    res_es = format_savings_summary(qr, is_spanish=True, target_currency="USD")
    assert "Saldo Total en USD:" in res_es
    assert "+500.00 USD" in res_es


@pytest.mark.anyio
async def test_query_service_get_savings_summary():
    from src.services.query.service import QueryService
    qs = QueryService()
    fam_id = uuid.uuid4()
    user_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    mock_txs = [
        DecryptedTransaction(
            id=uuid.uuid4(), family_id=fam_id, user_id=user_id,
            amount=1000.0, currency="USD", concept="Deposit", category="Salary", type="income", timestamp=now
        )
    ]

    with patch.object(qs, "_fetch_and_decrypt_transactions", return_value=mock_txs):
        res = await qs.get_savings_summary(
            family_id=fam_id,
            user_id=user_id,
            user_name="Tony",
            target_currency="USD",
            is_spanish=True
        )
        assert "Ahorros y Balance Total" in res
        assert "Saldo Total en USD:" in res
        assert "+1,000.00 USD" in res

