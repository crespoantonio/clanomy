import pytest
from unittest.mock import patch
from datetime import datetime, timezone
from sqlmodel import Session, create_engine, SQLModel
from sqlalchemy.pool import StaticPool

from src.db.models import Family, User
from src.services.subscription_service import can_log_transaction, has_unlimited_access
from src.core.config import settings

@pytest.fixture
def session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as sess:
        yield sess
    SQLModel.metadata.drop_all(engine)

def test_self_hosted_unlimited_access_and_quota(session):
    """When ENABLE_SUBSCRIPTIONS is False, all families have unlimited access regardless of plan or tx count."""
    family = Family(
        name="Self Hosted Fam",
        plan_type="free",
        monthly_tx_count=150,
        last_reset_month=datetime.now(timezone.utc).strftime("%Y-%m"),
        subscription_status="expired",
    )
    session.add(family)
    session.commit()

    with patch.object(settings, "ENABLE_SUBSCRIPTIONS", False):
        assert has_unlimited_access(family) is True
        assert can_log_transaction(family, limit=30) is True

def test_saas_mode_enforces_quota(session):
    """When ENABLE_SUBSCRIPTIONS is True, normal SaaS limits and statuses apply."""
    family = Family(
        name="SaaS Free Fam",
        plan_type="free",
        monthly_tx_count=35,
        last_reset_month=datetime.now(timezone.utc).strftime("%Y-%m"),
        subscription_status="active",
    )
    session.add(family)
    session.commit()

    with patch.object(settings, "ENABLE_SUBSCRIPTIONS", True):
        assert has_unlimited_access(family) is False
        assert can_log_transaction(family, limit=30) is False

def test_upgrade_command_in_self_hosted_mode(app_client, mock_telegram, telegram_payload_factory):
    """In self-hosted mode, /upgrade returns a friendly self-hosted message and sends NO invoices."""
    # Register user via /start
    app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/start", user_id=987654321),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    mock_telegram.messages.clear()

    with patch.object(settings, "ENABLE_SUBSCRIPTIONS", False):
        response = app_client.post(
            "/api/v1/telegram/webhook",
            json=telegram_payload_factory(text="/upgrade", user_id=987654321),
            headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
        )

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

        # Verify friendly self-hosted message was sent
        assert len(mock_telegram.messages) == 1
        msg = mock_telegram.messages[0]["text"]
        assert "Self-Hosted Clanomy" in msg
        assert "fully unlocked" in msg

def test_allowed_telegram_users_access_granted(app_client, mock_telegram, telegram_payload_factory):
    """Users in ALLOWED_TELEGRAM_USERS list are permitted through."""
    with patch.object(settings, "ALLOWED_TELEGRAM_USERS", "tony_crespo, 999888"):
        # By username
        resp1 = app_client.post(
            "/api/v1/telegram/webhook",
            json=telegram_payload_factory(text="/start", user_id=123, username="tony_crespo"),
            headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
        )
        assert resp1.status_code == 200
        assert "Welcome to Clanomy" in mock_telegram.messages[0]["text"]
        mock_telegram.messages.clear()

        # By numeric ID
        resp2 = app_client.post(
            "/api/v1/telegram/webhook",
            json=telegram_payload_factory(text="/start", user_id=999888, username="another_name"),
            headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
        )
        assert resp2.status_code == 200
        assert "Welcome to Clanomy" in mock_telegram.messages[0]["text"]

def test_allowed_telegram_users_access_denied(app_client, mock_telegram, telegram_payload_factory):
    """Unauthorized users are rejected immediately with Private Instance notice."""
    with patch.object(settings, "ALLOWED_TELEGRAM_USERS", "tony_crespo, 999888"):
        resp = app_client.post(
            "/api/v1/telegram/webhook",
            json=telegram_payload_factory(text="/start", user_id=55555, username="stranger"),
            headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
        )
        assert resp.status_code == 200
        assert len(mock_telegram.messages) == 1
        assert "Private Instance" in mock_telegram.messages[0]["text"]
