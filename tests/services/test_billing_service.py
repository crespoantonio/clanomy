import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, patch, MagicMock
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.pool import StaticPool
from fastapi import BackgroundTasks

from src.core.config import settings
from src.db.models import Family, User
from src.services.billing.billing_service import BillingService
from src.templates.telegram_messages import (
    SELF_HOSTED_UPGRADE_MESSAGE,
    BILLING_PORTAL_MESSAGE,
    UPGRADE_MENU_INTRO,
    UPGRADE_MENU_ANNUAL_INTRO,
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


@pytest.mark.anyio
async def test_handle_upgrade_command_when_subscriptions_disabled():
    """Verify that when ENABLE_SUBSCRIPTIONS is False, /upgrade returns SELF_HOSTED_UPGRADE_MESSAGE."""
    mock_tg = MockTelegramService()
    service = BillingService(telegram_service=mock_tg)
    user = User(telegram_id=12345, is_admin=True)
    family = Family(id=uuid4(), name="Test Fam")
    bg = MagicMock()

    with patch.object(settings, "ENABLE_SUBSCRIPTIONS", False):
        res = await service.handle_upgrade_command(
            background_tasks=bg,
            text="/upgrade",
            user=user,
            family=family,
            chat_id=12345
        )

    assert res == {"status": "ok"}
    bg.add_task.assert_called_once_with(
        mock_tg.send_message,
        chat_id=12345,
        text=SELF_HOSTED_UPGRADE_MESSAGE
    )


@pytest.mark.anyio
async def test_handle_billing_command_when_subscriptions_disabled():
    """Verify that when ENABLE_SUBSCRIPTIONS is False, /billing returns SELF_HOSTED_UPGRADE_MESSAGE."""
    mock_tg = MockTelegramService()
    service = BillingService(telegram_service=mock_tg)
    user = User(telegram_id=12345, is_admin=True)
    family = Family(id=uuid4(), name="Test Fam")
    bg = MagicMock()

    with patch.object(settings, "ENABLE_SUBSCRIPTIONS", False):
        res = await service.handle_billing_command(
            background_tasks=bg,
            user=user,
            family=family,
            chat_id=12345
        )

    assert res == {"status": "ok"}
    bg.add_task.assert_called_once_with(
        mock_tg.send_message,
        chat_id=12345,
        text=SELF_HOSTED_UPGRADE_MESSAGE
    )


@pytest.mark.anyio
async def test_handle_billing_command_with_portal_url():
    """Verify that /billing serves customer portal link when family has customer_portal_url."""
    mock_tg = MockTelegramService()
    service = BillingService(telegram_service=mock_tg)
    user = User(telegram_id=12345, is_admin=True)
    family = Family(id=uuid4(), name="Test Fam", customer_portal_url="https://portal.billing.com/manage/xyz")
    bg = MagicMock()

    with patch.object(settings, "ENABLE_SUBSCRIPTIONS", True):
        res = await service.handle_billing_command(
            background_tasks=bg,
            user=user,
            family=family,
            chat_id=12345
        )

    assert res == {"status": "ok"}
    assert bg.add_task.called
    call_args = bg.add_task.call_args
    assert call_args.kwargs["chat_id"] == 12345
    assert call_args.kwargs["text"] == BILLING_PORTAL_MESSAGE
    reply_markup = call_args.kwargs["reply_markup"]
    assert reply_markup["inline_keyboard"][0][0]["url"] == "https://portal.billing.com/manage/xyz"


@pytest.mark.anyio
async def test_handle_billing_command_without_portal_url():
    """Verify that /billing informs user when no customer portal link exists."""
    mock_tg = MockTelegramService()
    service = BillingService(telegram_service=mock_tg)
    user = User(telegram_id=12345, is_admin=True)
    family = Family(id=uuid4(), name="Test Fam", customer_portal_url=None)
    bg = MagicMock()

    with patch.object(settings, "ENABLE_SUBSCRIPTIONS", True):
        res = await service.handle_billing_command(
            background_tasks=bg,
            user=user,
            family=family,
            chat_id=12345
        )

    assert res == {"status": "ok"}
    assert bg.add_task.called
    call_args = bg.add_task.call_args
    assert "No Active Billing Portal Found" in call_args.kwargs["text"]


@pytest.mark.anyio
async def test_handle_upgrade_command_paddle_failure_fallback():
    """Verify that when Paddle checkout URL creation fails/returns None, /upgrade falls back to SELF_HOSTED_UPGRADE_MESSAGE."""
    mock_tg = MockTelegramService()
    service = BillingService(telegram_service=mock_tg)
    user = User(id=uuid4(), telegram_id=12345, is_admin=True)
    family = Family(id=uuid4(), name="Test Fam")
    bg = MagicMock()

    with patch.object(settings, "ENABLE_SUBSCRIPTIONS", True), \
         patch("src.services.billing.paddle_service.PaddleService.create_checkout_url", AsyncMock(return_value=None)):
        res = await service.handle_upgrade_command(
            background_tasks=bg,
            text="/upgrade",
            user=user,
            family=family,
            chat_id=12345
        )

    assert res == {"status": "ok"}
    assert bg.add_task.called
    call_args = bg.add_task.call_args
    assert call_args.kwargs["chat_id"] == 12345
    assert call_args.kwargs["text"] == SELF_HOSTED_UPGRADE_MESSAGE


@pytest.mark.anyio
async def test_handle_upgrade_command_specific_tier_failure_fallback():
    """Verify that when a specific tier checkout fails, /upgrade <tier> falls back to SELF_HOSTED_UPGRADE_MESSAGE."""
    mock_tg = MockTelegramService()
    service = BillingService(telegram_service=mock_tg)
    user = User(id=uuid4(), telegram_id=12345, is_admin=True)
    family = Family(id=uuid4(), name="Test Fam")

    tiers_to_test = ["/upgrade solo", "/upgrade duo", "/upgrade family", "/upgrade solo_pro_annual", "/upgrade annual"]

    for cmd in tiers_to_test:
        bg = MagicMock()
        with patch.object(settings, "ENABLE_SUBSCRIPTIONS", True), \
             patch("src.services.billing.paddle_service.PaddleService.create_checkout_url", AsyncMock(return_value=None)):
            res = await service.handle_upgrade_command(
                background_tasks=bg,
                text=cmd,
                user=user,
                family=family,
                chat_id=12345
            )

        assert res == {"status": "ok"}
        assert bg.add_task.called
        call_args = bg.add_task.call_args
        assert call_args.kwargs["chat_id"] == 12345
        assert call_args.kwargs["text"] == SELF_HOSTED_UPGRADE_MESSAGE


@pytest.mark.anyio
async def test_handle_upgrade_command_paddle_exception_fallback():
    """Verify that when an unhandled exception occurs during checkout generation, it gracefully falls back to SELF_HOSTED_UPGRADE_MESSAGE."""
    mock_tg = MockTelegramService()
    service = BillingService(telegram_service=mock_tg)
    user = User(id=uuid4(), telegram_id=12345, is_admin=True)
    family = Family(id=uuid4(), name="Test Fam")
    bg = MagicMock()

    with patch.object(settings, "ENABLE_SUBSCRIPTIONS", True), \
         patch("src.services.billing.paddle_service.PaddleService.create_checkout_url", AsyncMock(side_effect=RuntimeError("Paddle API Down"))):
        res = await service.handle_upgrade_command(
            background_tasks=bg,
            text="/upgrade",
            user=user,
            family=family,
            chat_id=12345
        )

    assert res == {"status": "ok"}
    assert bg.add_task.called
    call_args = bg.add_task.call_args
    assert call_args.kwargs["chat_id"] == 12345
    assert call_args.kwargs["text"] == SELF_HOSTED_UPGRADE_MESSAGE


@pytest.mark.anyio
async def test_handle_upgrade_command_paddle_success():
    """Verify that when Paddle checkout URL creation succeeds, the inline keyboard with checkout URLs is served."""
    mock_tg = MockTelegramService()
    service = BillingService(telegram_service=mock_tg)
    user = User(id=uuid4(), telegram_id=12345, is_admin=True)
    family = Family(id=uuid4(), name="Test Fam")
    bg = MagicMock()

    fake_checkout_url = "https://checkout.paddle.com/test_txn_123"

    with patch.object(settings, "ENABLE_SUBSCRIPTIONS", True), \
         patch("src.services.billing.paddle_service.PaddleService.create_checkout_url", AsyncMock(return_value=fake_checkout_url)):
        res = await service.handle_upgrade_command(
            background_tasks=bg,
            text="/upgrade",
            user=user,
            family=family,
            chat_id=12345
        )

    assert res == {"status": "ok"}
    assert bg.add_task.called
    call_args = bg.add_task.call_args
    assert call_args.kwargs["chat_id"] == 12345
    assert call_args.kwargs["text"] == UPGRADE_MENU_INTRO
    reply_markup = call_args.kwargs["reply_markup"]
    assert reply_markup is not None
    assert len(reply_markup["inline_keyboard"]) == 3
    assert reply_markup["inline_keyboard"][0][0]["url"] == fake_checkout_url

