import pytest
from sqlmodel import Session, create_engine, SQLModel
from src.db.models import User, Family
from src.services.messaging_service import MessagingService

# Setup in-memory SQLite for testing
@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session

def test_get_or_create_user_new_user(session: Session):
    service = MessagingService(session)
    user_data = {
        "id": 12345,
        "username": "testuser",
        "first_name": "Test",
        "last_name": "User"
    }
    
    user, family = service.get_or_create_user_and_family(user_data)
    
    assert user.telegram_id == 12345
    assert user.username == "testuser"
    assert user.full_name == "Test User"
    assert user.family_id == family.id
    assert user.has_used_trial is True
    assert family is not None
    assert family.plan_type == "trial"
    assert family.trial_ends_at is not None
    
    # Verify persistence
    db_user = session.get(User, user.id)
    assert db_user is not None
    assert db_user.telegram_id == 12345
    assert db_user.has_used_trial is True

def test_get_or_create_user_existing_user(session: Session):
    # Setup existing user
    family = Family(name="Existing Family")
    session.add(family)
    session.commit()
    
    user = User(
        telegram_id=12345,
        username="existing",
        full_name="Existing User",
        family_id=family.id
    )
    session.add(user)
    session.commit()
    
    service = MessagingService(session)
    user_data = {
        "id": 12345,
        "username": "existing_updated", # Changed username
        "first_name": "Existing",
        "last_name": "User"
    }
    
    returned_user, returned_family = service.get_or_create_user_and_family(user_data)
    
    assert returned_user.id == user.id
    assert returned_family.id == family.id
    # Should update info if changed
    assert returned_user.username == "existing_updated"
