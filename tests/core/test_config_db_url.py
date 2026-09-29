import pytest
from src.core.config import Settings

def test_database_url_normalization_postgres_prefix(monkeypatch):
    """Render provides postgres:// which must normalize to postgresql+psycopg://."""
    monkeypatch.setenv("ENCRYPTION_KEY", "MDEyMzQ1Njc4OTAxMjM0NTY3ODkwMTIzNDU2Nzg5MDE=")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake_bot_token")
    monkeypatch.setenv("MESSAGING_WEBHOOK_SECRET", "fake_secret")
    monkeypatch.setenv("DATABASE_URL", "postgres://user:password@ep-test.render.com:5432/clanomy_db")

    settings = Settings()
    assert settings.DATABASE_URL == "postgresql+psycopg://user:password@ep-test.render.com:5432/clanomy_db"

def test_database_url_normalization_postgresql_default_prefix(monkeypatch):
    """Standard postgresql:// without driver must normalize to postgresql+psycopg://."""
    monkeypatch.setenv("ENCRYPTION_KEY", "MDEyMzQ1Njc4OTAxMjM0NTY3ODkwMTIzNDU2Nzg5MDE=")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake_bot_token")
    monkeypatch.setenv("MESSAGING_WEBHOOK_SECRET", "fake_secret")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:password@localhost:5432/clanomy_db")

    settings = Settings()
    assert settings.DATABASE_URL == "postgresql+psycopg://user:password@localhost:5432/clanomy_db"

def test_database_url_normalization_already_has_psycopg(monkeypatch):
    """postgresql+psycopg:// should remain unchanged."""
    monkeypatch.setenv("ENCRYPTION_KEY", "MDEyMzQ1Njc4OTAxMjM0NTY3ODkwMTIzNDU2Nzg5MDE=")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake_bot_token")
    monkeypatch.setenv("MESSAGING_WEBHOOK_SECRET", "fake_secret")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:password@localhost:5432/clanomy_db")

    settings = Settings()
    assert settings.DATABASE_URL == "postgresql+psycopg://user:password@localhost:5432/clanomy_db"

def test_database_url_normalization_sqlite_unchanged(monkeypatch):
    """sqlite:// should remain unchanged."""
    monkeypatch.setenv("ENCRYPTION_KEY", "MDEyMzQ1Njc4OTAxMjM0NTY3ODkwMTIzNDU2Nzg5MDE=")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake_bot_token")
    monkeypatch.setenv("MESSAGING_WEBHOOK_SECRET", "fake_secret")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")

    settings = Settings()
    assert settings.DATABASE_URL == "sqlite:///:memory:"

def test_database_url_normalization_with_sslmode_params(monkeypatch):
    """Ensure query parameters such as sslmode=require are preserved."""
    monkeypatch.setenv("ENCRYPTION_KEY", "MDEyMzQ1Njc4OTAxMjM0NTY3ODkwMTIzNDU2Nzg5MDE=")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake_bot_token")
    monkeypatch.setenv("MESSAGING_WEBHOOK_SECRET", "fake_secret")
    monkeypatch.setenv("DATABASE_URL", "postgres://user:password@ep-test.render.com:5432/clanomy_db?sslmode=require")

    settings = Settings()
    assert settings.DATABASE_URL == "postgresql+psycopg://user:password@ep-test.render.com:5432/clanomy_db?sslmode=require"
