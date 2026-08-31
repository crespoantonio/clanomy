import pytest
from fastapi.testclient import TestClient
from src.core.security import verify_messaging_secret, verify_origin_secret
from src.core.config import settings
from src.main import app

def test_verify_messaging_secret_success():
    # Mock settings.MESSAGING_WEBHOOK_SECRET for the test
    original_secret = getattr(settings, "MESSAGING_WEBHOOK_SECRET", None)
    settings.MESSAGING_WEBHOOK_SECRET = "super-secret"
    
    try:
        assert verify_messaging_secret("super-secret") is True
    finally:
        if original_secret is not None:
            settings.MESSAGING_WEBHOOK_SECRET = original_secret

def test_verify_messaging_secret_failure():
    original_secret = getattr(settings, "MESSAGING_WEBHOOK_SECRET", None)
    settings.MESSAGING_WEBHOOK_SECRET = "super-secret"
    
    try:
        assert verify_messaging_secret("wrong-secret") is False
        assert verify_messaging_secret(None) is False
    finally:
        if original_secret is not None:
            settings.MESSAGING_WEBHOOK_SECRET = original_secret

def test_verify_origin_secret():
    original_origin = getattr(settings, "CLOUDFLARE_ORIGIN_SECRET", None)
    try:
        # 1. When not configured (None or empty), origin check passes
        settings.CLOUDFLARE_ORIGIN_SECRET = None
        assert verify_origin_secret(None) is True
        assert verify_origin_secret("any") is True

        settings.CLOUDFLARE_ORIGIN_SECRET = ""
        assert verify_origin_secret(None) is True

        # 2. When configured, matches exact secret constant-time
        settings.CLOUDFLARE_ORIGIN_SECRET = "cf-secret-token-123"
        assert verify_origin_secret("cf-secret-token-123") is True
        assert verify_origin_secret("wrong-token") is False
        assert verify_origin_secret(None) is False
    finally:
        settings.CLOUDFLARE_ORIGIN_SECRET = original_origin

def test_security_headers_in_response():
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("X-XSS-Protection") == "1; mode=block"
    assert "Strict-Transport-Security" in response.headers
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "server" not in response.headers

def test_origin_shield_middleware():
    client = TestClient(app)
    original_origin = getattr(settings, "CLOUDFLARE_ORIGIN_SECRET", None)
    try:
        settings.CLOUDFLARE_ORIGIN_SECRET = "shield-key-abc"
        
        # Direct access without header is blocked with 403
        blocked_resp = client.get("/")
        assert blocked_resp.status_code == 403
        assert blocked_resp.json() == {"detail": "Direct origin access forbidden"}

        # Access with valid origin header succeeds
        allowed_resp = client.get("/", headers={"X-Origin-Verify-Secret": "shield-key-abc"})
        assert allowed_resp.status_code == 200

        # Health probe bypasses origin secret check for monitoring
        health_resp = client.get("/health")
        assert health_resp.status_code in [200, 503] # Status depends on test DB state, but not 403 blocked
    finally:
        settings.CLOUDFLARE_ORIGIN_SECRET = original_origin

