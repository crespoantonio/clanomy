import pytest

def test_webhook_invalid_secret(app_client, telegram_payload_factory):
    """[P0] Webhook should reject requests with invalid secret token."""
    payload = telegram_payload_factory(text="/start")
    response = app_client.post(
        "/api/v1/telegram/webhook",
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"}
    )
    assert response.status_code == 403
    assert response.json() == {"detail": "Invalid secret token"}

def test_webhook_success_registration(app_client, mock_telegram, telegram_payload_factory):
    """[P0] Webhook should register a new user on /start command."""
    payload = telegram_payload_factory(text="/start", user_id=999, first_name="Bruce")
    
    response = app_client.post(
        "/api/v1/telegram/webhook",
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    
    # Verify the welcome message was sent
    assert len(mock_telegram.messages) == 1
    welcome = mock_telegram.messages[0]["text"]
    assert "Welcome to Clanomy" in welcome
    assert "60-Day Family Pro Trial" in welcome
    assert "Send a voice note" in welcome
    assert "Type an expense" in welcome
    assert "Type an income" in welcome
    assert "Ask a question" in welcome

def test_webhook_log_text_expense(app_client, mock_telegram, telegram_payload_factory):
    """[P0] Webhook should process text expense and extract via LLM."""
    # First register the user
    app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/start", user_id=888),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    mock_telegram.messages.clear()
    
    # Log an expense
    payload = telegram_payload_factory(text="Spent 25.50 on dinner at McDonald's", user_id=888)
    
    response = app_client.post(
        "/api/v1/telegram/webhook",
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    
    assert len(mock_telegram.messages) > 0
    response_text = mock_telegram.messages[-1]["text"]
    assert "25.5" in response_text
    # We expect 'dinner' or 'McDonald' to be in the concept
    assert "dinner" in response_text.lower() or "mcdonald" in response_text.lower()

def test_webhook_zero_spending_fallback(app_client, mock_telegram, telegram_payload_factory):
    """[P3] Webhook should handle queries with zero spending gracefully."""
    app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/start", user_id=777),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    mock_telegram.messages.clear()
    
    payload = telegram_payload_factory(text="How much did I spend yesterday?", user_id=777)
    
    response = app_client.post(
        "/api/v1/telegram/webhook",
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    
    assert response.status_code == 200
    assert len(mock_telegram.messages) > 0
    response_text = mock_telegram.messages[-1]["text"]
    assert "0.00" in response_text or "haven't logged any expenses" in response_text.lower() or "zero" in response_text.lower()

def test_webhook_log_text_income(app_client, mock_telegram, telegram_payload_factory):
    """[P0] Webhook should process text income and reply with income badge & cash flow snapshot."""
    # First register the user
    app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/start", user_id=666),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    mock_telegram.messages.clear()
    
    # Log an income
    payload = telegram_payload_factory(text="Got paid 3500 salary from Acme Corp", user_id=666)
    
    response = app_client.post(
        "/api/v1/telegram/webhook",
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    
    assert len(mock_telegram.messages) > 0
    response_text = mock_telegram.messages[-1]["text"]
    assert "💰 Income Logged:" in response_text
    assert "3,500.00" in response_text
    assert "Salary" in response_text
    assert "Snapshot:" in response_text
    assert "Total In:" in response_text
    assert "Net Savings:" in response_text

def test_webhook_upgrade_command_general(app_client, mock_telegram, telegram_payload_factory):
    """[P0] Webhook should handle /upgrade and dispatch tier explanation and both invoices."""
    # Register user
    app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/start", user_id=4441),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    mock_telegram.messages.clear()

    # Trigger /upgrade
    payload = telegram_payload_factory(text="/upgrade", user_id=4441)
    response = app_client.post(
        "/api/v1/telegram/webhook",
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    # Verify intro message + both invoices
    assert len(mock_telegram.messages) == 3
    intro = mock_telegram.messages[0]["text"]
    assert "Upgrade to Clanomy Pro" in intro
    assert "Solo Pro (200 Stars / month)" in intro
    assert "Family Pro (450 Stars / month)" in intro

    invoices = [m for m in mock_telegram.messages if m.get("type") == "invoice"]
    assert len(invoices) == 2
    plans = {inv["plan_type"] for inv in invoices}
    assert plans == {"solo_pro", "family_pro"}
    for inv in invoices:
        assert inv["payload"].startswith(f"sub_{inv['plan_type']}_")

def test_webhook_upgrade_command_solo_tier(app_client, mock_telegram, telegram_payload_factory):
    """[P1] Webhook should handle '/upgrade solo' and dispatch Solo Pro invoice directly."""
    app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/start", user_id=4442),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    mock_telegram.messages.clear()

    payload = telegram_payload_factory(text="/upgrade solo", user_id=4442)
    response = app_client.post(
        "/api/v1/telegram/webhook",
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert response.status_code == 200
    assert len(mock_telegram.messages) == 1
    assert mock_telegram.messages[0].get("type") == "invoice"
    assert mock_telegram.messages[0]["plan_type"] == "solo_pro"
    assert mock_telegram.messages[0]["payload"].startswith("sub_solo_pro_")

def test_webhook_upgrade_command_family_tier(app_client, mock_telegram, telegram_payload_factory):
    """[P1] Webhook should handle '/upgrade family' and dispatch Family Pro invoice directly."""
    app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/start", user_id=4443),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    mock_telegram.messages.clear()

    payload = telegram_payload_factory(text="/upgrade family", user_id=4443)
    response = app_client.post(
        "/api/v1/telegram/webhook",
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert response.status_code == 200
    assert len(mock_telegram.messages) == 1
    assert mock_telegram.messages[0].get("type") == "invoice"
    assert mock_telegram.messages[0]["plan_type"] == "family_pro"
    assert mock_telegram.messages[0]["payload"].startswith("sub_family_pro_")

def test_webhook_solo_pro_invite_blocked(app_client, mock_telegram, telegram_payload_factory):
    """[P0] If a Solo Pro subscriber attempts /invite, inform them Family Pro is required."""
    from src.db.session import engine
    from sqlmodel import Session, select
    from src.db.models import Family, User

    user_id = 4444
    app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/start", user_id=user_id),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )

    # Set workspace plan to solo_pro
    with Session(engine) as session:
        user = session.exec(select(User).where(User.telegram_id == user_id)).first()
        family = session.get(Family, user.family_id)
        family.plan_type = "solo_pro"
        session.add(family)
        session.commit()

    mock_telegram.messages.clear()

    # Attempt to invite
    payload = telegram_payload_factory(text="/invite", user_id=user_id)
    response = app_client.post(
        "/api/v1/telegram/webhook",
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert response.status_code == 200
    assert len(mock_telegram.messages) > 0
    resp_text = mock_telegram.messages[-1]["text"]
    assert "Solo Pro" in resp_text
    assert "Family Pro" in resp_text
    assert "/upgrade" in resp_text

def test_webhook_pre_checkout_query_valid(app_client, mock_telegram, telegram_payload_factory):
    """[P0] Webhook answers pre_checkout_query with ok=True for valid paid plan."""
    payload = telegram_payload_factory(
        pre_checkout_query={
            "id": "query_valid_123",
            "from": {"id": 9001, "first_name": "Tony", "username": "tony"},
            "currency": "XTR",
            "total_amount": 150,
            "invoice_payload": "sub_solo_pro_123e4567-e89b-12d3-a456-426614174000"
        }
    )
    response = app_client.post(
        "/api/v1/telegram/webhook",
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    
    answers = [m for m in mock_telegram.messages if m.get("type") == "pre_checkout_answer"]
    assert len(answers) == 1
    assert answers[0]["pre_checkout_query_id"] == "query_valid_123"
    assert answers[0]["ok"] is True

def test_webhook_pre_checkout_query_invalid(app_client, mock_telegram, telegram_payload_factory):
    """[P0] Webhook answers pre_checkout_query with ok=False for invalid/unauthorized payload."""
    payload = telegram_payload_factory(
        pre_checkout_query={
            "id": "query_invalid_456",
            "from": {"id": 9002, "first_name": "Tony", "username": "tony"},
            "currency": "XTR",
            "total_amount": 150,
            "invoice_payload": "sub_lifetime_pro"
        }
    )
    response = app_client.post(
        "/api/v1/telegram/webhook",
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    answers = [m for m in mock_telegram.messages if m.get("type") == "pre_checkout_answer"]
    assert len(answers) == 1
    assert answers[0]["pre_checkout_query_id"] == "query_invalid_456"
    assert answers[0]["ok"] is False
    assert "Invalid or unsupported subscription plan" in answers[0]["error_message"]

def test_webhook_successful_payment_solo_pro(app_client, mock_telegram, telegram_payload_factory):
    """[P0] Webhook processes successful_payment for Solo Pro and activates subscription."""
    from src.db.session import engine
    from sqlmodel import Session, select
    from src.db.models import Family, User

    user_id = 9101
    app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/start", user_id=user_id),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    mock_telegram.messages.clear()

    with Session(engine) as session:
        user = session.exec(select(User).where(User.telegram_id == user_id)).first()
        fam_id = str(user.family_id)

    # Trigger successful payment
    payload = telegram_payload_factory(
        user_id=user_id,
        successful_payment={
            "currency": "XTR",
            "total_amount": 150,
            "invoice_payload": f"sub_solo_pro_{fam_id}",
            "telegram_payment_charge_id": "charge_solo_123",
            "provider_payment_charge_id": ""
        }
    )
    response = app_client.post(
        "/api/v1/telegram/webhook",
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert response.status_code == 200

    with Session(engine) as session:
        user = session.exec(select(User).where(User.telegram_id == user_id)).first()
        family = session.get(Family, user.family_id)
        assert family.plan_type == "solo_pro"
        assert family.subscription_status == "active"
        assert family.max_members == 1
        assert family.telegram_payment_charge_id == "charge_solo_123"
        assert family.current_period_end is not None

    assert len(mock_telegram.messages) == 1
    welcome = mock_telegram.messages[0]["text"]
    assert "Welcome to Clanomy Solo Pro" in welcome
    assert "unlocked unlimited voice and text" in welcome

def test_webhook_successful_payment_family_pro(app_client, mock_telegram, telegram_payload_factory):
    """[P0] Webhook processes successful_payment for Family Pro and updates max_members to 5."""
    from src.db.session import engine
    from sqlmodel import Session, select
    from src.db.models import Family, User

    user_id = 9102
    app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/start", user_id=user_id),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    mock_telegram.messages.clear()

    with Session(engine) as session:
        user = session.exec(select(User).where(User.telegram_id == user_id)).first()
        fam_id = str(user.family_id)

    payload = telegram_payload_factory(
        user_id=user_id,
        successful_payment={
            "currency": "XTR",
            "total_amount": 300,
            "invoice_payload": f"sub_family_pro_{fam_id}",
            "telegram_payment_charge_id": "charge_fam_456"
        }
    )
    response = app_client.post(
        "/api/v1/telegram/webhook",
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert response.status_code == 200

    with Session(engine) as session:
        user = session.exec(select(User).where(User.telegram_id == user_id)).first()
        family = session.get(Family, user.family_id)
        assert family.plan_type == "family_pro"
        assert family.subscription_status == "active"
        assert family.max_members == 5
        assert family.telegram_payment_charge_id == "charge_fam_456"

    assert len(mock_telegram.messages) == 1
    welcome = mock_telegram.messages[0]["text"]
    assert "Welcome to Clanomy Family Pro" in welcome
    assert "shared family ledger for up to 5 members" in welcome

def test_webhook_successful_payment_solo_pro_notifies_other_members(app_client, mock_telegram, telegram_payload_factory):
    """[P1] When multi-member family switches to Solo Pro, notify non-admin members."""
    from src.db.session import engine
    from sqlmodel import Session, select
    from src.db.models import Family, User

    admin_id = 9201
    member_id = 9202

    # Register admin
    app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/start", user_id=admin_id),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )

    # Attach second member to same family
    with Session(engine) as session:
        admin_user = session.exec(select(User).where(User.telegram_id == admin_id)).first()
        fam_id = admin_user.family_id
        member_user = User(
            telegram_id=member_id,
            username="member_two",
            full_name="Member Two",
            family_id=fam_id
        )
        session.add(member_user)
        session.commit()

    mock_telegram.messages.clear()

    # Admin purchases Solo Pro
    payload = telegram_payload_factory(
        user_id=admin_id,
        successful_payment={
            "currency": "XTR",
            "total_amount": 150,
            "invoice_payload": f"sub_solo_pro_{fam_id}",
            "telegram_payment_charge_id": "charge_solo_multi"
        }
    )
    response = app_client.post(
        "/api/v1/telegram/webhook",
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert response.status_code == 200

    # Admin receives welcome, Member receives plan update notification
    assert len(mock_telegram.messages) == 2
    admin_msg = next(m for m in mock_telegram.messages if m["chat_id"] == admin_id)
    member_msg = next(m for m in mock_telegram.messages if m["chat_id"] == member_id)

    assert "Welcome to Clanomy Solo Pro" in admin_msg["text"]
    assert "Workspace Plan Update" in member_msg["text"]
    assert "Solo Pro" in member_msg["text"]
    assert "/leavefamily" in member_msg["text"]

def test_webhook_successful_payment_protects_lifetime_pro(app_client, mock_telegram, telegram_payload_factory):
    """[P0] External webhook cannot downgrade or overwrite lifetime_pro."""
    from src.db.session import engine
    from sqlmodel import Session, select
    from src.db.models import Family, User

    user_id = 9301
    app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/start", user_id=user_id),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )

    with Session(engine) as session:
        user = session.exec(select(User).where(User.telegram_id == user_id)).first()
        family = session.get(Family, user.family_id)
        family.plan_type = "lifetime_pro"
        family.subscription_status = "active"
        session.add(family)
        session.commit()
        fam_id = str(family.id)

    mock_telegram.messages.clear()

    payload = telegram_payload_factory(
        user_id=user_id,
        successful_payment={
            "currency": "XTR",
            "total_amount": 150,
            "invoice_payload": f"sub_solo_pro_{fam_id}",
            "telegram_payment_charge_id": "charge_lifetime_safe"
        }
    )
    response = app_client.post(
        "/api/v1/telegram/webhook",
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert response.status_code == 200

    with Session(engine) as session:
        user = session.exec(select(User).where(User.telegram_id == user_id)).first()
        family = session.get(Family, user.family_id)
        assert family.plan_type == "lifetime_pro"
        assert family.subscription_status == "active"
        assert family.telegram_payment_charge_id == "charge_lifetime_safe"

    assert len(mock_telegram.messages) == 1
    assert "Lifetime Pro Active" in mock_telegram.messages[0]["text"]

def test_webhook_refunded_payment_transitions_to_free(app_client, mock_telegram, telegram_payload_factory):
    """[P1] Refunded payment transitions family to free tier with data safety reassurance."""
    from src.db.session import engine
    from sqlmodel import Session, select
    from src.db.models import Family, User

    user_id = 9401
    app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/start", user_id=user_id),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )

    with Session(engine) as session:
        user = session.exec(select(User).where(User.telegram_id == user_id)).first()
        family = session.get(Family, user.family_id)
        family.plan_type = "family_pro"
        family.subscription_status = "active"
        session.add(family)
        session.commit()
        fam_id = str(family.id)

    mock_telegram.messages.clear()

    payload = telegram_payload_factory(
        user_id=user_id,
        refunded_payment={
            "currency": "XTR",
            "total_amount": 300,
            "invoice_payload": f"sub_family_pro_{fam_id}",
            "telegram_payment_charge_id": "charge_refunded_123"
        }
    )
    response = app_client.post(
        "/api/v1/telegram/webhook",
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert response.status_code == 200

    with Session(engine) as session:
        user = session.exec(select(User).where(User.telegram_id == user_id)).first()
        family = session.get(Family, user.family_id)
        assert family.plan_type == "free"
        assert family.subscription_status == "expired"

    assert len(mock_telegram.messages) == 1
    refund_text = mock_telegram.messages[0]["text"]
    assert "Subscription Update" in refund_text
    assert "Free tier" in refund_text
    assert "100% safe" in refund_text

def test_webhook_lifecycle_renewal(app_client):
    """[P0] Webhook processes renewal and extends current_period_end."""
    from src.db.session import engine
    from sqlmodel import Session
    from src.db.models import Family
    from datetime import datetime, timezone, timedelta
    
    with Session(engine) as session:
        family = Family(name="Test Renewal", plan_type="solo_pro", subscription_status="active", max_members=1)
        family.current_period_end = datetime.now(timezone.utc) + timedelta(days=5)
        session.add(family)
        session.commit()
        session.refresh(family)
        fam_id = str(family.id)
        old_end = family.current_period_end
        
    payload = {"family_id": fam_id, "charge_id": "charge_ren_123"}
    response = app_client.post(
        "/api/v1/telegram/webhook/renewal",
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert response.status_code == 200
    
    with Session(engine) as session:
        family = session.get(Family, family.id)
        assert family.subscription_status == "active"
        assert family.telegram_payment_charge_id == "charge_ren_123"
        assert family.current_period_end > old_end

def test_webhook_lifecycle_cancellation(app_client):
    """[P0] Webhook processes cancellation and sets subscription_status to cancelled."""
    from src.db.session import engine
    from sqlmodel import Session
    from src.db.models import Family
    
    with Session(engine) as session:
        family = Family(name="Test Cancel", plan_type="family_pro", subscription_status="active", max_members=5)
        session.add(family)
        session.commit()
        session.refresh(family)
        fam_id = str(family.id)
        
    payload = {"family_id": fam_id}
    response = app_client.post(
        "/api/v1/telegram/webhook/cancellation",
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert response.status_code == 200
    
    with Session(engine) as session:
        family = session.get(Family, family.id)
        assert family.subscription_status == "cancelled"

def test_webhook_lifecycle_failure(app_client, mock_telegram, telegram_payload_factory):
    """[P0] Webhook processes failure, transitions to free, and notifies admin."""
    from src.db.session import engine
    from sqlmodel import Session
    from src.db.models import Family, User
    
    admin_id = 9501
    app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/start", user_id=admin_id),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    mock_telegram.messages.clear()
    
    with Session(engine) as session:
        from sqlmodel import select
        user = session.exec(select(User).where(User.telegram_id == admin_id)).first()
        family = session.get(Family, user.family_id)
        family.plan_type = "solo_pro"
        family.subscription_status = "active"
        session.add(family)
        session.commit()
        fam_id = str(family.id)

    payload = {"family_id": fam_id}
    response = app_client.post(
        "/api/v1/telegram/webhook/failure",
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert response.status_code == 200
    
    with Session(engine) as session:
        family = session.get(Family, family.id)
        assert family.plan_type == "free"
        assert family.subscription_status == "expired"
        
    assert len(mock_telegram.messages) == 1
    failure_msg = mock_telegram.messages[0]["text"]
    assert "Subscription Expired/Failed" in failure_msg
    assert "Free tier" in failure_msg

def test_webhook_rejects_unsupported_media(app_client, mock_telegram, telegram_payload_factory):
    """[P0] Webhook rejects unsupported media (photo, doc, audio, video) before any AI processing."""
    app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/start", user_id=9801),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    mock_telegram.messages.clear()

    # Send a document attachment
    doc_payload = telegram_payload_factory(user_id=9801)
    doc_payload["message"]["document"] = {"file_id": "doc_123", "file_name": "receipt.pdf"}

    response = app_client.post(
        "/api/v1/telegram/webhook",
        json=doc_payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert len(mock_telegram.messages) == 1
    assert "Unsupported Format" in mock_telegram.messages[0]["text"]

    mock_telegram.messages.clear()

    # Send a photo attachment
    photo_payload = telegram_payload_factory(user_id=9801)
    photo_payload["message"]["photo"] = [{"file_id": "photo_123"}]

    response = app_client.post(
        "/api/v1/telegram/webhook",
        json=photo_payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert response.status_code == 200
    assert len(mock_telegram.messages) == 1
    assert "Unsupported Format" in mock_telegram.messages[0]["text"]

def test_webhook_rejects_excessive_text_length(app_client, mock_telegram, telegram_payload_factory):
    """[P0] Webhook fast-fails when text length exceeds MAX_TEXT_LENGTH before Ollama inference."""
    app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/start", user_id=9802),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    mock_telegram.messages.clear()

    long_text = "Spent 50 dollars on groceries " * 20  # 600 characters > 350 limit
    payload = telegram_payload_factory(text=long_text, user_id=9802)

    response = app_client.post(
        "/api/v1/telegram/webhook",
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert response.status_code == 200
    assert len(mock_telegram.messages) == 1
    alert_msg = mock_telegram.messages[0]["text"]
    assert "Message Too Long" in alert_msg
    assert "350 characters" in alert_msg

def test_webhook_rejects_excessive_voice_duration(app_client, mock_telegram, telegram_payload_factory):
    """[P0] Webhook fast-fails when voice duration exceeds MAX_VOICE_DURATION_SECONDS before Whisper download."""
    app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/start", user_id=9803),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    mock_telegram.messages.clear()

    voice_payload = telegram_payload_factory(user_id=9803)
    voice_payload["message"]["voice"] = {
        "file_id": "long_voice_file_id",
        "duration": 120,  # 120s > 60s limit
        "mime_type": "audio/ogg"
    }

    response = app_client.post(
        "/api/v1/telegram/webhook",
        json=voice_payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert response.status_code == 200
    assert len(mock_telegram.messages) == 1
    alert_msg = mock_telegram.messages[0]["text"]
    assert "Voice Note Too Long" in alert_msg
    assert "60 seconds" in alert_msg





