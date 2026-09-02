import pytest
from unittest.mock import patch, MagicMock
from src.core.config import settings
from src.core.subscription_config import FREE_TIER_MONTHLY_LIMIT
from src.db.models import Family
from src.services.subscription_service import can_log_transaction

@pytest.mark.anyio
async def test_lifespan_saas_mode_fails_fast_without_ai_api_key(monkeypatch):
    """Verify that when ENABLE_SUBSCRIPTIONS=True and AI_API_KEY is unset in production, startup aborts immediately."""
    from src.main import lifespan
    mock_app = MagicMock()

    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    with patch.object(settings, "ENABLE_SUBSCRIPTIONS", True), \
         patch.object(settings, "AI_API_KEY", None), \
         patch.object(settings, "DATABASE_URL", "postgresql+psycopg://user:pass@host/db"):
        with pytest.raises(RuntimeError, match="Missing AI_API_KEY for Groq Cloud deployment"):
            async with lifespan(mock_app):
                pass

def test_database_session_engine_configuration():
    """Verify that src.db.session.engine has pool_pre_ping enabled."""
    from src.db.session import engine
    # pool_pre_ping must be enabled on the engine
    assert engine.pool._pre_ping is True

def test_free_tier_quota_limit_is_twenty():
    """Verify that FREE_TIER_MONTHLY_LIMIT is strictly 20 and can_log_transaction defaults to 20."""
    from datetime import datetime, timezone
    current_month = datetime.now(timezone.utc).strftime("%Y-%m")
    assert FREE_TIER_MONTHLY_LIMIT == 20
    
    # 19 logs: permitted
    fam_19 = Family(plan_type="free", monthly_tx_count=19, last_reset_month=current_month)
    assert can_log_transaction(fam_19) is True
    
    # 20 logs: capped
    fam_20 = Family(plan_type="free", monthly_tx_count=20, last_reset_month=current_month)
    assert can_log_transaction(fam_20) is False
