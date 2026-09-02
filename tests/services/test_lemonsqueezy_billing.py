import hmac
import hashlib
import json
import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.pool import StaticPool
from fastapi import BackgroundTasks

from src.core.config import settings
from src.db.models import Family, User
from src.services.billing.lemonsqueezy_billing import LemonSqueezyBillingService
from src.templates.telegram_messages import (
    SELF_HOSTED_UPGRADE_MESSAGE,
    SOLO_PRO_CONFIRMATION,
    FAMILY_PRO_CONFIRMATION,
    SUBSCRIPTION_CANCELLED_MESSAGE,
    BILLING_PORTAL_MESSAGE,
)


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
def mock_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_verify_webhook_signature(monkeypatch):
    monkeypatch.setattr(settings, "LEMON_SQUEEZY_WEBHOOK_SECRET", "test_secret_key_12345")
    service = LemonSqueezyBillingService()

    payload = b'{"event":"test"}'
    valid_sig = hmac.new(b"test_secret_key_12345", payload, hashlib.sha256).hexdigest()

    assert service.verify_webhook_signature(payload, valid_sig) is True
    assert service.verify_webhook_signature(payload, "invalid_signature") is False
    assert service.verify_webhook_signature(b'tampered', valid_sig) is False


def test_handle_webhook_subscription_created(mock_db, monkeypatch):
    mock_tg = MockTelegramService()
    service = LemonSqueezyBillingService(telegram_service=mock_tg)

    family = Family(name="Test Fam", plan_type="free", subscription_status="expired")
    mock_db.add(family)
    mock_db.commit()
    mock_db.refresh(family)

    user = User(telegram_id=999888, family_id=family.id)
    mock_db.add(user)
    mock_db.commit()

    payload = {
        "meta": {
            "event_name": "subscription_created",
            "custom_data": {
                "family_id": str(family.id),
                "chat_id": 999888,
                "plan_type": "solo_pro"
            }
        },
        "data": {
            "id": "ls_sub_1001",
            "attributes": {
                "customer_id": 555,
                "renews_at": "2026-10-02T12:00:00Z",
                "urls": {
                    "customer_portal": "https://app.lemonsqueezy.com/my-orders/portal-token-123"
                }
            }
        }
    }

    bg_tasks = BackgroundTasks()
    res = service.handle_webhook_event(mock_db, "subscription_created", payload, bg_tasks)

    assert res["status"] == "upgraded"
    assert res["plan"] == "solo_pro"

    mock_db.refresh(family)
    assert family.subscription_status == "active"
    assert family.plan_type == "solo_pro"
    assert family.max_members == 1
    assert family.lemonsqueezy_subscription_id == "ls_sub_1001"
    assert family.lemonsqueezy_customer_id == "555"
    assert family.customer_portal_url == "https://app.lemonsqueezy.com/my-orders/portal-token-123"
    assert family.current_period_end is not None


def test_handle_webhook_subscription_cancelled(mock_db):
    mock_tg = MockTelegramService()
    service = LemonSqueezyBillingService(telegram_service=mock_tg)

    family = Family(
        name="Test Fam",
        plan_type="family_pro",
        subscription_status="active",
        lemonsqueezy_subscription_id="ls_sub_2002",
        current_period_end=datetime.now(timezone.utc) + timedelta(days=20)
    )
    mock_db.add(family)
    mock_db.commit()
    mock_db.refresh(family)

    payload = {
        "meta": {
            "event_name": "subscription_cancelled",
            "custom_data": {
                "family_id": str(family.id),
                "chat_id": 12345
            }
        },
        "data": {
            "id": "ls_sub_2002",
            "attributes": {
                "ends_at": (datetime.now(timezone.utc) + timedelta(days=20)).isoformat()
            }
        }
    }

    bg_tasks = BackgroundTasks()
    res = service.handle_webhook_event(mock_db, "subscription_cancelled", payload, bg_tasks)

    assert res["status"] == "cancelled"
    mock_db.refresh(family)
    assert family.subscription_status == "cancelled"
    assert family.plan_type == "family_pro"


def test_handle_webhook_subscription_expired(mock_db):
    mock_tg = MockTelegramService()
    service = LemonSqueezyBillingService(telegram_service=mock_tg)

    family = Family(
        name="Test Fam",
        plan_type="solo_pro",
        subscription_status="cancelled",
        lemonsqueezy_subscription_id="ls_sub_3003"
    )
    mock_db.add(family)
    mock_db.commit()
    mock_db.refresh(family)

    payload = {
        "meta": {
            "event_name": "subscription_expired",
            "custom_data": {
                "family_id": str(family.id)
            }
        },
        "data": {
            "id": "ls_sub_3003",
            "attributes": {}
        }
    }

    bg_tasks = BackgroundTasks()
    res = service.handle_webhook_event(mock_db, "subscription_expired", payload, bg_tasks)

    assert res["status"] == "expired"
    mock_db.refresh(family)
    assert family.subscription_status == "expired"
    assert family.plan_type == "free"


@pytest.mark.anyio
async def test_handle_upgrade_command_self_hosted(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_SUBSCRIPTIONS", False)
    mock_tg = MockTelegramService()
    service = LemonSqueezyBillingService(telegram_service=mock_tg)

    user = User(telegram_id=111, family_id=uuid4())
    family = Family(id=user.family_id, name="Self-hosted Fam")
    bg_tasks = BackgroundTasks()

    res = await service.handle_upgrade_command(bg_tasks, "/upgrade", user, family, 111)
    assert res["status"] == "ok"

    # Execute queued background tasks
    for task in bg_tasks.tasks:
        await task.func(*task.args, **task.kwargs)

    assert len(mock_tg.sent_messages) == 1
    assert "Self-Hosted" in mock_tg.sent_messages[0]["text"]


@pytest.mark.anyio
async def test_handle_upgrade_command_saas_fallback_url(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_SUBSCRIPTIONS", True)
    mock_tg = MockTelegramService()
    service = LemonSqueezyBillingService(telegram_service=mock_tg)

    user = User(telegram_id=222, family_id=uuid4())
    family = Family(id=user.family_id, name="SaaS Fam")
    bg_tasks = BackgroundTasks()

    res = await service.handle_upgrade_command(bg_tasks, "/upgrade", user, family, 222)
    assert res["status"] == "ok"

    for task in bg_tasks.tasks:
        await task.func(*task.args, **task.kwargs)

    assert len(mock_tg.sent_messages) == 1
    msg = mock_tg.sent_messages[0]
    assert "Solo Pro" in msg["text"]
    assert msg["reply_markup"] is not None
    assert "inline_keyboard" in msg["reply_markup"]


@pytest.mark.anyio
async def test_handle_billing_command(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_SUBSCRIPTIONS", True)
    mock_tg = MockTelegramService()
    service = LemonSqueezyBillingService(telegram_service=mock_tg)

    user = User(telegram_id=333, family_id=uuid4())
    family = Family(
        id=user.family_id,
        name="Portal Fam",
        customer_portal_url="https://app.lemonsqueezy.com/portal/my-sub-1"
    )
    bg_tasks = BackgroundTasks()

    res = await service.handle_billing_command(bg_tasks, user, family, 333)
    assert res["status"] == "ok"

    for task in bg_tasks.tasks:
        await task.func(*task.args, **task.kwargs)

    assert len(mock_tg.sent_messages) == 1
    msg = mock_tg.sent_messages[0]
    assert "billing portal" in msg["text"].lower()
    assert msg["reply_markup"]["inline_keyboard"][0][0]["url"] == "https://app.lemonsqueezy.com/portal/my-sub-1"


def test_webhook_rejects_mismatched_store_id(mock_db, monkeypatch):
    """[Security] Attacker with different Lemon Squeezy store ID cannot trigger events."""
    monkeypatch.setattr(settings, "LEMON_SQUEEZY_STORE_ID", "12345")
    mock_tg = MockTelegramService()
    service = LemonSqueezyBillingService(telegram_service=mock_tg)

    family = Family(name="Test Store Fam")
    mock_db.add(family)
    mock_db.commit()

    payload = {
        "meta": {
            "event_name": "subscription_created",
            "custom_data": {"family_id": str(family.id)}
        },
        "data": {
            "id": "sub_foreign_store",
            "attributes": {
                "store_id": "99999",  # Attacker's foreign store ID
                "status": "active"
            }
        }
    }

    bg_tasks = BackgroundTasks()
    res = service.handle_webhook_event(mock_db, "subscription_created", payload, bg_tasks)

    assert res["status"] == "ignored"
    assert res["reason"] == "Mismatched store_id"


def test_webhook_variant_id_authoritative_over_spoofed_custom_data(mock_db, monkeypatch):
    """[Security] Attacker cannot get Family Pro by spoofing custom_data when paying for Solo Pro variant."""
    monkeypatch.setattr(settings, "LEMON_SQUEEZY_SOLO_PRO_VARIANT_ID", "variant_solo_100")
    monkeypatch.setattr(settings, "LEMON_SQUEEZY_FAMILY_PRO_VARIANT_ID", "variant_fam_200")
    mock_tg = MockTelegramService()
    service = LemonSqueezyBillingService(telegram_service=mock_tg)

    family = Family(name="Attacker Fam", plan_type="free")
    mock_db.add(family)
    mock_db.commit()

    # Attacker purchased Solo Pro variant (variant_solo_100), but spoofed custom_data with family_pro
    payload = {
        "meta": {
            "event_name": "subscription_created",
            "custom_data": {
                "family_id": str(family.id),
                "plan_type": "family_pro",  # Spoofed!
                "chat_id": 1234
            }
        },
        "data": {
            "id": "sub_spoof_test",
            "attributes": {
                "variant_id": "variant_solo_100",  # Authoritative: paid for Solo Pro
                "status": "active"
            }
        }
    }

    bg_tasks = BackgroundTasks()
    res = service.handle_webhook_event(mock_db, "subscription_created", payload, bg_tasks)

    assert res["status"] == "upgraded"
    assert res["plan"] == "solo_pro"  # Authoritative variant prevailed!

    mock_db.refresh(family)
    assert family.plan_type == "solo_pro"
    assert family.max_members == 1


def test_webhook_unpaid_status_does_not_activate_pro(mock_db):
    """[Security] Subscriptions with status 'unpaid' or 'past_due' do not receive active Pro status."""
    mock_tg = MockTelegramService()
    service = LemonSqueezyBillingService(telegram_service=mock_tg)

    family = Family(name="Unpaid Fam", plan_type="free", subscription_status="expired")
    mock_db.add(family)
    mock_db.commit()

    payload = {
        "meta": {
            "event_name": "subscription_created",
            "custom_data": {
                "family_id": str(family.id),
                "plan_type": "solo_pro",
                "chat_id": 5555
            }
        },
        "data": {
            "id": "sub_unpaid_123",
            "attributes": {
                "status": "unpaid"  # Payment has not cleared
            }
        }
    }

    bg_tasks = BackgroundTasks()
    res = service.handle_webhook_event(mock_db, "subscription_created", payload, bg_tasks)

    mock_db.refresh(family)
    assert family.subscription_status == "unpaid"
    # No congratulatory Telegram message sent
    assert len(mock_tg.sent_messages) == 0


def test_has_unlimited_access_expired_beyond_grace_period(monkeypatch):
    """[Security] Subscriptions past their current_period_end + 48h grace window fail unlimited access."""
    from src.services.subscription_service import has_unlimited_access
    monkeypatch.setattr(settings, "ENABLE_SUBSCRIPTIONS", True)

    now = datetime.now(timezone.utc)
    # Expired 3 days ago (> 48h grace)
    expired_end = now - timedelta(days=3)

    family = Family(
        name="Stale Subscriber",
        plan_type="solo_pro",
        subscription_status="active",
        current_period_end=expired_end
    )

    assert has_unlimited_access(family, now=now) is False

    # Within 24h of period end (within 48h grace period for delayed webhook delivery)
    recent_end = now - timedelta(hours=24)
    family.current_period_end = recent_end
    assert has_unlimited_access(family, now=now) is True

