import pytest
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from sqlmodel import Session, create_engine, SQLModel
from src.db.models import User, Family, FamilyInvite, Transaction
from src.services.family_service import FamilyService

from sqlalchemy.pool import StaticPool

@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
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


def test_leave_family_blocked_for_active_pro_admin(session: Session, family_service: FamilyService):
    from src.templates.telegram_messages import LEAVE_FAMILY_ADMIN_ACTIVE_PRO_BLOCKED

    family = Family(name="Pro Family", plan_type="family_pro", subscription_status="active")
    session.add(family)
    session.commit()

    admin = User(telegram_id=8001, username="pro_admin", family_id=family.id, is_admin=True)
    member = User(telegram_id=8002, username="pro_member", family_id=family.id, is_admin=False)
    session.add_all([admin, member])
    session.commit()

    # Preview should report blocked
    preview = family_service.get_leave_family_preview(admin.id)
    assert preview["allowed"] is False
    assert preview["reason"] == "active_pro_admin"
    assert preview["message"] == LEAVE_FAMILY_ADMIN_ACTIVE_PRO_BLOCKED

    # Direct leave should be blocked
    success, msg, _ = family_service.leave_family(admin.id)
    assert success is False
    assert msg == LEAVE_FAMILY_ADMIN_ACTIVE_PRO_BLOCKED


def test_leave_family_admin_free_transfers_to_oldest(session: Session, family_service: FamilyService):
    family = Family(name="Free Family", plan_type="free")
    session.add(family)
    session.commit()

    admin = User(telegram_id=9001, username="free_admin", family_id=family.id, is_admin=True)
    member1 = User(telegram_id=9002, username="member_older", family_id=family.id, is_admin=False)
    member2 = User(telegram_id=9003, username="member_younger", family_id=family.id, is_admin=False)
    session.add_all([admin, member1, member2])
    session.commit()

    # Add transaction for admin
    tx = Transaction(user_id=admin.id, family_id=family.id, amount=50.0, category="food", concept="lunch")
    session.add(tx)
    session.commit()

    # Preview explains transfer to member_older
    preview = family_service.get_leave_family_preview(admin.id)
    assert preview["allowed"] is True
    assert preview["requires_confirmation"] is True
    assert "@member_older" in preview["prompt"]

    # Admin confirms leave
    success, msg, new_family = family_service.leave_family(admin.id)
    assert success is True
    assert new_family is not None
    session.refresh(admin)
    assert admin.family_id == new_family.id

    # member1 should now be the new admin of the original family
    session.refresh(member1)
    assert member1.is_admin is True

    # Admin's transaction moved to new_family
    session.refresh(tx)
    assert tx.family_id == new_family.id


@pytest.mark.anyio
async def test_handle_leave_family_two_step_confirmation(session: Session, family_service: FamilyService):
    from src.services.handlers.family_handler import handle_leave_family

    family = Family(name="Confirm Fam", plan_type="free")
    session.add(family)
    session.commit()

    admin = User(telegram_id=9101, username="admin_c", family_id=family.id, is_admin=True)
    member = User(telegram_id=9102, username="member_c", family_id=family.id, is_admin=False)
    session.add_all([admin, member])
    session.commit()

    # Step 1: Member calls without confirmation -> receives prompt
    prompt_resp = await handle_leave_family(member.id, raw_text="/leavefamily", family_service=family_service)
    assert "Confirm Leaving Family" in prompt_resp
    assert "CONFIRM LEAVE" in prompt_resp

    # Verify member is still in the family
    session.refresh(member)
    assert member.family_id == family.id

    # Step 2: Member replies CONFIRM LEAVE -> executes leave
    exec_resp = await handle_leave_family(member.id, raw_text="CONFIRM LEAVE", family_service=family_service)
    assert "left the family group" in exec_resp.lower()

    # Member is now in new family
    session.refresh(member)
    assert member.family_id != family.id


def test_split_family_on_downgrade(session: Session, family_service: FamilyService):
    family = Family(name="Big Family", plan_type="family_pro")
    session.add(family)
    session.commit()

    admin = User(telegram_id=9201, username="admin_downgrade", family_id=family.id, is_admin=True)
    m1 = User(telegram_id=9202, username="m1_senior", family_id=family.id, is_admin=False)
    m2 = User(telegram_id=9203, username="m2_junior", family_id=family.id, is_admin=False)
    session.add_all([admin, m1, m2])
    session.commit()

    tx_admin = Transaction(user_id=admin.id, family_id=family.id, amount=100.0, category="rent", concept="rent")
    tx_m1 = Transaction(user_id=m1.id, family_id=family.id, amount=20.0, category="food", concept="food")
    tx_m2 = Transaction(user_id=m2.id, family_id=family.id, amount=15.0, category="coffee", concept="coffee")
    session.add_all([tx_admin, tx_m1, tx_m2])
    session.commit()

    # Execute split
    new_fam, non_admins = family_service.split_family_on_downgrade(family.id)
    assert new_fam is not None
    assert len(non_admins) == 2
    assert new_fam.plan_type == "free"

    # Admin stays in original family
    session.refresh(admin)
    assert admin.family_id == family.id

    # Non-admins moved to new family; m1 is the new admin
    session.refresh(m1)
    session.refresh(m2)
    assert m1.family_id == new_fam.id
    assert m1.is_admin is True
    assert m2.family_id == new_fam.id
    assert m2.is_admin is False

    # Transactions correctly partitioned
    session.refresh(tx_admin)
    session.refresh(tx_m1)
    session.refresh(tx_m2)
    assert tx_admin.family_id == family.id
    assert tx_m1.family_id == new_fam.id
    assert tx_m2.family_id == new_fam.id


def test_graduate_member_to_new_workspace(session: Session, family_service: FamilyService):
    host_fam = Family(name="Host Fam", plan_type="family_pro")
    session.add(host_fam)
    session.commit()

    admin = User(telegram_id=9301, username="host_admin", family_id=host_fam.id, is_admin=True)
    grad_user = User(telegram_id=9302, username="graduating_user", family_id=host_fam.id, is_admin=False)
    session.add_all([admin, grad_user])
    session.commit()

    tx_host = Transaction(user_id=admin.id, family_id=host_fam.id, amount=200.0, category="bills", concept="power")
    tx_grad = Transaction(user_id=grad_user.id, family_id=host_fam.id, amount=30.0, category="books", concept="textbook")
    session.add_all([tx_host, tx_grad])
    session.commit()

    # Graduate to Family Pro
    new_fam = family_service.graduate_member_to_new_workspace(grad_user.id, target_plan="family_pro")
    assert new_fam.plan_type == "family_pro"

    # grad_user is admin in new workspace
    session.refresh(grad_user)
    assert grad_user.family_id == new_fam.id
    assert grad_user.is_admin is True

    # Host family is unchanged with admin
    session.refresh(admin)
    assert admin.family_id == host_fam.id

    # Personal transactions cleanly migrated
    session.refresh(tx_host)
    session.refresh(tx_grad)
    assert tx_host.family_id == host_fam.id
    assert tx_grad.family_id == new_fam.id


def test_free_and_trial_member_limit_enforcement(session: Session, family_service: FamilyService):
    """Verify that Free and Trial workspaces enforce the 5-member limit on invite creation and joining."""
    from src.services.family_service import PlanLimitExceededError

    # Create free family with 5 members
    fam = Family(name="Free Family Cap", plan_type="free", max_members=5)
    session.add(fam)
    session.commit()

    admin = User(telegram_id=9401, username="admin_free", family_id=fam.id, is_admin=True)
    session.add(admin)
    session.commit()

    # Add 4 more members (total 5)
    for i in range(2, 6):
        u = User(telegram_id=9400 + i, username=f"member_{i}", family_id=fam.id, is_admin=False)
        session.add(u)
    session.commit()

    # 1. Attempting to create invite when at 5 members must raise PlanLimitExceededError
    with pytest.raises(PlanLimitExceededError) as exc:
        family_service.create_invite(fam.id, admin.id)
    assert "limit of 5 members" in str(exc.value)

    # 2. Attempting to join with an existing token when at 5 members must be rejected
    invite = FamilyInvite(family_id=fam.id, created_by_user_id=admin.id, token="free_cap_token", expires_at=datetime.now(timezone.utc) + timedelta(hours=1))
    session.add(invite)
    session.commit()

    other_fam = Family(name="Other")
    session.add(other_fam)
    session.commit()
    outsider = User(telegram_id=9499, username="outsider", family_id=other_fam.id)
    session.add(outsider)
    session.commit()

    ok, msg, _ = family_service.join_family_via_invite("free_cap_token", outsider.id)
    assert ok is False
    assert "limit of 5 members" in msg




