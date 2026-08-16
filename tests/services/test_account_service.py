import pytest
import asyncio
from unittest.mock import patch
from uuid import uuid4
from sqlmodel import Session, create_engine, SQLModel
from sqlalchemy.pool import StaticPool

from src.db.models import Family, User, Transaction
from src.services.account_service import AccountService

@pytest.fixture(name="engine")
def engine_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine

@pytest.fixture(name="session")
def session_fixture(engine):
    with Session(engine) as session:
        yield session

@pytest.mark.anyio
async def test_delete_single_member_family(engine, session):
    family_id = uuid4()
    user_id = uuid4()
    
    family = Family(id=family_id, name="Test Family")
    user = User(id=user_id, telegram_id=123, family_id=family_id)
    tx = Transaction(id=uuid4(), family_id=family_id, user_id=user_id, amount="encoded", concept="encoded", category="food")
    
    tx_id = tx.id
    
    session.add(family)
    session.add(user)
    session.add(tx)
    session.commit()
    
    service = AccountService(engine)
    result = await service.delete_account(user_id)
    
    assert result is True
    
    # Verify everything is gone
    with Session(engine) as check_session:
        assert check_session.get(User, user_id) is None
        assert check_session.get(Family, family_id) is None
        assert check_session.get(Transaction, tx_id) is None

@pytest.mark.anyio
async def test_delete_multi_member_family(engine, session):
    family_id = uuid4()
    user_id_1 = uuid4()
    user_id_2 = uuid4()
    
    family = Family(id=family_id, name="Test Family")
    user1 = User(id=user_id_1, telegram_id=123, family_id=family_id)
    user2 = User(id=user_id_2, telegram_id=456, family_id=family_id)
    tx1 = Transaction(id=uuid4(), family_id=family_id, user_id=user_id_1, amount="encoded", concept="encoded", category="food")
    tx2 = Transaction(id=uuid4(), family_id=family_id, user_id=user_id_2, amount="encoded", concept="encoded", category="rent")
    
    tx1_id = tx1.id
    tx2_id = tx2.id
    
    session.add(family)
    session.add(user1)
    session.add(user2)
    session.add(tx1)
    session.add(tx2)
    session.commit()
    
    service = AccountService(engine)
    result = await service.delete_account(user_id_1)
    
    assert result is True
    
    # Verify user1 and tx1 are gone
    with Session(engine) as check_session:
        assert check_session.get(User, user_id_1) is None
        assert check_session.get(Transaction, tx1_id) is None
        
        # Verify family, user2, and tx2 remain
        assert check_session.get(Family, family_id) is not None
        assert check_session.get(User, user_id_2) is not None
        assert check_session.get(Transaction, tx2_id) is not None

@pytest.mark.anyio
async def test_delete_rollback_on_error(engine, session):
    family_id = uuid4()
    user_id = uuid4()
    
    family = Family(id=family_id, name="Test Family")
    user = User(id=user_id, telegram_id=123, family_id=family_id)
    
    session.add(family)
    session.add(user)
    session.commit()
    
    service = AccountService(engine)
    
    with patch("src.services.account_service.Session.commit", side_effect=Exception("Simulated commit error")):
        result = await service.delete_account(user_id)
        
    assert result is False
    
    # Verify data is untouched
    with Session(engine) as check_session:
        assert check_session.get(User, user_id) is not None
        assert check_session.get(Family, family_id) is not None
