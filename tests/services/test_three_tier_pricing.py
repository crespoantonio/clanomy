import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, patch, MagicMock
from sqlmodel import Session, SQLModel, create_engine, select
from sqlalchemy.pool import StaticPool
from fastapi import BackgroundTasks

from src.core.config import settings
from src.core.subscription_config import (
    SUBSCRIPTION_TIERS,
    get_tier_config,
    get_tier_by_variant_id,
)
from src.db.models import Family, User, FamilyInvite
from src.services.subscription_service import (
    VALID_PLAN_TYPES,
    is_unlimited_plan,
    has_unlimited_access,
)
from src.services.family_service import FamilyService, PlanLimitExceededError
from src.services.billing.lemonsqueezy_billing import LemonSqueezyBillingService
from src.templates.telegram_messages import DUO_PRO_CONFIRMATION


class MockTelegramService:
    def __init__(self):
        self.sent_messages = []

    async def send_message(self, chat_id: int, text: str, parse_mode=None, reply_markup=None):
        self.sent_messages.append({
            "chat_id": chat_id,
            "text": text,
            "reply_markup": reply_markup
        })

    async def get_bot_username(self):
        return "TestClanomyBot"


@pytest.fixture
def tier_test_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_subscription_tiers_registry():
    """Verify that all 3 tiers (monthly and annual) are properly configured with exact prices and member limits."""
    # Check all 6 tier keys
    assert "solo_pro" in SUBSCRIPTION_TIERS
    assert "duo_pro" in SUBSCRIPTION_TIERS
    assert "family_pro" in SUBSCRIPTION_TIERS
    assert "solo_pro_annual" in SUBSCRIPTION_TIERS
    assert "duo_pro_annual" in SUBSCRIPTION_TIERS
    assert "family_pro_annual" in SUBSCRIPTION_TIERS

    # Solo Pro
    solo = SUBSCRIPTION_TIERS["solo_pro"]
    assert solo.price_usd_cents == 499
    assert solo.max_members == 1
    assert solo.internal_plan == "solo_pro"

    solo_ann = SUBSCRIPTION_TIERS["solo_pro_annual"]
    assert solo_ann.price_usd_cents == 4999
    assert solo_ann.max_members == 1
    assert solo_ann.duration_days == 365

    # Duo Pro
    duo = SUBSCRIPTION_TIERS["duo_pro"]
    assert duo.price_usd_cents == 799
    assert duo.max_members == 2
    assert duo.internal_plan == "duo_pro"
    assert duo.variant_id_setting_name == "LEMON_SQUEEZY_DUO_PRO_VARIANT_ID"

    duo_ann = SUBSCRIPTION_TIERS["duo_pro_annual"]
    assert duo_ann.price_usd_cents == 7999
    assert duo_ann.max_members == 2
    assert duo_ann.duration_days == 365
    assert duo_ann.variant_id_setting_name == "LEMON_SQUEEZY_DUO_PRO_ANNUAL_VARIANT_ID"

    # Family Pro
    fam = SUBSCRIPTION_TIERS["family_pro"]
    assert fam.price_usd_cents == 1199
    assert fam.max_members == 5
    assert fam.internal_plan == "family_pro"

    fam_ann = SUBSCRIPTION_TIERS["family_pro_annual"]
    assert fam_ann.price_usd_cents == 11999
    assert fam_ann.max_members == 5
    assert fam_ann.duration_days == 365

    # Plan validation helpers
    assert "duo_pro" in VALID_PLAN_TYPES
    assert is_unlimited_plan("duo_pro") is True


def test_duo_pro_member_capacity_enforcement(tier_test_session):
    """Verify that Duo Pro allows 2 partners but blocks inviting or joining a 3rd member."""
    fam_service = FamilyService()
    fam_service.engine = tier_test_session.bind

    # Create a duo_pro workspace
    family = Family(
        name="Couple Clan",
        plan_type="duo_pro",
        max_members=2,
        subscription_status="active"
    )
    tier_test_session.add(family)
    tier_test_session.commit()
    tier_test_session.refresh(family)

    user1 = User(telegram_id=1001, full_name="Partner One", family_id=family.id, is_admin=True)
    tier_test_session.add(user1)
    tier_test_session.commit()
    tier_test_session.refresh(user1)

    # 1. Partner 1 creates an invite (allowed, currently 1 member)
    invite, link = fam_service.create_invite(family.id, user1.id)
    assert invite is not None
    assert "join_" in link

    # 2. Partner 2 joins from their personal workspace
    fam2 = Family(name="Partner 2 Fam")
    tier_test_session.add(fam2)
    tier_test_session.commit()
    tier_test_session.refresh(fam2)

    user2 = User(telegram_id=1002, full_name="Partner Two", family_id=fam2.id)
    tier_test_session.add(user2)
    tier_test_session.commit()
    tier_test_session.refresh(user2)

    ok, msg, joined_fam = fam_service.join_family_via_invite(invite.token, user2.id)
    assert ok is True
    assert joined_fam.id == family.id

    # Workspace now has 2 members
    members = tier_test_session.exec(select(User).where(User.family_id == family.id)).all()
    assert len(members) == 2

    # 3. Attempting to create a new invite when at capacity (2) must be blocked
    with pytest.raises(PlanLimitExceededError) as exc_info:
        fam_service.create_invite(family.id, user1.id)
    assert "Duo Pro plan only supports up to 2 partners" in str(exc_info.value)

    # 4. Attempting to join with an existing invite token when workspace is full must be rejected
    invite2 = FamilyInvite(family_id=family.id, created_by_user_id=user1.id, token="bypass_token", expires_at=invite.expires_at)
    tier_test_session.add(invite2)
    tier_test_session.commit()

    fam3 = Family(name="Partner 3 Fam")
    tier_test_session.add(fam3)
    tier_test_session.commit()

    user3 = User(telegram_id=1003, full_name="Third Wheel", family_id=fam3.id)
    tier_test_session.add(user3)
    tier_test_session.commit()
    tier_test_session.refresh(user3)

    ok3, msg3, _ = fam_service.join_family_via_invite("bypass_token", user3.id)
    assert ok3 is False
    assert "reached the Duo Pro limit of 2 members" in msg3


def test_duo_pro_webhook_activation(tier_test_session, monkeypatch):
    """Verify that Lemon Squeezy webhook for duo_pro upgrades workspace to max_members=2 and sends confirmation."""
    monkeypatch.setattr(settings, "ENABLE_SUBSCRIPTIONS", True)
    monkeypatch.setattr(settings, "LEMON_SQUEEZY_STORE_ID", "store_999")
    monkeypatch.setattr(settings, "LEMON_SQUEEZY_DUO_PRO_VARIANT_ID", "var_duo_123")

    family = Family(name="Test Duo Family", plan_type="free", max_members=5)
    tier_test_session.add(family)
    tier_test_session.commit()
    tier_test_session.refresh(family)

    user = User(telegram_id=5555, family_id=family.id, is_admin=True)
    tier_test_session.add(user)
    tier_test_session.commit()

    mock_telegram = MagicMock()
    mock_telegram.send_message = AsyncMock()

    billing_service = LemonSqueezyBillingService(mock_telegram)

    webhook_payload = {
        "meta": {
            "event_name": "subscription_created",
            "custom_data": {
                "family_id": str(family.id),
                "chat_id": "5555"
            }
        },
        "data": {
            "id": "sub_duo_001",
            "attributes": {
                "store_id": "store_999",
                "customer_id": "cust_duo_001",
                "variant_id": "var_duo_123",
                "status": "active",
                "renews_at": "2027-01-01T00:00:00Z",
                "urls": {
                    "customer_portal": "https://billing.lemonsqueezy.com/portal/duo"
                }
            }
        }
    }

    mock_bg = MagicMock()
    res = billing_service.handle_webhook_event(
        session=tier_test_session,
        event_name="subscription_created",
        payload=webhook_payload,
        background_tasks=mock_bg
    )

    assert res["status"] == "upgraded"
    assert res["plan"] == "duo_pro"

    # Verify family state
    tier_test_session.refresh(family)
    assert family.plan_type == "duo_pro"
    assert family.max_members == 2
    assert family.subscription_status == "active"
    assert family.customer_portal_url == "https://billing.lemonsqueezy.com/portal/duo"

    # Verify confirmation message was scheduled
    mock_bg.add_task.assert_called_with(
        mock_telegram.send_message,
        chat_id=5555,
        text=DUO_PRO_CONFIRMATION
    )


@pytest.mark.anyio
async def test_handle_upgrade_command_shows_all_three_tiers():
    """Verify /upgrade displays all 3 tiers with updated pricing in the inline keyboard."""
    mock_telegram = MagicMock()
    mock_telegram.send_message = AsyncMock()
    billing_service = LemonSqueezyBillingService(mock_telegram)

    family_id = uuid4()
    family = Family(id=family_id, name="Demo Family", plan_type="free")
    user = User(telegram_id=777, family_id=family_id, is_admin=True)
    mock_bg = MagicMock()

    with patch.object(settings, "ENABLE_SUBSCRIPTIONS", True), \
         patch.object(billing_service, "create_checkout_url", AsyncMock(side_effect=lambda f, c, plan, **kw: f"https://checkout.test/{plan}")):
        
        await billing_service.handle_upgrade_command(
            background_tasks=mock_bg,
            text="/upgrade",
            user=user,
            family=family,
            chat_id=777
        )

        assert mock_bg.add_task.called
        call_kwargs = mock_bg.add_task.call_args.kwargs
        reply_markup = call_kwargs.get("reply_markup", {})
        buttons = reply_markup.get("inline_keyboard", [])

        # Must have 3 buttons: Solo, Duo, and Family
        assert len(buttons) == 3
        assert "Solo Pro ($4.99 / mo)" in buttons[0][0]["text"]
        assert "Duo Pro ($7.99 / mo)" in buttons[1][0]["text"]
        assert "Family Pro ($11.99 / mo)" in buttons[2][0]["text"]
        assert "https://checkout.test/duo_pro" == buttons[1][0]["url"]


@pytest.mark.anyio
async def test_handle_upgrade_annual_shows_all_three_tiers():
    """Verify /upgrade annual displays all 3 annual tiers with updated pricing."""
    mock_telegram = MagicMock()
    billing_service = LemonSqueezyBillingService(mock_telegram)

    family_id = uuid4()
    family = Family(id=family_id, name="Demo Family", plan_type="free")
    user = User(telegram_id=777, family_id=family_id, is_admin=True)
    mock_bg = MagicMock()

    with patch.object(settings, "ENABLE_SUBSCRIPTIONS", True), \
         patch.object(billing_service, "create_checkout_url", AsyncMock(side_effect=lambda f, c, plan, **kw: f"https://checkout.test/{plan}")):
        
        await billing_service.handle_upgrade_command(
            background_tasks=mock_bg,
            text="/upgrade annual",
            user=user,
            family=family,
            chat_id=777
        )

        assert mock_bg.add_task.called
        call_kwargs = mock_bg.add_task.call_args.kwargs
        reply_markup = call_kwargs.get("reply_markup", {})
        buttons = reply_markup.get("inline_keyboard", [])

        assert len(buttons) == 3
        assert "Solo Pro Annual ($49.99/yr)" in buttons[0][0]["text"]
        assert "Duo Pro Annual ($79.99/yr)" in buttons[1][0]["text"]
        assert "Family Pro Annual ($119.99/yr)" in buttons[2][0]["text"]


@pytest.mark.anyio
async def test_handle_upgrade_duo_specific():
    """Verify /upgrade duo generates a direct checkout for Duo Pro."""
    mock_telegram = MagicMock()
    billing_service = LemonSqueezyBillingService(mock_telegram)

    family_id = uuid4()
    family = Family(id=family_id, name="Demo Family", plan_type="free")
    user = User(telegram_id=777, family_id=family_id, is_admin=True)
    mock_bg = MagicMock()

    with patch.object(settings, "ENABLE_SUBSCRIPTIONS", True), \
         patch.object(billing_service, "create_checkout_url", AsyncMock(return_value="https://checkout.test/duo_pro")):
        
        await billing_service.handle_upgrade_command(
            background_tasks=mock_bg,
            text="/upgrade duo",
            user=user,
            family=family,
            chat_id=777
        )

        assert mock_bg.add_task.called
        call_kwargs = mock_bg.add_task.call_args.kwargs
        reply_markup = call_kwargs.get("reply_markup", {})
        buttons = reply_markup.get("inline_keyboard", [])

        assert len(buttons) == 1
        assert "Duo Pro ($7.99/mo)" in buttons[0][0]["text"]
        assert "https://checkout.test/duo_pro" == buttons[0][0]["url"]
