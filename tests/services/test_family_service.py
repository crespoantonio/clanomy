import pytest
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from sqlmodel import Session, create_engine, SQLModel
from src.db.models import User, Family, FamilyInvite
from src.services.family_service import FamilyService

@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session

@pytest.fixture(name="family_service")
def family_service_fixture(session: Session):
    # Pass session or mock dependency injection if needed
    service = FamilyService()
    service.engine = session.bind  # Mock engine for testing
    return service

def test_create_family(session: Session, family_service: FamilyService):
    dummy_family = Family(name="Initial Dummy")
    session.add(dummy_family)
    session.commit()
    
    user_id = uuid4()
    user = User(id=user_id, telegram_id=111, family_id=dummy_family.id) # Initial dummy family
    session.add(user)
    session.commit()
    
    # Create family
    family = family_service.create_family(user_id=user_id, name="The Smiths")
    family_id = family.id
    db_family = session.get(Family, family_id)
    assert db_family is not None
    assert db_family.name == "The Smiths"
    
    # User should now be in the new family
    session.refresh(user)
    assert user.family_id == family.id

def test_create_invite(session: Session, family_service: FamilyService):
    family = Family(name="Invite Gen")
    session.add(family)
    session.commit()
    
    user = User(telegram_id=222, family_id=family.id)
    session.add(user)
    session.commit()
    
    invite, link = family_service.create_invite(family_id=family.id, user_id=user.id, ttl_hours=24)
    
    assert invite is not None
    assert invite.token in link
    assert invite.family_id == family.id
    assert invite.created_by_user_id == user.id
    assert invite.is_active is True
    # check expiration is roughly 24h
    expires_at = invite.expires_at.replace(tzinfo=timezone.utc) if invite.expires_at.tzinfo is None else invite.expires_at
    delta = expires_at - datetime.now(timezone.utc)
    assert 23 < delta.total_seconds() / 3600 <= 24

def test_join_family_via_invite_success(session: Session, family_service: FamilyService):
    family = Family(name="Target")
    session.add(family)
    session.commit()
    
    creator = User(telegram_id=333, family_id=family.id)
    session.add(creator)
    session.commit()
    
    invite, _ = family_service.create_invite(family_id=family.id, user_id=creator.id)
    
    joiner_family = Family(name="Joiner Init")
    session.add(joiner_family)
    session.commit()
    
    joiner = User(telegram_id=444, family_id=joiner_family.id)
    session.add(joiner)
    session.commit()
    
    success, msg, joined_family = family_service.join_family_via_invite(token=invite.token, user_id=joiner.id)
    
    assert success is True
    assert joined_family is not None
    assert joined_family.id == family.id
    
    session.refresh(joiner)
    assert joiner.family_id == family.id

def test_join_family_via_invite_expired(session: Session, family_service: FamilyService):
    family = Family(name="Expired")
    session.add(family)
    session.commit()
    
    creator = User(telegram_id=555, family_id=family.id)
    session.add(creator)
    session.commit()
    
    invite = FamilyInvite(
        family_id=family.id,
        created_by_user_id=creator.id,
        token="expired_token",
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1)
    )
    session.add(invite)
    session.commit()
    
    joiner_family = Family(name="Joiner Init")
    session.add(joiner_family)
    session.commit()
    
    joiner = User(telegram_id=666, family_id=joiner_family.id)
    session.add(joiner)
    session.commit()
    
    success, msg, joined_family = family_service.join_family_via_invite(token="expired_token", user_id=joiner.id)
    
    assert success is False
    assert joined_family is None
    assert "expired" in msg.lower() or "invalid" in msg.lower()

def test_get_family_info(session: Session, family_service: FamilyService):
    family = Family(name="Info Fam")
    session.add(family)
    session.commit()
    
    user1 = User(telegram_id=777, username="u1", full_name="User One", family_id=family.id)
    user2 = User(telegram_id=888, username="u2", family_id=family.id)
    session.add(user1)
    session.add(user2)
    session.commit()
    
    info = family_service.get_family_info(user_id=user1.id)
    assert info["name"] == "Info Fam"
    assert len(info["members"]) == 2
    assert "u1" in [m.get("username") for m in info["members"]]

def test_join_family_via_invite_with_transaction_migration(session: Session, family_service: FamilyService):
    from src.db.models import Transaction
    target_family = Family(name="Target Family")
    session.add(target_family)
    session.commit()
    
    creator = User(telegram_id=901, family_id=target_family.id)
    session.add(creator)
    session.commit()
    
    invite, _ = family_service.create_invite(family_id=target_family.id, user_id=creator.id)
    
    solo_family = Family(name="Solo Family")
    session.add(solo_family)
    session.commit()
    
    joiner = User(telegram_id=902, family_id=solo_family.id)
    session.add(joiner)
    session.commit()
    
    tx = Transaction(
        family_id=solo_family.id,
        user_id=joiner.id,
        amount="encoded_amount",
        concept="encoded_concept",
        category="Food/Drink"
    )
    session.add(tx)
    session.commit()
    
    solo_family_id = solo_family.id
    success, msg, joined_family = family_service.join_family_via_invite(token=invite.token, user_id=joiner.id)
    
    assert success is True
    assert joined_family.id == target_family.id
    
    session.refresh(tx)
    assert tx.family_id == target_family.id
    session.expire_all()
    assert session.get(Family, solo_family_id) is None
