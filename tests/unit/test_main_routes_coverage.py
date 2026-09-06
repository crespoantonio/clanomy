import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from src.main import app, lifespan
from src.core.config import settings

def test_root_endpoint():
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "online"
    assert data["service"] == "Clanomy API"

def test_landing_page_routes():
    client = TestClient(app)
    
    # /landing
    resp = client.get("/landing")
    assert resp.status_code in (200, 404)

    # /styles.css
    resp = client.get("/styles.css")
    assert resp.status_code in (200, 404)

    # /script.js
    resp = client.get("/script.js")
    assert resp.status_code in (200, 404)

    # /translations.js
    resp = client.get("/translations.js")
    assert resp.status_code in (200, 404)

    # /assets/nonexistent.png
    resp = client.get("/assets/nonexistent.png")
    assert resp.status_code == 404

def test_health_check_ollama_probe():
    client = TestClient(app)
    mock_client = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_client.get.return_value = mock_resp

    with patch.object(settings, "AI_API_KEY", None), \
         patch("src.core.http_client.get_http_client", return_value=mock_client):
        resp = client.get("/health")
        assert resp.status_code in (200, 503)
        data = resp.json()
        assert data.get("ollama") == "connected"

    # Ollama degraded
    mock_resp.status_code = 500
    with patch.object(settings, "AI_API_KEY", None), \
         patch("src.core.http_client.get_http_client", return_value=mock_client):
        resp = client.get("/health")
        assert resp.status_code in (200, 503)
        data = resp.json()
        assert data.get("ollama") == "degraded"

    # Ollama unreachable exception
    mock_client.get.side_effect = Exception("Ollama down")
    with patch.object(settings, "AI_API_KEY", None), \
         patch("src.core.http_client.get_http_client", return_value=mock_client):
        resp = client.get("/health")
        assert resp.status_code in (200, 503)
        data = resp.json()
        assert data.get("ollama") == "unreachable"

@pytest.mark.anyio
async def test_lifespan_startup_and_shutdown():
    with patch("src.main.run_migrations"), \
         patch("src.core.http_client.HTTPClientManager.init"), \
         patch("src.core.http_client.HTTPClientManager.close", new_callable=AsyncMock), \
         patch("asyncio.sleep", new_callable=AsyncMock), \
         patch.object(settings, "ENABLE_INTERNAL_SCHEDULER", True), \
         patch("src.services.notification_scheduler.start_notification_scheduler"), \
         patch("src.services.notification_scheduler.stop_notification_scheduler", new_callable=AsyncMock), \
         patch("src.db.session.engine.dispose"):
        
        async with lifespan(app):
            pass

@pytest.mark.anyio
async def test_lifespan_migration_failure():
    with patch("src.main.run_migrations", side_effect=Exception("DB connection error")), \
         pytest.raises(RuntimeError, match="Startup aborted: database migration failed"):
        async with lifespan(app):
            pass
