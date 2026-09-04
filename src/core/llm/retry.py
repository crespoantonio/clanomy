import asyncio
import logging
import random
import re
from typing import Optional
import httpx
from tenacity import RetryCallState
from tenacity.wait import wait_base

from src.core.llm.base import PayloadTruncatedError

logger = logging.getLogger(__name__)


def is_retryable_provider_error(exception: BaseException) -> bool:
    """
    Only retries transient network errors, rate limits (429), and server errors (5xx).
    Never retries client errors (400, 401, 403, 404, 422) or deterministic truncation.
    """
    if isinstance(exception, PayloadTruncatedError):
        return False
    if isinstance(exception, (httpx.RequestError, asyncio.TimeoutError, ConnectionError, OSError)):
        return True
    if isinstance(exception, httpx.HTTPStatusError):
        status = exception.response.status_code
        return status == 429 or status >= 500
    return False


class ProviderRateLimitWait(wait_base):
    """
    Dynamic wait strategy that inspects Retry-After, rate-limit reset headers,
    or Google Gemini retryDelay when facing HTTP 429, adding jitter and falling
    back to exponential backoff.
    """
    def __init__(self, min_wait: float = 0.5, max_wait: float = 30.0):
        self.min_wait = min_wait
        self.max_wait = max_wait

    def __call__(self, retry_state: RetryCallState) -> float:
        exc = retry_state.outcome.exception() if retry_state.outcome else None
        if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429:
            resp = exc.response
            # 1. Standard RFC Retry-After header
            retry_after = resp.headers.get("Retry-After")
            if retry_after:
                try:
                    delay = float(retry_after) + random.uniform(0.1, 0.5)
                    logger.warning(f"[RateLimit 429] Respecting Retry-After header: sleeping {delay:.2f}s")
                    return min(max(delay, self.min_wait), self.max_wait)
                except ValueError:
                    pass

            # 2. Provider specific reset headers (e.g. Groq x-ratelimit-reset-tokens or x-ratelimit-reset-requests)
            reset_header = resp.headers.get("x-ratelimit-reset-tokens") or resp.headers.get("x-ratelimit-reset-requests")
            if reset_header:
                match = re.search(r"(\d+(?:\.\d+)?)\s*(s|ms)?", reset_header)
                if match:
                    val = float(match.group(1))
                    unit = match.group(2)
                    delay = (val / 1000.0 if unit == "ms" else val) + random.uniform(0.1, 0.5)
                    logger.warning(f"[RateLimit 429] Respecting {reset_header} header: sleeping {delay:.2f}s")
                    return min(max(delay, self.min_wait), self.max_wait)

            # 3. Google Gemini API error details (retryDelay in error body or error details)
            try:
                err_json = resp.json()
                details = err_json.get("error", {}).get("details", [])
                for detail in details:
                    retry_delay = detail.get("retryDelay")
                    if retry_delay:
                        clean_delay = str(retry_delay).rstrip("s")
                        delay = float(clean_delay) + random.uniform(0.1, 0.5)
                        logger.warning(f"[RateLimit 429] Respecting Gemini retryDelay ({retry_delay}): sleeping {delay:.2f}s")
                        return min(max(delay, self.min_wait), self.max_wait)
            except Exception:
                pass

        # 4. Fallback: Full Jitter Exponential Backoff
        attempt = retry_state.attempt_number
        base_delay = min(self.max_wait, self.min_wait * (2 ** (attempt - 1)))
        return base_delay * random.uniform(0.5, 1.0)
