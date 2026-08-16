import pytest
from sqlmodel import Session, SQLModel, create_engine, select
from src.db.models import Family, User, Transaction
import uuid
from datetime import datetime, timezone

# Setup in-memory SQLite for testing models
@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session

def test_create_family(session: Session):
    family = Family(name="Test Family")
    session.add(family)
    session.commit()
    session.refresh(family)
    
    assert family.id is not None
    assert isinstance(family.id, uuid.UUID)
    assert family.name == "Test Family"

def test_create_user_in_family(session: Session):
    family = Family(name="Smiths")
    session.add(family)
    session.commit()
    
    user = User(
        telegram_id=123456789,
        username="john_smith",
        family_id=family.id
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    
    assert user.id is not None
    assert user.family_id == family.id
    assert user.family.name == "Smiths"
    assert len(family.users) == 1

def test_create_transaction(session: Session):
    family = Family(name="Budget Family")
    session.add(family)
    session.commit()
    
    user = User(telegram_id=999, family_id=family.id)
    session.add(user)
    session.commit()
    
    # Ciphertext strings (simulating EncryptionService output)
    encrypted_amount = "gAAAAABm..."
    encrypted_concept = "gAAAAABn..."
    
    transaction = Transaction(
        family_id=family.id,
        user_id=user.id,
        amount=encrypted_amount,
        concept=encrypted_concept,
        category="Food",
        timestamp=datetime.now(timezone.utc)
    )
    session.add(transaction)
    session.commit()
    session.refresh(transaction)
    
    assert transaction.id is not None
    assert transaction.amount == encrypted_amount
    assert transaction.family_id == family.id
    assert transaction.user_id == user.id
    
def test_family_transaction_relationship(session: Session):
    family = Family(name="Relation Family")
    session.add(family)
    session.commit()
    
    user = User(telegram_id=1, family_id=family.id)
    session.add(user)
    
    t1 = Transaction(family_id=family.id, user_id=user.id, amount="10", concept="A", category="X")
    t2 = Transaction(family_id=family.id, user_id=user.id, amount="20", concept="B", category="Y")
    session.add(t1)
    session.add(t2)
    session.commit()
    
    session.refresh(family)
    assert len(family.transactions) == 2

def test_transaction_requires_family(session: Session):
    # This should fail if family_id is mandatory and no family is provided
    # Note: SQLModel/SQLAlchemy only enforces this on commit/flush if nullable=False
    with pytest.raises(Exception):
        t = Transaction(amount="10", concept="A", category="X")
        session.add(t)
        session.commit()

def test_cascade_delete_family(session: Session):
    family = Family(name="Cascade Family")
    session.add(family)
    session.commit()
    
    user1 = User(telegram_id=101, family_id=family.id)
    user2 = User(telegram_id=102, family_id=family.id)
    session.add(user1)
    session.add(user2)
    session.commit()
    
    t1 = Transaction(family_id=family.id, user_id=user1.id, amount="10", concept="A", category="X")
    t2 = Transaction(family_id=family.id, user_id=user2.id, amount="20", concept="B", category="Y")
    session.add(t1)
    session.add(t2)
    session.commit()
    
    # Verify records exist
    assert len(session.exec(select(User).where(User.family_id == family.id)).all()) == 2
    assert len(session.exec(select(Transaction).where(Transaction.family_id == family.id)).all()) == 2
    
    # Delete the family
    session.delete(family)
    session.commit()
    
    # Verify users and transactions are deleted due to relationship cascades
    assert len(session.exec(select(User).where(User.family_id == family.id)).all()) == 0
    assert len(session.exec(select(Transaction).where(Transaction.family_id == family.id)).all()) == 0

def test_cascade_delete_user(session: Session):
    family = Family(name="Cascade User Family")
    session.add(family)
    session.commit()
    
    user = User(telegram_id=201, family_id=family.id)
    session.add(user)
    session.commit()
    
    t1 = Transaction(family_id=family.id, user_id=user.id, amount="10", concept="A", category="X")
    t2 = Transaction(family_id=family.id, user_id=user.id, amount="20", concept="B", category="Y")
    session.add(t1)
    session.add(t2)
    session.commit()
    
    # Delete the user
    session.delete(user)
    session.commit()
    
    # Verify transactions for this user are deleted
    assert len(session.exec(select(Transaction).where(Transaction.user_id == user.id)).all()) == 0

