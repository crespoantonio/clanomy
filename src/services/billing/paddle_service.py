"""
Paddle Billing API Service.
Encapsulates cryptographic webhook verification, transaction-based checkout link generation,
and customer billing portal session creation.
"""

import time
import hmac
import hashlib
import logging
from typing import Optional, Dict, Any, List
from src.core.config import settings
from src.core.http_client import get_http_client, make_timeout
from src.core.subscription_config import get_paddle_price_id_for_tier

logger = logging.getLogger(__name__)


class PaddleService:
    def __init__(
        self,
        api_key: Optional[str] = None,
        webhook_secret: Optional[str] = None,
        environment: Optional[str] = None,
    ):
        self.api_key = api_key or settings.PADDLE_API_KEY
        self.webhook_secret = webhook_secret or settings.PADDLE_WEBHOOK_SECRET_KEY
        self.environment = (environment or settings.PADDLE_ENVIRONMENT or "sandbox").lower().strip()
        self.base_url = (
            "https://sandbox-api.paddle.com"
            if self.environment == "sandbox"
            else "https://api.paddle.com"
        )

    def verify_webhook_signature(
        self,
        raw_body: str,
        signature_header: str,
        tolerance_seconds: int = 5
    ) -> bool:
        """
        Cryptographically verifies the Paddle-Signature header against the raw body.
        Paddle-Signature format: ts=<unix_timestamp>;h1=<hmac_sha256_hex>
        
        Safeguards:
        1. Checks for missing header, secret, or raw body.
        2. Enforces timestamp tolerance (default 5s) against replay attacks.
        3. Validates HMAC-SHA256 hash using constant-time comparison.
        """
        if not self.webhook_secret or not signature_header or not raw_body:
            logger.warning("Paddle signature verification failed: missing secret, header, or body")
            return False

        try:
            parts = signature_header.split(";")
            params: Dict[str, str] = {}
            for part in parts:
                if "=" in part:
                    k, v = part.split("=", 1)
                    params[k.strip()] = v.strip()

            ts_str = params.get("ts")
            h1 = params.get("h1")

            if not ts_str or not h1:
                logger.warning(f"Paddle signature verification failed: invalid header format '{signature_header}'")
                return False

            ts = int(ts_str)
            current_ts = int(time.time())

            # Replay attack protection
            if abs(current_ts - ts) > tolerance_seconds:
                logger.warning(
                    f"Paddle signature verification failed: timestamp drift {abs(current_ts - ts)}s "
                    f"exceeds tolerance of {tolerance_seconds}s"
                )
                return False

            signed_payload = f"{ts}:{raw_body}"
            expected_hash = hmac.new(
                self.webhook_secret.encode("utf-8"),
                signed_payload.encode("utf-8"),
                hashlib.sha256
            ).hexdigest()

            if not hmac.compare_digest(expected_hash, h1):
                logger.warning("Paddle signature verification failed: signature mismatch")
                return False

            return True

        except Exception as e:
            logger.error(f"Paddle signature verification exception: {e}", exc_info=True)
            return False

    async def create_checkout_url(
        self,
        family_id: str,
        user_id: str,
        plan_code: str,
        customer_email: Optional[str] = None
    ) -> Optional[str]:
        """
        Creates a transaction in Paddle Billing with custom_data binding family_id and user_id.
        Returns the checkout URL for the user to finalize subscription.
        If price ID or API key is not configured, returns None so callers can gracefully fall back.
        """
        if not self.api_key:
            logger.info("Paddle API key is not configured; skipping checkout transaction creation")
            return None

        price_id = get_paddle_price_id_for_tier(plan_code)
        if not price_id:
            logger.info(f"No Paddle price ID configured for plan code '{plan_code}'")
            return None

        payload: Dict[str, Any] = {
            "items": [
                {
                    "price_id": price_id,
                    "quantity": 1
                }
            ],
            "custom_data": {
                "family_id": str(family_id),
                "user_id": str(user_id),
                "plan_code": plan_code
            }
        }

        if customer_email:
            payload["customer_id"] = None  # let Paddle associate or create customer

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        try:
            client = get_http_client()
            response = await client.post(
                f"{self.base_url}/transactions",
                json=payload,
                headers=headers,
                timeout=make_timeout(5.0)
            )

            if response.status_code not in (200, 201):
                logger.error(f"Paddle create transaction failed [{response.status_code}]: {response.text}")
                return None

            data = response.json().get("data", {})
            checkout_info = data.get("checkout", {})
            checkout_url = checkout_info.get("url")

            if checkout_url:
                return checkout_url

            # Fallback to hosted checkout format if transaction ID is present
            transaction_id = data.get("id")
            if transaction_id:
                return f"https://pay.paddle.com/checkout/{transaction_id}"

            return None

        except Exception as e:
            logger.error(f"Exception creating Paddle checkout transaction: {e}", exc_info=True)
            return None

    async def create_customer_portal_session(
        self,
        customer_id: str,
        subscription_ids: Optional[List[str]] = None
    ) -> Optional[str]:
        """
        Creates an authenticated Customer Portal session for self-serve subscription management.
        POST /customers/{customer_id}/portal-sessions
        Returns the temporary overview URL.
        """
        if not self.api_key or not customer_id:
            logger.info("Cannot create customer portal session: missing API key or customer_id")
            return None

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        body: Dict[str, Any] = {}
        if subscription_ids:
            body["subscription_ids"] = subscription_ids

        try:
            client = get_http_client()
            response = await client.post(
                f"{self.base_url}/customers/{customer_id}/portal-sessions",
                json=body,
                headers=headers,
                timeout=make_timeout(5.0)
            )

            if response.status_code not in (200, 201):
                logger.error(f"Paddle portal session creation failed [{response.status_code}]: {response.text}")
                return None

            data = response.json().get("data", {})
            urls = data.get("urls", {})
            general = urls.get("general", {})
            overview_url = general.get("overview")

            return overview_url

        except Exception as e:
            logger.error(f"Exception creating customer portal session: {e}", exc_info=True)
            return None
