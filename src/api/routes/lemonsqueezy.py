import json
import logging
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks, Depends
from sqlmodel import Session

from src.db.session import get_session
from src.services.billing.lemonsqueezy_billing import LemonSqueezyBillingService

router = APIRouter(prefix="/api/webhooks", tags=["lemonsqueezy"])
logger = logging.getLogger(__name__)

billing_service = LemonSqueezyBillingService()


@router.post("/lemonsqueezy")
async def lemonsqueezy_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session)
):
    """
    Receives and processes incoming webhooks from Lemon Squeezy (Merchant of Record).
    Verifies HMAC-SHA256 signature in X-Signature header before dispatching.
    """
    # Enforce strict maximum body size to protect against memory exhaustion DoS attacks (max 256 KB)
    content_length = request.headers.get("Content-Length")
    if content_length:
        try:
            if int(content_length) > 262144:
                logger.warning(f"Rejected oversized Lemon Squeezy webhook payload: {content_length} bytes")
                raise HTTPException(status_code=413, detail="Payload too large")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid Content-Length")

    raw_body = await request.body()
    if len(raw_body) > 262144:
        raise HTTPException(status_code=413, detail="Payload too large")

    signature = request.headers.get("X-Signature", "")

    if not billing_service.verify_webhook_signature(raw_body, signature):
        logger.warning("Rejected Lemon Squeezy webhook with invalid signature")
        raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception as e:
        logger.error(f"Failed to parse Lemon Squeezy JSON payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event_name = payload.get("meta", {}).get("event_name", "unknown")
    logger.info(f"Received Lemon Squeezy webhook event: {event_name}")

    result = billing_service.handle_webhook_event(
        session=session,
        event_name=event_name,
        payload=payload,
        background_tasks=background_tasks
    )

    return {"status": "ok", "result": result}
