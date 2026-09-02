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
    
    # Test custom ttl_hours
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

def test_create_invite_default_1h_ttl(session: Session, family_service: FamilyService):
    family = Family(name="Invite Gen Default")
    session.add(family)
    session.commit()
    
    user = User(telegram_id=223, family_id=family.id)
    session.add(user)
    session.commit()
    
    # Test default TTL is 1 hour
    invite, link = family_service.create_invite(family_id=family.id, user_id=user.id)
    
    assert invite is not None
    assert invite.token in link
    assert invite.is_active is True
    expires_at = invite.expires_at.replace(tzinfo=timezone.utc) if invite.expires_at.tzinfo is None else invite.expires_at
    delta = expires_at - datetime.now(timezone.utc)
    assert 0.9 <= delta.total_seconds() / 3600 <= 1.0

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

    # Verify single-use: invite is marked inactive immediately upon successful join
    updated_invite = session.get(FamilyInvite, invite.id)
    assert updated_invite.is_active is False

def test_join_family_via_invite_single_use_blocked(session: Session, family_service: FamilyService):
    family = Family(name="Target Single Use")
    session.add(family)
    session.commit()
    
    creator = User(telegram_id=5551, family_id=family.id)
    session.add(creator)
    session.commit()
    
    invite, _ = family_service.create_invite(family_id=family.id, user_id=creator.id)
    
    fam1 = Family(name="Fam1")
    fam2 = Family(name="Fam2")
    session.add(fam1)
    session.add(fam2)
    session.commit()
    
    user1 = User(telegram_id=5552, family_id=fam1.id)
    user2 = User(telegram_id=5553, family_id=fam2.id)
    session.add(user1)
    session.add(user2)
    session.commit()
    
    # First join succeeds
    success1, _, _ = family_service.join_family_via_invite(token=invite.token, user_id=user1.id)
    assert success1 is True
    
    # Second join with same token must fail because token was invalidated
    success2, msg2, _ = family_service.join_family_via_invite(token=invite.token, user_id=user2.id)
    assert success2 is False
    assert "invalid or has expired" in msg2

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


def test_create_family_trial_and_anti_abuse(session: Session, family_service: FamilyService):
    # User 1: has NOT used trial -> gets trial
    u1 = User(telegram_id=1001, username="u1", has_used_trial=False, family_id=uuid4())
    session.add(u1)
    session.commit()

    f1 = family_service.create_family(user_id=u1.id, name="Family 1")
    session.refresh(u1)
    assert f1.plan_type == "trial"
    assert f1.trial_ends_at is not None
    assert u1.has_used_trial is True

    # User 2: has already used trial -> gets free
    u2 = User(telegram_id=1002, username="u2", has_used_trial=True, family_id=uuid4())
    session.add(u2)
    session.commit()

    f2 = family_service.create_family(user_id=u2.id, name="Family 2")
    session.refresh(u2)
    assert f2.plan_type == "free"
    assert f2.trial_ends_at is None


def test_is_family_admin(session: Session, family_service: FamilyService):
    family = Family(name="Admin Test Fam")
    session.add(family)
    session.commit()

    creator = User(telegram_id=2001, username="creator", family_id=family.id)
    session.add(creator)
    session.commit()

    member = User(telegram_id=2002, username="member", family_id=family.id)
    session.add(member)
    session.commit()

    assert family_service.is_family_admin(family.id, creator.id) is True
    assert family_service.is_family_admin(family.id, member.id) is False


def test_remove_member_success(session: Session, family_service: FamilyService):
    from src.db.models import Transaction
    family = Family(name="Removal Fam")
    session.add(family)
    session.commit()

    admin = User(telegram_id=3001, username="admin_u", full_name="Admin User", family_id=family.id, has_used_trial=True)
    session.add(admin)
    session.commit()

    member = User(telegram_id=3002, username="member_u", full_name="Member User", family_id=family.id, has_used_trial=True)
    session.add(member)
    session.commit()

    tx = Transaction(
        family_id=family.id,
        user_id=member.id,
        amount="enc_amt",
        concept="enc_cpt",
        category="Groceries"
    )
    session.add(tx)
    session.commit()

    success, msg, removed_user, new_family = family_service.remove_member(
        admin_user_id=admin.id,
        target_identifier="@member_u"
    )

    assert success is True
    assert removed_user.id == member.id
    assert new_family is not None
    assert new_family.id != family.id
    assert new_family.plan_type == "free"

    session.refresh(member)
    assert member.family_id == new_family.id

    session.refresh(tx)
    assert tx.family_id == new_family.id


def test_remove_member_non_admin_forbidden(session: Session, family_service: FamilyService):
    family = Family(name="Forbidden Fam")
    session.add(family)
    session.commit()

    admin = User(telegram_id=4001, username="admin4", family_id=family.id)
    session.add(admin)
    session.commit()

    member = User(telegram_id=4002, username="member4", family_id=family.id)
    session.add(member)
    session.commit()

    # Member tries to remove admin
    success, msg, _, _ = family_service.remove_member(
        admin_user_id=member.id,
        target_identifier="@admin4"
    )
    assert success is False
    assert "only the family admin" in msg.lower()


def test_remove_member_self_removal_prevented(session: Session, family_service: FamilyService):
    family = Family(name="Self Fam")
    session.add(family)
    session.commit()

    admin = User(telegram_id=5001, username="admin5", family_id=family.id)
    session.add(admin)
    session.commit()

    success, msg, _, _ = family_service.remove_member(
        admin_user_id=admin.id,
        target_identifier="@admin5"
    )
    assert success is False
    assert "cannot remove yourself" in msg.lower()


def test_leave_family_success(session: Session, family_service: FamilyService):
    from src.db.models import Transaction
    family = Family(name="Multi Fam")
    session.add(family)
    session.commit()

    creator = User(telegram_id=6001, username="creator6", family_id=family.id, has_used_trial=True)
    session.add(creator)
    session.commit()

    leaver = User(telegram_id=6002, username="leaver6", full_name="Leaver Six", family_id=family.id, has_used_trial=True)
    session.add(leaver)
    session.commit()

    tx = Transaction(
        family_id=family.id,
        user_id=leaver.id,
        amount="enc_amt",
        concept="enc_cpt",
        category="Dining"
    )
    session.add(tx)
    session.commit()

    success, msg, new_family = family_service.leave_family(user_id=leaver.id)

    assert success is True
    assert "left the family group" in msg.lower()
    assert new_family is not None
    assert new_family.id != family.id
    assert new_family.plan_type == "free"

    session.refresh(leaver)
    assert leaver.family_id == new_family.id

    session.refresh(tx)
    assert tx.family_id == new_family.id


def test_leave_family_solo_notice(session: Session, family_service: FamilyService):
    family = Family(name="Solo Fam")
    session.add(family)
    session.commit()

    user = User(telegram_id=7001, username="solo7", family_id=family.id)
    session.add(user)
    session.commit()

    success, msg, res_family = family_service.leave_family(user_id=user.id)
    assert success is False
    assert "already in your own personal workspace" in msg.lower()

def test_family_default_currency_get_and_set(session: Session, family_service: FamilyService):
    family = Family(name="Currency Test Fam")
    session.add(family)
    session.commit()

    # Initial default should be USD
    curr = family_service.get_family_default_currency(family.id)
    assert curr == "USD"

    # Set to ARS
    updated = family_service.set_family_default_currency(family.id, "ARS")
    assert updated == "ARS"
    assert family_service.get_family_default_currency(family.id) == "ARS"

    # Set via alias e.g. "pesos mexicanos"
    updated_mxn = family_service.set_family_default_currency(family.id, "pesos mexicanos")
    assert updated_mxn == "MXN"
    assert family_service.get_family_default_currency(family.id) == "MXN"

    # Invalid currency code raises ValueError
    with pytest.raises(ValueError, match="Invalid currency code"):
        family_service.set_family_default_currency(family.id, "INVALID_CODE")


