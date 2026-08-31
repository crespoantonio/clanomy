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

