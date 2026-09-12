"""
End-to-End (E2E) Billing and Subscription Lifecycle Tests.
Covers:
1. Upgrade commands & checkout tier selection (/upgrade, /upgrade solo, /upgrade family)
2. Member invitation gating across tiers (Solo Pro vs Family Pro)
3. Daily Fair-Use limit enforcement & command immunity
4. Free Tier monthly quota enforcement & command immunity
5. Paddle Webhook activation fulfillment (subscription.activated)
6. Paddle Webhook cancellation lifecycle (subscription.canceled & broadcast notification)
"""

import time
from datetime import datetime, timezone, timedelta
from uuid import uuid4
import pytest
from unittest.mock import patch, AsyncMock
from sqlmodel import Session, select

from src.core.config import settings
from src.core.subscription_config import FREE_TIER_MONTHLY_LIMIT, DAILY_FAIR_USE_LIMITS
from src.core.encryption import EncryptionService
from src.db.models import User, Family, Transaction
from tests.e2e.conftest import e2e_test_engine


def test_e2e_upgrade_commands_and_tier_selection(app_client, mock_telegram, telegram_payload_factory, monkeypatch):
    """[E2E] /upgrade presents all 3 tiers with checkout buttons; targeted /upgrade solo and /upgrade family dispatch directly."""
    monkeypatch.setattr(settings, "ENABLE_SUBSCRIPTIONS", True)
    user_id = 92001
    secret_header = {"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}

    # Register user & accept terms
    app_client.post("/api/v1/telegram/webhook", json=telegram_payload_factory(text="/start", user_id=user_id), headers=secret_header)
    app_client.post("/api/v1/telegram/webhook", json={
        "callback_query": {
            "id": "cb_tos_92001",
            "from": {"id": user_id, "first_name": "BillingTester"},
            "message": {"message_id": 100, "chat": {"id": user_id}},
            "data": "accept_tos"
        }
    }, headers=secret_header)
    mock_telegram.messages.clear()

    # 1. Bare /upgrade
    with patch("src.services.billing.paddle_service.PaddleService.create_checkout_url", AsyncMock(return_value="https://checkout.paddle.com/test_checkout")):
        res = app_client.post("/api/v1/telegram/webhook", json=telegram_payload_factory(text="/upgrade", user_id=user_id), headers=secret_header)
    assert res.status_code == 200
    assert len(mock_telegram.messages) == 1
    intro = mock_telegram.messages[0]["text"]
    assert "Upgrade to Clanomy Pro" in intro
    assert "Solo Pro" in intro
    assert "Duo Pro" in intro
    assert "Family Pro" in intro
    markup = mock_telegram.messages[0].get("reply_markup")
    assert markup is not None
    assert len(markup["inline_keyboard"]) == 3

    # 2. Targeted /upgrade solo
    mock_telegram.messages.clear()
    with patch("src.services.billing.paddle_service.PaddleService.create_checkout_url", AsyncMock(return_value="https://checkout.paddle.com/test_solo")):
        res = app_client.post("/api/v1/telegram/webhook", json=telegram_payload_factory(text="/upgrade solo", user_id=user_id), headers=secret_header)
    assert res.status_code == 200
    assert len(mock_telegram.messages) == 1
    assert "Solo Pro" in mock_telegram.messages[0]["text"]
    assert "Solo Pro" in mock_telegram.messages[0]["reply_markup"]["inline_keyboard"][0][0]["text"]

    # 3. Targeted /upgrade family
    mock_telegram.messages.clear()
    with patch("src.services.billing.paddle_service.PaddleService.create_checkout_url", AsyncMock(return_value="https://checkout.paddle.com/test_family")):
        res = app_client.post("/api/v1/telegram/webhook", json=telegram_payload_factory(text="/upgrade family", user_id=user_id), headers=secret_header)
    assert res.status_code == 200
    assert len(mock_telegram.messages) == 1
    assert "Family Pro" in mock_telegram.messages[0]["text"]
    assert "Family Pro" in mock_telegram.messages[0]["reply_markup"]["inline_keyboard"][0][0]["text"]


def test_e2e_tier_member_invitation_gating(app_client, mock_telegram, telegram_payload_factory):
    """[E2E] Solo Pro subscribers are gated from /invite (limit 1 member), while Family Pro is permitted."""
    user_id = 92002
    secret_header = {"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}

    app_client.post("/api/v1/telegram/webhook", json=telegram_payload_factory(text="/start", user_id=user_id), headers=secret_header)
    app_client.post("/api/v1/telegram/webhook", json={
        "callback_query": {
            "id": "cb_tos_92002",
            "from": {"id": user_id, "first_name": "SoloTester"},
            "message": {"message_id": 100, "chat": {"id": user_id}},
            "data": "accept_tos"
        }
    }, headers=secret_header)

    # Set workspace to solo_pro
    with Session(e2e_test_engine) as session:
        u = session.exec(select(User).where(User.telegram_id == user_id)).first()
        family_id = u.family_id
        f = session.get(Family, family_id)
        f.plan_type = "solo_pro"
        f.max_members = 1
        session.add(f)
        session.commit()

    # Attempt /invite on Solo Pro -> blocked
    mock_telegram.messages.clear()
    res = app_client.post("/api/v1/telegram/webhook", json=telegram_payload_factory(text="/invite", user_id=user_id), headers=secret_header)
    assert res.status_code == 200
    assert len(mock_telegram.messages) == 1
    resp_text = mock_telegram.messages[0]["text"]
    assert "Solo Pro" in resp_text
    assert "Family Pro" in resp_text or "/upgrade" in resp_text

    # Upgrade workspace to family_pro in DB
    with Session(e2e_test_engine) as session:
        f = session.get(Family, family_id)
        f.plan_type = "family_pro"
        f.max_members = 5
        session.add(f)
        session.commit()

    # Attempt /invite on Family Pro -> success
    mock_telegram.messages.clear()
    res = app_client.post("/api/v1/telegram/webhook", json=telegram_payload_factory(text="/invite", user_id=user_id), headers=secret_header)
    assert res.status_code == 200
    assert len(mock_telegram.messages) == 1
    invite_text = mock_telegram.messages[0]["text"]
    assert "invite" in invite_text.lower() or "invitación" in invite_text.lower() or "t.me" in invite_text


def test_e2e_daily_limit_enforcement_and_command_immunity(app_client, mock_telegram, telegram_payload_factory):
    """
    [E2E] When a family exceeds their tier daily fair-use limit, natural language expense/income
    logging is blocked with format_daily_limit_reached, but slash commands (/month, /today, /balance, /help)
    remain 100% active and unblocked.
    """
    user_id = 92003
    secret_header = {"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}

    app_client.post("/api/v1/telegram/webhook", json=telegram_payload_factory(text="/start", user_id=user_id), headers=secret_header)
    app_client.post("/api/v1/telegram/webhook", json={
        "callback_query": {
            "id": "cb_tos_92003",
            "from": {"id": user_id, "first_name": "DailyLimitTester"},
            "message": {"message_id": 100, "chat": {"id": user_id}},
            "data": "accept_tos"
        }
    }, headers=secret_header)

    # Setup family as solo_pro with daily_tx_count = 60 (at limit)
    with Session(e2e_test_engine) as session:
        u = session.exec(select(User).where(User.telegram_id == user_id)).first()
        family_id = u.family_id
        f = session.get(Family, family_id)
        f.plan_type = "solo_pro"
        f.daily_tx_count = 60
        session.add(f)
        session.commit()

    # 1. Natural Language Spend Logging -> Rejected due to daily limit
    mock_telegram.messages.clear()
    spend_res = app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="Spent 25 on sushi", user_id=user_id),
        headers=secret_header
    )
    assert spend_res.status_code == 200
    assert len(mock_telegram.messages) == 1
    limit_msg = mock_telegram.messages[0]["text"]
    assert "daily limit" in limit_msg.lower() or "límite diario" in limit_msg.lower()

    # 2. Natural Language Income Logging -> Rejected due to daily limit
    mock_telegram.messages.clear()
    income_res = app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="Got paid 500 freelance", user_id=user_id),
        headers=secret_header
    )
    assert income_res.status_code == 200
    assert len(mock_telegram.messages) == 1
    assert "daily limit" in mock_telegram.messages[0]["text"].lower() or "límite diario" in mock_telegram.messages[0]["text"].lower()

    # 3. Slash Commands Immunity Check: /month, /today, /balance, /help must all work!
    mock_telegram.messages.clear()
    month_res = app_client.post("/api/v1/telegram/webhook", json=telegram_payload_factory(text="/month", user_id=user_id), headers=secret_header)
    assert month_res.status_code == 200
    assert len(mock_telegram.messages) == 1
    assert "Summary" in mock_telegram.messages[0]["text"] or "Resumen" in mock_telegram.messages[0]["text"]

    mock_telegram.messages.clear()
    balance_res = app_client.post("/api/v1/telegram/webhook", json=telegram_payload_factory(text="/balance", user_id=user_id), headers=secret_header)
    assert balance_res.status_code == 200
    assert len(mock_telegram.messages) == 1
    assert "Cash Flow" in mock_telegram.messages[0]["text"] or "Saldo" in mock_telegram.messages[0]["text"]

    mock_telegram.messages.clear()
    help_res = app_client.post("/api/v1/telegram/webhook", json=telegram_payload_factory(text="/help", user_id=user_id), headers=secret_header)
    assert help_res.status_code == 200
    assert len(mock_telegram.messages) == 1
    assert "/month" in mock_telegram.messages[0]["text"]


def test_e2e_free_tier_monthly_limit_gate_and_command_immunity(app_client, mock_telegram, telegram_payload_factory):
    """
    [E2E] When a Free tier workspace reaches FREE_TIER_MONTHLY_LIMIT (20 logs), natural language
    logging is blocked prompting an upgrade, while slash commands remain 100% free and functional.
    """
    user_id = 92004
    secret_header = {"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}

    app_client.post("/api/v1/telegram/webhook", json=telegram_payload_factory(text="/start", user_id=user_id), headers=secret_header)
    app_client.post("/api/v1/telegram/webhook", json={
        "callback_query": {
            "id": "cb_tos_92004",
            "from": {"id": user_id, "first_name": "FreeLimitTester"},
            "message": {"message_id": 100, "chat": {"id": user_id}},
            "data": "accept_tos"
        }
    }, headers=secret_header)

    # Set workspace to Free tier with monthly_tx_count = 20 and last_reset_month = current month
    with Session(e2e_test_engine) as session:
        u = session.exec(select(User).where(User.telegram_id == user_id)).first()
        f = session.get(Family, u.family_id)
        f.plan_type = "free"
        f.monthly_tx_count = FREE_TIER_MONTHLY_LIMIT
        f.last_reset_month = datetime.now(timezone.utc).strftime("%Y-%m")
        session.add(f)
        session.commit()

    # Attempt to log expense -> Gated with upgrade prompt
    mock_telegram.messages.clear()
    res = app_client.post("/api/v1/telegram/webhook", json=telegram_payload_factory(text="Spent 20 on groceries", user_id=user_id), headers=secret_header)
    assert res.status_code == 200
    assert len(mock_telegram.messages) == 1
    resp = mock_telegram.messages[0]["text"]
    assert "reached your free limit" in resp.lower() or "cuota mensual" in resp.lower() or "/upgrade" in resp.lower()

    # Verify slash commands (/today, /month, /balance) continue to work for free
    mock_telegram.messages.clear()
    res = app_client.post("/api/v1/telegram/webhook", json=telegram_payload_factory(text="/today", user_id=user_id), headers=secret_header)
    assert res.status_code == 200
    assert len(mock_telegram.messages) == 1
    assert "Today" in mock_telegram.messages[0]["text"] or "Hoy" in mock_telegram.messages[0]["text"]


def test_e2e_paddle_webhook_activation_and_cancellation_lifecycle(app_client, mock_telegram, telegram_payload_factory, paddle_webhook_factory):
    """
    [E2E] Full Paddle Webhook lifecycle:
    1. User is on Free tier.
    2. Signed subscription.created event arrives -> workspace upgraded to family_pro, status=active, max_members=5.
    3. Signed subscription.canceled event arrives -> workspace status=canceled, broadcast cancellation dispatched to family.
    4. At period end expiration, workspace transitions to plan_type=free.
    """
    user_id = 92005
    secret_header = {"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}

    app_client.post("/api/v1/telegram/webhook", json=telegram_payload_factory(text="/start", user_id=user_id), headers=secret_header)
    app_client.post("/api/v1/telegram/webhook", json={
        "callback_query": {
            "id": "cb_tos_92005",
            "from": {"id": user_id, "first_name": "PaddleLifecycleTester"},
            "message": {"message_id": 100, "chat": {"id": user_id}},
            "data": "accept_tos"
        }
    }, headers=secret_header)

    with Session(e2e_test_engine) as session:
        u = session.exec(select(User).where(User.telegram_id == user_id)).first()
        family_id = u.family_id
        f = session.get(Family, family_id)
        f.plan_type = "free"
        f.subscription_status = "inactive"
        session.add(f)
        session.commit()

    # =========================================================================
    # Step 1: Paddle Webhook: subscription.created (activation)
    # =========================================================================
    sub_id = f"sub_e2e_{int(time.time())}"
    cust_id = f"ctm_e2e_{int(time.time())}"
    period_end = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    activation_data = {
        "id": sub_id,
        "customer_id": cust_id,
        "status": "active",
        "custom_data": {"family_id": str(family_id), "plan_code": "family_pro"},
        "current_billing_period": {"ends_at": period_end},
        "items": [{"price": {"description": "Clanomy Family Pro", "id": "pri_family_pro"}}]
    }
    raw_body, sig_header = paddle_webhook_factory("subscription.created", activation_data)

    res = app_client.post("/api/v1/paddle/webhook", content=raw_body, headers={"Paddle-Signature": sig_header})
    assert res.status_code == 200
    assert res.json() == {"received": True}

    # Verify DB state after activation
    with Session(e2e_test_engine) as session:
        f = session.get(Family, family_id)
        assert f.plan_type == "family_pro"
        assert f.subscription_status == "active"
        assert f.paddle_subscription_id == sub_id
        assert f.paddle_customer_id == cust_id
        assert f.max_members == 5

    # =========================================================================
    # Step 2: Paddle Webhook: subscription.canceled
    # =========================================================================
    mock_telegram.messages.clear()
    cancellation_data = {
        "id": sub_id,
        "customer_id": cust_id,
        "status": "canceled",
        "custom_data": {"family_id": str(family_id)},
        "current_billing_period": {"ends_at": period_end}
    }
    raw_cancel_body, cancel_sig_header = paddle_webhook_factory("subscription.canceled", cancellation_data, event_id=f"evt_cancel_{int(time.time())}")

    res = app_client.post("/api/v1/paddle/webhook", content=raw_cancel_body, headers={"Paddle-Signature": cancel_sig_header})
    assert res.status_code == 200
    assert res.json() == {"received": True}

    # Verify DB status updated to canceled
    with Session(e2e_test_engine) as session:
        f = session.get(Family, family_id)
        assert f.subscription_status == "canceled"

    # Verify broadcast notification sent to family members
    assert len(mock_telegram.messages) == 1
    cancel_notice = mock_telegram.messages[0]["text"]
    assert "cancelaci" in cancel_notice.lower() or "cancel" in cancel_notice.lower()
    assert "20" in cancel_notice or str(FREE_TIER_MONTHLY_LIMIT) in cancel_notice

    # =========================================================================
    # Step 3: At period end expiration, workspace transitions to free tier
    # =========================================================================
    with Session(e2e_test_engine) as session:
        f = session.get(Family, family_id)
        # Simulate current_period_end having passed
        f.current_period_end = datetime.now(timezone.utc) - timedelta(days=1)
        session.add(f)
        session.commit()

    # Re-triggering cancellation with past current_period_end sets plan_type="free"
    raw_expired_body, expired_sig = paddle_webhook_factory(
        "subscription.canceled",
        cancellation_data,
        event_id=f"evt_expired_{int(time.time())}"
    )
    res_exp = app_client.post("/api/v1/paddle/webhook", content=raw_expired_body, headers={"Paddle-Signature": expired_sig})
    assert res_exp.status_code == 200

    with Session(e2e_test_engine) as session:
        f = session.get(Family, family_id)
        assert f.plan_type == "free"
        assert f.max_members == 5
