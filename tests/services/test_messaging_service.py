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

def test_get_or_create_user_no_last_name(session: Session):
    """Verify that user without last_name does not result in 'First None'."""
    service = MessagingService(session)
    user_data = {
        "id": 99999,
        "username": "tony_c",
        "first_name": "Tony",
        "last_name": None
    }
    
    user, family = service.get_or_create_user_and_family(user_data)
    assert user.full_name == "Tony"
    assert family.name == "Tony's Family"

def test_get_or_create_user_no_first_name(session: Session):
    """Verify that user with only last_name sets full_name to last_name."""
    service = MessagingService(session)
    user_data = {
        "id": 88888,
        "username": "crespo_user",
        "first_name": None,
        "last_name": "Crespo"
    }
    
    user, family = service.get_or_create_user_and_family(user_data)
    assert user.full_name == "Crespo"
    assert family.name == "Crespo's Family"

def test_get_or_create_user_only_username(session: Session):
    """Verify that user with neither first nor last name falls back cleanly."""
    service = MessagingService(session)
    user_data = {
        "id": 77777,
        "username": "mystery_user",
        "first_name": None,
        "last_name": None
    }
    
    user, family = service.get_or_create_user_and_family(user_data)
    assert user.full_name is None
    assert family.name == "mystery_user's Family"

