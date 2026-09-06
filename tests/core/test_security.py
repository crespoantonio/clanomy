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
        
        # Direct access without header is blocked with 403 on non-exempt paths
        blocked_resp = client.get("/")
        assert blocked_resp.status_code == 403
        assert blocked_resp.json() == {"detail": "Direct origin access forbidden"}

        # Access with valid origin header succeeds
        allowed_resp = client.get("/", headers={"X-Origin-Verify-Secret": "shield-key-abc"})
        assert allowed_resp.status_code == 200

        # Alternate origin key header succeeds
        allowed_resp_alt = client.get("/", headers={"X-Clanomy-Origin-Key": "shield-key-abc"})
        assert allowed_resp_alt.status_code == 200

        # All configured exempt paths bypass origin shield verification (do NOT return 403)
        for exempt_path in settings.CLOUDFLARE_ORIGIN_EXEMPT_PATHS:
            resp = client.get(exempt_path)
            assert resp.status_code != 403, f"Path {exempt_path} should be exempt from origin shield"

        # Verify helper method
        for exempt_path in settings.CLOUDFLARE_ORIGIN_EXEMPT_PATHS:
            assert settings.is_origin_shield_exempt(exempt_path) is True
            assert settings.is_origin_shield_exempt(f"{exempt_path}/") is True
        assert settings.is_origin_shield_exempt("/") is False
        assert settings.is_origin_shield_exempt("/api/v1/other") is False
    finally:
        settings.CLOUDFLARE_ORIGIN_SECRET = original_origin

def test_request_size_limit_middleware():
    client = TestClient(app)
    original_limit = getattr(settings, "MAX_REQUEST_SIZE_BYTES", None)
    try:
        settings.MAX_REQUEST_SIZE_BYTES = 1000  # 1000 bytes limit for test

        # 1. Payload within limit succeeds (not 413)
        small_body = b"x" * 500
        resp = client.post(
            "/api/v1/simulate/message",
            content=small_body,
            headers={"Content-Length": str(len(small_body)), "Content-Type": "application/json"}
        )
        assert resp.status_code != 413

        # 2. Content-Length header exceeding limit is rejected with 413 immediately
        resp_413 = client.post(
            "/api/v1/simulate/message",
            content=b"x" * 2000,
            headers={"Content-Length": "2000", "Content-Type": "application/json"}
        )
        assert resp_413.status_code == 413
        assert resp_413.json() == {"detail": "Payload too large"}

        # 3. Invalid Content-Length header returns 400
        resp_400 = client.post(
            "/api/v1/simulate/message",
            content=b"test",
            headers={"Content-Length": "invalid_number", "Content-Type": "application/json"}
        )
        assert resp_400.status_code == 400
        assert resp_400.json() == {"detail": "Invalid Content-Length header"}

        # 4. Chunked/streamed body exceeding limit without Content-Length header returns 413
        large_body = b"y" * 1500
        resp_chunked_413 = client.post(
            "/api/v1/simulate/message",
            content=large_body,
            headers={"Content-Type": "application/json"}  # No Content-Length
        )
        assert resp_chunked_413.status_code == 413
        assert resp_chunked_413.json() == {"detail": "Payload too large"}
    finally:
        settings.MAX_REQUEST_SIZE_BYTES = original_limit

def test_mask_database_url():
    from src.core.security import mask_database_url
    
    # 1. Standard URL
    raw_url = "postgresql+psycopg://postgres:supersecretpassword@db.supabase.co:5432/postgres"
    masked = mask_database_url(raw_url)
    assert "supersecretpassword" not in masked
    assert "postgres:***@" in masked
    assert "db.supabase.co:5432/postgres" in masked
    
    # 2. URL with percent-encoded special characters
    raw_encoded = "postgresql+psycopg://postgres.ref:9%40ka%21FfAA%2A%24@aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require"
    masked_encoded = mask_database_url(raw_encoded)
    assert "9%40ka" not in masked_encoded
    assert ":***@" in masked_encoded
    assert "aws-0-us-east-1.pooler.supabase.com" in masked_encoded

    # 3. None or empty
    assert mask_database_url(None) == ""
    assert mask_database_url("") == ""

def test_sanitize_exception_message():
    from src.core.security import sanitize_exception_message
    
    raw_url = "postgresql+psycopg://postgres:secret123@db.supabase.co:5432/postgres"
    error_msg = f"Connection failed to '{raw_url}' with error timeout"
    
    sanitized = sanitize_exception_message(error_msg, raw_url=raw_url)
    assert "secret123" not in sanitized
    assert "postgres:***@db.supabase.co:5432/postgres" in sanitized




