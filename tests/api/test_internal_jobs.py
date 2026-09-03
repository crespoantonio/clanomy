import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlalchemy.pool import StaticPool

from src.main import app
from src.core.config import settings
from src.db.models import Family, User, Transaction
from src.db.session import get_session

@pytest.fixture
def internal_test_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session

@pytest.fixture
def client(internal_test_session):
    def override_get_session():
        yield internal_test_session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

def test_trial_lifecycle_rejects_missing_secret(client, monkeypatch):
    monkeypatch.setattr(settings, "CRON_SECRET", "super_secret_cron_token_123")
    response = client.post("/api/internal/jobs/trial-lifecycle")
    assert response.status_code == 401
    assert "Unauthorized" in response.json()["detail"]

def test_trial_lifecycle_rejects_invalid_secret(client, monkeypatch):
    monkeypatch.setattr(settings, "CRON_SECRET", "super_secret_cron_token_123")
    response = client.post(
        "/api/internal/jobs/trial-lifecycle",
        headers={"X-Job-Secret": "completely_wrong_secret"}
    )
    assert response.status_code == 401
    assert "Unauthorized" in response.json()["detail"]

def test_trial_lifecycle_accepts_valid_header_and_authorization_bearer(client, monkeypatch, internal_test_session):
    secret = "my_gcp_cron_secret_abc"
    monkeypatch.setattr(settings, "CRON_SECRET", secret)
    monkeypatch.setattr(settings, "ENABLE_SUBSCRIPTIONS", True)

    # 1. Test via X-Job-Secret
    resp1 = client.post(
        "/api/internal/jobs/trial-lifecycle",
        headers={"X-Job-Secret": secret}
    )
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["status"] == "success"
    assert data1["job"] == "trial-lifecycle"
    assert "timestamp" in data1

    # 2. Test via Authorization: Bearer <secret>
    resp2 = client.post(
        "/api/internal/jobs/trial-lifecycle",
        headers={"Authorization": f"Bearer {secret}"}
    )
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "success"

def test_trial_lifecycle_executes_transitions_and_guarantees_idempotency(client, monkeypatch, internal_test_session):
    secret = "lifecycle_test_secret_999"
    monkeypatch.setattr(settings, "CRON_SECRET", secret)
    monkeypatch.setattr(settings, "ENABLE_SUBSCRIPTIONS", True)

    now = datetime.now(timezone.utc)

    # Setup Day 60 candidate family
    fam = Family(
        name="Expired Household",
        plan_type="trial",
        trial_ends_at=now - timedelta(hours=1),
        notified_day_50=True,
        notified_day_60=False
    )
    internal_test_session.add(fam)
    internal_test_session.flush()

    user = User(telegram_id=88888, family_id=fam.id, is_admin=True)
    internal_test_session.add(user)
    internal_test_session.commit()

    # First execution: transitions family to free
    resp1 = client.post(
        "/api/internal/jobs/trial-lifecycle",
        headers={"X-Job-Secret": secret}
    )
    assert resp1.status_code == 200
    res1_data = resp1.json()
    assert res1_data["day_60_processed"] == 1

    # Verify DB state
    internal_test_session.refresh(fam)
    assert fam.plan_type == "free"
    assert fam.max_members == 5
    assert fam.subscription_status == "expired"
    assert fam.notified_day_60 is True

    # Second execution on same day: idempotency prevents duplicate processing
    resp2 = client.post(
        "/api/internal/jobs/trial-lifecycle",
        headers={"X-Job-Secret": secret}
    )
    assert resp2.status_code == 200
    assert resp2.json()["day_60_processed"] == 0
