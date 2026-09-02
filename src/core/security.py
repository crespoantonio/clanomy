import secrets
from src.core.config import settings
from typing import Optional

def verify_messaging_secret(received_secret: Optional[str]) -> bool:
    """
    Verifies that the received secret token matches the one configured for the webhook.
    Uses constant-time comparison to prevent timing attacks.
    """
    if not received_secret or not settings.MESSAGING_WEBHOOK_SECRET:
        return False
        
    return secrets.compare_digest(received_secret, settings.MESSAGING_WEBHOOK_SECRET)

def verify_origin_secret(received_secret: Optional[str]) -> bool:
    """
    Verifies that the request carries the configured Cloudflare Origin Shield Secret.
    If CLOUDFLARE_ORIGIN_SECRET is not configured (None or empty), origin check is skipped (returns True).
    Uses constant-time comparison to prevent timing attacks.
    """
    if not settings.CLOUDFLARE_ORIGIN_SECRET or not settings.CLOUDFLARE_ORIGIN_SECRET.strip():
        return True
    if not received_secret:
        return False
    return secrets.compare_digest(received_secret, settings.CLOUDFLARE_ORIGIN_SECRET.strip())

def mask_database_url(url: Optional[str]) -> str:
    """
    Masks the password in a database URL string to protect credentials from appearing in logs or error traces.
    e.g. postgresql+psycopg://user:password@host:5432/db -> postgresql+psycopg://user:***@host:5432/db
    """
    if not url:
        return ""
    try:
        from sqlalchemy.engine import make_url
        return make_url(url).render_as_string(hide_password=True)
    except Exception:
        import re
        return re.sub(r":([^@/:\s]+)@", r":***@", url)

def sanitize_auth_tokens(error_or_text: object) -> str:
    """
    Redacts Bearer tokens, gsk_* Groq keys, OpenAI keys, and Telegram bot tokens from text/error strings.
    """
    import re
    text = str(error_or_text)
    # Redact Bearer tokens
    text = re.sub(r"Bearer\s+[A-Za-z0-9_\-\.]+", "Bearer [REDACTED]", text, flags=re.IGNORECASE)
    # Redact Groq keys (gsk_...)
    text = re.sub(r"gsk_[A-Za-z0-9]{20,}", "gsk_[REDACTED]", text)
    # Redact OpenAI keys (sk-...)
    text = re.sub(r"sk-[A-Za-z0-9]{20,}", "sk-[REDACTED]", text)
    # Redact Telegram Bot tokens: \d{8,10}:[A-Za-z0-9_-]{30,40}
    text = re.sub(r"\b\d{8,10}:[A-Za-z0-9_-]{30,40}\b", "[TELEGRAM_TOKEN_REDACTED]", text)
    return text


def sanitize_exception_message(error_or_text: object, raw_url: Optional[str] = None) -> str:
    """
    Replaces raw database credentials, auth tokens, and connection strings in error messages with masked equivalents.
    """
    import re
    text = str(error_or_text)
    target_url = raw_url or (settings.DATABASE_URL if hasattr(settings, "DATABASE_URL") else None)
    if target_url:
        masked = mask_database_url(target_url)
        text = text.replace(target_url, masked)
        text = text.replace(target_url.replace("%", "%%"), masked)
    text = re.sub(r":([^@/:\s]{2,})@", r":***@", text)
    return sanitize_auth_tokens(text)

