import pytest
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from sqlmodel import Session, select
from src.db.session import engine
from src.db.models import Family, User, Transaction, ScheduledBill
from src.core.encryption import EncryptionService
from src.services.query.models import NormalizedQueryAST, TemporalScope, EntityFilters, QueryOperation
from src.services.query.dataset_router import DatasetRouter, InMemoryEntityResolver, calculate_token_similarity

@pytest.fixture
def test_setup():
    from sqlmodel import SQLModel
    SQLModel.metadata.create_all(engine)
    encryption = EncryptionService()
    family_id = uuid4()
    user_id = uuid4()

    with Session(engine) as session:
        fam = Family(id=family_id, name="Test Query Family", default_currency="USD")
        session.add(fam)
        user = User(id=user_id, family_id=family_id, telegram_id=12345678, username="tester", full_name="Test User", is_admin=True)
        session.add(user)

        # 1. Historical Transaction (Rent/Bills)
        past_tx = Transaction(
            family_id=family_id,
            user_id=user_id,
            amount=encryption.encrypt("120.00 USD"),
            concept=encryption.encrypt("Electricidad Edesur"),
            category="Rent/Bills",
            type="expense",
            timestamp=datetime.now(timezone.utc) - timedelta(days=20)
        )
        session.add(past_tx)

        # 2. Historical Paid Scheduled Bill
        paid_bill = ScheduledBill(
            family_id=family_id,
            user_id=user_id,
            amount=encryption.encrypt("60.00 USD"),
            concept=encryption.encrypt("Internet Fibertel"),
            category="Rent/Bills",
            due_date=datetime.now(timezone.utc) - timedelta(days=15),
            status="paid"
        )
        session.add(paid_bill)

        # 3. Upcoming Scheduled Bill
        upcoming_bill = ScheduledBill(
            family_id=family_id,
            user_id=user_id,
            amount=encryption.encrypt("85.00 USD"),
            concept=encryption.encrypt("Gas Naturgy"),
            category="Rent/Bills",
            due_date=datetime.now(timezone.utc) + timedelta(days=10),
            status="pending"
        )
        session.add(upcoming_bill)
        session.commit()

    yield family_id, user_id, encryption

    # Cleanup
    with Session(engine) as session:
        session.exec(select(Transaction).where(Transaction.family_id == family_id))
        for t in session.exec(select(Transaction).where(Transaction.family_id == family_id)).all():
            session.delete(t)
        for b in session.exec(select(ScheduledBill).where(ScheduledBill.family_id == family_id)).all():
            session.delete(b)
        for u in session.exec(select(User).where(User.family_id == family_id)).all():
            session.delete(u)
        fam = session.get(Family, family_id)
        if fam:
            session.delete(fam)
        session.commit()

def test_similarity_calculation():
    assert calculate_token_similarity("electricity", "electricidad") > 0.7
    assert calculate_token_similarity("Iberdrola", "Iberdrola Luz") >= 0.9
    assert calculate_token_similarity("Netflix", "Spotify") < 0.4

def test_in_memory_entity_resolver():
    resolver = InMemoryEntityResolver()
    candidates = ["Internet Fibertel", "Electricidad Edesur", "Gimnasio"]
    res = resolver.resolve_candidate("internet", candidates)
    assert res.status == "EXACT"
    assert res.matched_candidate == "Internet Fibertel"

def test_dataset_router_historical_bills(test_setup):
    family_id, user_id, encryption = test_setup
    router = DatasetRouter(encryption)

    ast = NormalizedQueryAST(
        raw_query="bills last 3 months",
        temporal=TemporalScope(
            timeframe="last_90_days",
            is_historical=True,
            is_projected=False
        ),
        filters=EntityFilters(domains=["bills"]),
        operation=QueryOperation(op="list")
    )

    dataset = router.route_and_fetch(
        family_id=family_id,
        ast=ast,
        start_time=datetime.now(timezone.utc) - timedelta(days=90),
        end_time=datetime.now(timezone.utc)
    )

    # Should fetch both historical transaction and paid scheduled bill
    assert len(dataset.transactions) >= 1
    assert len(dataset.scheduled_bills) >= 1
    concepts = [t.concept for t in dataset.transactions] + [b.concept for b in dataset.scheduled_bills]
    assert "Electricidad Edesur" in concepts
    assert "Internet Fibertel" in concepts
    assert "Gas Naturgy" not in concepts

def test_dataset_router_upcoming_bills(test_setup):
    family_id, user_id, encryption = test_setup
    router = DatasetRouter(encryption)

    ast = NormalizedQueryAST(
        raw_query="upcoming bills",
        temporal=TemporalScope(
            timeframe="this_month",
            is_historical=False,
            is_projected=True
        ),
        filters=EntityFilters(domains=["bills"]),
        operation=QueryOperation(op="list")
    )

    dataset = router.route_and_fetch(
        family_id=family_id,
        ast=ast,
        start_time=datetime.now(timezone.utc),
        end_time=datetime.now(timezone.utc) + timedelta(days=30)
    )

    # Should only fetch pending upcoming bills, zero historical transactions
    assert len(dataset.transactions) == 0
    assert len(dataset.scheduled_bills) >= 1
    assert dataset.scheduled_bills[0].concept == "Gas Naturgy"
