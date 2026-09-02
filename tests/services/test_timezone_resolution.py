import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool
from timezonefinder import TimezoneFinder

from src.core.config import settings
from src.db.models import Family, User, Transaction
from src.services.family_service import FamilyService
from src.services.handlers.command_handler import CommandHandler
from src.services.query.date_resolver import (
    resolve_date_range,
    validate_and_normalize_timezone,
    TIMEZONE_ALIASES,
    OFFSET_ALIASES
)
from src.services.query.formatters import (
    format_timezone_footer,
    format_today_summary,
    format_month_summary,
    format_me_summary,
    format_balance_summary,
    format_bills_summary
)
from src.services.query.models import QueryResult, ParsedQueryIntent


@pytest.fixture
def in_memory_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    FamilyService._instance = None
    service = FamilyService(engine=engine)
    yield engine, service
    SQLModel.metadata.drop_all(engine)
    FamilyService._instance = None


def test_timezone_normalization():
    assert validate_and_normalize_timezone("Buenos Aires") == "America/Argentina/Buenos_Aires"
    assert validate_and_normalize_timezone("buenos aires") == "America/Argentina/Buenos_Aires"
    assert validate_and_normalize_timezone("madrid") == "Europe/Madrid"
    assert validate_and_normalize_timezone("Spain") == "Europe/Madrid"
    assert validate_and_normalize_timezone("-3") == "America/Argentina/Buenos_Aires"
    assert validate_and_normalize_timezone("UTC-3") == "America/Argentina/Buenos_Aires"
    assert validate_and_normalize_timezone("+1") == "Europe/Madrid"
    assert validate_and_normalize_timezone("America/Argentina/Buenos_Aires") == "America/Argentina/Buenos_Aires"
    assert validate_and_normalize_timezone("Europe/Madrid") == "Europe/Madrid"
    assert validate_and_normalize_timezone("Invalid/Non_Existent_Timezone") is None
    assert validate_and_normalize_timezone(None) is None
    assert validate_and_normalize_timezone("") is None


def test_timezone_finder_offline_coords():
    tf = TimezoneFinder()
    # Buenos Aires, Argentina
    assert tf.timezone_at(lat=-34.6037, lng=-58.3816) == "America/Argentina/Buenos_Aires"
    # Madrid, Spain
    assert tf.timezone_at(lat=40.4168, lng=-3.7038) == "Europe/Madrid"
    # New York, USA
    assert tf.timezone_at(lat=40.7128, lng=-74.0060) == "America/New_York"


def test_argentina_late_night_today_query():
    """
    Forensic scenario reproduction:
    User is in Argentina (UTC-3).
    Logs lunch at 12:59 local (15:59:55 UTC).
    Queries /today at 22:06 local (next day 01:06:00 UTC).
    """
    # 22:06 local in Buenos Aires is 01:06 UTC next day (2026-09-02)
    query_time_utc = datetime(2026, 9, 2, 1, 6, 0, tzinfo=timezone.utc)
    lunch_time_utc = datetime(2026, 9, 1, 15, 59, 55, tzinfo=timezone.utc)

    # With tz_name="America/Argentina/Buenos_Aires"
    start_utc, end_utc = resolve_date_range(
        "today",
        reference_time=query_time_utc,
        tz_name="America/Argentina/Buenos_Aires"
    )

    # Local day 2026-09-01 runs from 03:00 UTC (2026-09-01) to 02:59:59.999999 UTC (2026-09-02)
    assert start_utc == datetime(2026, 9, 1, 3, 0, 0, tzinfo=timezone.utc)
    assert end_utc == datetime(2026, 9, 2, 2, 59, 59, 999999, tzinfo=timezone.utc)

    # The 15:59 UTC transaction MUST be inside the window!
    assert start_utc <= lunch_time_utc <= end_utc


def test_yesterday_timezone_window():
    # 22:06 local in Buenos Aires on Sept 1 is 01:06 UTC Sept 2
    query_time_utc = datetime(2026, 9, 2, 1, 6, 0, tzinfo=timezone.utc)
    start_utc, end_utc = resolve_date_range(
        "yesterday",
        reference_time=query_time_utc,
        tz_name="America/Argentina/Buenos_Aires"
    )

    # Yesterday in local time was 2026-08-31
    assert start_utc == datetime(2026, 8, 31, 3, 0, 0, tzinfo=timezone.utc)
    assert end_utc == datetime(2026, 9, 1, 2, 59, 59, 999999, tzinfo=timezone.utc)


def test_formatters_contain_timezone_footer():
    footer = format_timezone_footer("America/Argentina/Buenos_Aires")
    assert "💡 <i>Active timezone: America/Argentina/Buenos_Aires. Change with /timezone</i>" in footer

    # Empty today summary
    qr_empty = QueryResult(
        intent=ParsedQueryIntent(intent="spending_summary", timeframe="today"),
        total_count=0,
        transactions=[]
    )
    today_text = format_today_summary(qr_empty, is_family=True, tz_name="America/Argentina/Buenos_Aires")
    assert "Active timezone: America/Argentina/Buenos_Aires" in today_text
    assert "/timezone" in today_text

    # Empty month summary
    month_text = format_month_summary(qr_empty, family_name="Clan Test", tz_name="Europe/Madrid")
    assert "Active timezone: Europe/Madrid" in month_text

    # Empty me summary
    me_text = format_me_summary(qr_empty, user_name="Tony", tz_name="America/Santiago")
    assert "Active timezone: America/Santiago" in me_text

    # Empty bills summary
    bills_text = format_bills_summary([], tz_name="America/Bogota")
    assert "Active timezone: America/Bogota" in bills_text

    # Empty balance summary
    balance_text = format_balance_summary(qr_empty, tz_name="UTC")
    assert "Active timezone: UTC" in balance_text


@pytest.mark.anyio
async def test_command_handler_timezone_resolution_cascade(in_memory_db):
    engine, family_service = in_memory_db
    handler = CommandHandler()

    user = User(id=uuid4(), telegram_id=111, full_name="Tony", timezone=None)
    family = Family(id=uuid4(), name="Household", timezone=None)

    # Cascade 1: Both None -> DEFAULT_TIMEZONE
    assert handler._resolve_active_timezone(user, family) == "America/Argentina/Buenos_Aires"

    # Cascade 2: Family set -> Family timezone
    family.timezone = "America/Santiago"
    assert handler._resolve_active_timezone(user, family) == "America/Santiago"

    # Cascade 3: User set -> User timezone overrides Family
    user.timezone = "Europe/Madrid"
    assert handler._resolve_active_timezone(user, family) == "Europe/Madrid"


@pytest.mark.anyio
async def test_command_handler_handle_timezone_command(in_memory_db):
    engine, family_service = in_memory_db
    handler = CommandHandler()

    with Session(engine) as session:
        family = Family(id=uuid4(), name="Household", timezone="America/Argentina/Buenos_Aires")
        user = User(id=uuid4(), telegram_id=123, family_id=family.id, full_name="Tony", is_admin=True)
        member = User(id=uuid4(), telegram_id=456, family_id=family.id, full_name="Maria", is_admin=False)
        session.add_all([family, user, member])
        session.commit()
        session.refresh(family)
        session.refresh(user)
        session.refresh(member)

    # 1. Inspect without args
    info = await handler.handle_timezone(user, family, "")
    assert "Timezone Settings" in info
    assert "America/Argentina/Buenos_Aires" in info
    assert "/timezone" in info

    # 2. Update personal timezone
    res = await handler.handle_timezone(user, family, "Madrid")
    assert "Personal Timezone Updated!" in res
    assert "Europe/Madrid" in res
    assert user.timezone == "Europe/Madrid"

    # 3. Non-admin trying to update household timezone
    res_forbidden = await handler.handle_timezone(member, family, "--household Madrid")
    assert "Only household administrators" in res_forbidden

    # 4. Admin updating household timezone
    res_admin = await handler.handle_timezone(user, family, "--household Mexico City")
    assert "Household Default Timezone Updated!" in res_admin
    assert "America/Mexico_City" in res_admin

    # 5. Invalid timezone name
    res_invalid = await handler.handle_timezone(user, family, "Atlantis/Narnia")
    assert "Unrecognized timezone" in res_invalid
