import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from sqlmodel import Session, SQLModel, create_engine, select
from sqlalchemy.pool import StaticPool

from src.db.models import Family, User, Transaction
from src.services.notification_scheduler import (
    NotificationScheduler,
    get_day_50_trial_families,
    get_day_60_trial_families,
    format_day_50_message,
    format_day_60_message,
    process_day_50_notifications,
    process_day_60_notifications,
    run_daily_trial_notifications,
    start_notification_scheduler,
    stop_notification_scheduler,
)

class MockTelegramService:
    def __init__(self):
        self.sent_messages = []

    async def send_message(self, chat_id: int, text: str) -> None:
        self.sent_messages.append({"chat_id": chat_id, "text": text})

@pytest.fixture
def memory_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session

def test_get_day_50_trial_families_query_filtering(memory_session):
    now = datetime(2026, 8, 26, 12, 0, 0, tzinfo=timezone.utc)

    # 1. Candidate: trial ends in 5 days, not notified
    fam_candidate_5d = Family(
        name="Candidate 5d",
        plan_type="trial",
        trial_ends_at=now + timedelta(days=5),
        notified_day_50=False,
        notified_day_60=False
    )
    # 2. Candidate: trial ends in exactly 10 days, not notified
    fam_candidate_10d = Family(
        name="Candidate 10d",
        plan_type="trial",
        trial_ends_at=now + timedelta(days=10),
        notified_day_50=False,
        notified_day_60=False
    )
    # 3. Excluded: trial ends in 20 days (Day 40)
    fam_future_20d = Family(
        name="Future 20d",
        plan_type="trial",
        trial_ends_at=now + timedelta(days=20),
        notified_day_50=False,
        notified_day_60=False
    )
    # 4. Excluded: already notified for day 50
    fam_already_notified = Family(
        name="Already Notified 50",
        plan_type="trial",
        trial_ends_at=now + timedelta(days=5),
        notified_day_50=True,
        notified_day_60=False
    )
    # 5. Excluded: trial already expired (trial_ends_at <= now, belongs to Day 60)
    fam_expired = Family(
        name="Expired Trial",
        plan_type="trial",
        trial_ends_at=now - timedelta(days=1),
        notified_day_50=False,
        notified_day_60=False
    )
    # 6. Excluded: paid plan
    fam_paid = Family(
        name="Paid Plan",
        plan_type="solo_pro",
        trial_ends_at=now + timedelta(days=5),
        notified_day_50=False
    )

    memory_session.add_all([
        fam_candidate_5d,
        fam_candidate_10d,
        fam_future_20d,
        fam_already_notified,
        fam_expired,
        fam_paid
    ])
    memory_session.commit()

    candidates = get_day_50_trial_families(memory_session, now=now)
    candidate_ids = {f.id for f in candidates}

    assert candidate_ids == {fam_candidate_5d.id, fam_candidate_10d.id}

def test_get_day_60_trial_families_query_filtering(memory_session):
    now = datetime(2026, 8, 26, 12, 0, 0, tzinfo=timezone.utc)

    # 1. Candidate: trial expired yesterday, plan is trial, not notified
    fam_expired_1 = Family(
        name="Expired Yesterday",
        plan_type="trial",
        trial_ends_at=now - timedelta(days=1),
        notified_day_50=True,
        notified_day_60=False
    )
    # 2. Candidate: trial expired exactly now, plan is trial, not notified
    fam_expired_now = Family(
        name="Expired Exactly Now",
        plan_type="trial",
        trial_ends_at=now,
        notified_day_50=False,
        notified_day_60=False
    )
    # 3. Excluded: trial still active (ends in 2 days)
    fam_active_trial = Family(
        name="Active Trial",
        plan_type="trial",
        trial_ends_at=now + timedelta(days=2),
        notified_day_60=False
    )
    # 4. Excluded: already notified for day 60
    fam_already_notified_60 = Family(
        name="Already Notified 60",
        plan_type="trial",
        trial_ends_at=now - timedelta(days=2),
        notified_day_60=True
    )
    # 5. Excluded: upgraded to Solo Pro
    fam_solo_pro = Family(
        name="Upgraded Solo Pro",
        plan_type="solo_pro",
        trial_ends_at=now - timedelta(days=2),
        notified_day_60=False
    )
    # 6. Excluded: upgraded to Family Pro
    fam_family_pro = Family(
        name="Upgraded Family Pro",
        plan_type="family_pro",
        trial_ends_at=now - timedelta(days=2),
        notified_day_60=False
    )
    # 7. Excluded: Lifetime Pro
    fam_lifetime_pro = Family(
        name="Lifetime Pro",
        plan_type="lifetime_pro",
        trial_ends_at=now - timedelta(days=2),
        notified_day_60=False
    )

    memory_session.add_all([
        fam_expired_1,
        fam_expired_now,
        fam_active_trial,
        fam_already_notified_60,
        fam_solo_pro,
        fam_family_pro,
        fam_lifetime_pro
    ])
    memory_session.commit()

    candidates = get_day_60_trial_families(memory_session, now=now)
    candidate_ids = {f.id for f in candidates}

    assert candidate_ids == {fam_expired_1.id, fam_expired_now.id}

def test_format_day_50_message_content():
    family = Family(name="Smith Family", plan_type="trial")
    
    # Check with 42 transactions
    msg = format_day_50_message(family, tx_count=42, days_remaining=10)
    assert "42" in msg
    assert "10 Days" in msg
    assert "Family Pro" in msg
    assert "300" in msg
    assert "Solo Pro" in msg
    assert "150" in msg
    assert "/upgrade" in msg

    # Check with 0 transactions
    msg_zero = format_day_50_message(family, tx_count=0, days_remaining=10)
    assert "0" in msg_zero
    assert "10 Days" in msg_zero
    assert "/upgrade" in msg_zero

def test_format_day_60_message_content():
    family = Family(name="Smith Family", plan_type="trial")
    
    msg = format_day_60_message(family)
    assert "safe" in msg.lower()
    assert "30" in msg
    assert "/upgrade" in msg
    assert "Free" in msg or "free" in msg

@pytest.mark.anyio
async def test_process_day_50_notifications_lifecycle(memory_session):
    now = datetime(2026, 8, 26, 12, 0, 0, tzinfo=timezone.utc)
    mock_telegram = MockTelegramService()

    fam = Family(
        name="Miller Household",
        plan_type="trial",
        trial_ends_at=now + timedelta(days=5),
        notified_day_50=False,
        notified_day_60=False
    )
    memory_session.add(fam)
    memory_session.flush()

    user1 = User(telegram_id=11111, family_id=fam.id, is_admin=True)
    user2 = User(telegram_id=22222, family_id=fam.id, is_admin=False)

    tx1 = Transaction(family_id=fam.id, user_id=user1.id, amount="enc1", concept="enc1", category="Food")
    tx2 = Transaction(family_id=fam.id, user_id=user2.id, amount="enc2", concept="enc2", category="Rent")

    memory_session.add_all([user1, user2, tx1, tx2])
    memory_session.commit()

    processed_count = await process_day_50_notifications(
        session=memory_session,
        telegram_service=mock_telegram,
        now=now
    )

    assert processed_count == 1
    assert len(mock_telegram.sent_messages) == 2
    chat_ids = {m["chat_id"] for m in mock_telegram.sent_messages}
    assert chat_ids == {11111, 22222}

    # Verify message mentions 2 transactions tracked
    for m in mock_telegram.sent_messages:
        assert "2" in m["text"]
        assert "/upgrade" in m["text"]

    # Verify database state updated
    memory_session.refresh(fam)
    assert fam.notified_day_50 is True
    assert fam.plan_type == "trial"

    # Verify idempotency
    mock_telegram.sent_messages.clear()
    rerun_count = await process_day_50_notifications(
        session=memory_session,
        telegram_service=mock_telegram,
        now=now
    )
    assert rerun_count == 0
    assert len(mock_telegram.sent_messages) == 0

@pytest.mark.anyio
async def test_process_day_60_notifications_lifecycle(memory_session):
    now = datetime(2026, 8, 26, 12, 0, 0, tzinfo=timezone.utc)
    mock_telegram = MockTelegramService()

    fam = Family(
        name="Johnson Family",
        plan_type="trial",
        trial_ends_at=now - timedelta(hours=2),
        notified_day_50=True,
        notified_day_60=False
    )
    memory_session.add(fam)
    memory_session.flush()

    user1 = User(telegram_id=33333, family_id=fam.id, is_admin=True)
    memory_session.add(user1)
    memory_session.commit()

    processed_count = await process_day_60_notifications(
        session=memory_session,
        telegram_service=mock_telegram,
        now=now
    )

    assert processed_count == 1
    assert len(mock_telegram.sent_messages) == 1
    msg = mock_telegram.sent_messages[0]
    assert msg["chat_id"] == 33333
    assert "safe" in msg["text"].lower()
    assert "30" in msg["text"]
    assert "/upgrade" in msg["text"]

    # Verify family transitioned to free and notified_day_60 set
    memory_session.refresh(fam)
    assert fam.plan_type == "free"
    assert fam.notified_day_60 is True

    # Verify idempotency
    mock_telegram.sent_messages.clear()
    rerun_count = await process_day_60_notifications(
        session=memory_session,
        telegram_service=mock_telegram,
        now=now
    )
    assert rerun_count == 0
    assert len(mock_telegram.sent_messages) == 0

@pytest.mark.anyio
async def test_run_daily_trial_notifications_orchestration(memory_session):
    now = datetime(2026, 8, 26, 12, 0, 0, tzinfo=timezone.utc)
    mock_telegram = MockTelegramService()

    # Day 50 candidate
    fam50 = Family(
        name="Family 50",
        plan_type="trial",
        trial_ends_at=now + timedelta(days=8),
        notified_day_50=False
    )
    # Day 60 candidate
    fam60 = Family(
        name="Family 60",
        plan_type="trial",
        trial_ends_at=now - timedelta(days=1),
        notified_day_50=True,
        notified_day_60=False
    )
    memory_session.add_all([fam50, fam60])
    memory_session.flush()

    u50 = User(telegram_id=50001, family_id=fam50.id, is_admin=True)
    u60 = User(telegram_id=60001, family_id=fam60.id, is_admin=True)
    memory_session.add_all([u50, u60])
    memory_session.commit()

    summary = await run_daily_trial_notifications(
        session=memory_session,
        telegram_service=mock_telegram,
        now=now,
        ignore_lock=True
    )

    assert summary["day_50_processed"] == 1
    assert summary["day_60_processed"] == 1
    assert len(mock_telegram.sent_messages) == 2

    memory_session.refresh(fam50)
    memory_session.refresh(fam60)
    assert fam50.notified_day_50 is True
    assert fam60.notified_day_60 is True
    assert fam60.plan_type == "free"

@pytest.mark.anyio
async def test_scheduler_lifecycle_start_and_stop():
    scheduler = NotificationScheduler(interval_seconds=1)
    
    # Start task
    task = scheduler.start()
    assert task is not None
    assert scheduler.is_running is True

    await asyncio.sleep(0.1)

    # Stop task
    await scheduler.stop()
    assert scheduler.is_running is False
