"""
Paddle Billing Webhook Route.
Receives and processes notifications from Paddle Billing with cryptographic verification,
replay protection, and idempotency guarantees.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional, Any, Dict
from uuid import UUID
from fastapi import APIRouter, Request, Response, status, Depends
from fastapi.responses import JSONResponse
from sqlmodel import Session, select

from src.core.config import settings
from src.core.subscription_config import get_tier_config, SUBSCRIPTION_TIERS
from src.db.session import get_session
from src.db.models import Family, ProcessedWebhook
from src.services.billing.paddle_service import PaddleService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["paddle"])


def _parse_iso_datetime(dt_str: Optional[str]) -> Optional[datetime]:
    """Safely parses ISO-8601 timestamps from Paddle payloads."""
    if not dt_str:
        return None
    try:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except Exception:
        return None


def _find_family(session: Session, data: Dict[str, Any], custom_data: Dict[str, Any]) -> Optional[Family]:
    """
    Locates the target Family using:
    1. custom_data.family_id (direct, deterministic binding)
    2. paddle_subscription_id
    3. paddle_customer_id
    """
    family_id_str = custom_data.get("family_id")
    if family_id_str:
        try:
            family_uuid = UUID(family_id_str)
            family = session.get(Family, family_uuid)
            if family:
                return family
        except (ValueError, TypeError):
            pass

    sub_id = data.get("id") if data.get("id", "").startswith("sub_") else data.get("subscription_id")
    if sub_id:
        family = session.exec(select(Family).where(Family.paddle_subscription_id == sub_id)).first()
        if family:
            return family

    customer_id = data.get("customer_id")
    if customer_id:
        family = session.exec(select(Family).where(Family.paddle_customer_id == customer_id)).first()
        if family:
            return family

    return None


def _resolve_plan_type_and_members(plan_code: Optional[str], price_id: Optional[str]) -> tuple[Optional[str], Optional[int]]:
    """Resolves target plan_type and max_members from plan_code or price_id."""
    if plan_code:
        tier = get_tier_config(plan_code)
        if tier:
            return tier.internal_plan, tier.max_members

    if price_id:
        for code, tier in SUBSCRIPTION_TIERS.items():
            from src.core.subscription_config import get_paddle_price_id_for_tier
            if get_paddle_price_id_for_tier(code) == price_id:
                return tier.internal_plan, tier.max_members

    return None, None


@router.post("/paddle/webhook", status_code=status.HTTP_200_OK)
async def paddle_webhook(
    request: Request,
    session: Session = Depends(get_session)
):
    """
    Receives and processes Paddle webhook notifications.
    Contract:
    - Fast acknowledgment (returns 200 within 5 seconds for valid events).
    - Cryptographic HMAC-SHA256 signature verification.
    - Timestamp drift tolerance verification (5s) for replay attack defense.
    - Idempotent execution via processed_webhook ledger.
    """
    # 1. Check if subscriptions are enabled
    if not settings.ENABLE_SUBSCRIPTIONS:
        logger.warning("Paddle webhook received but ENABLE_SUBSCRIPTIONS is false.")
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": "Subscriptions are disabled on this instance"}
        )

    # 2. Extract raw body bytes and Paddle-Signature header
    raw_body_bytes = await request.body()
    raw_body = raw_body_bytes.decode("utf-8")
    signature_header = request.headers.get("Paddle-Signature", "")

    if not signature_header or not raw_body:
        logger.warning("Paddle webhook rejected: missing signature header or empty payload")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": "Missing signature or body"}
        )

    # 3. Cryptographic signature and timestamp verification
    paddle_service = PaddleService()
    is_valid = paddle_service.verify_webhook_signature(raw_body, signature_header)
    if not is_valid:
        logger.warning("Paddle webhook rejected: invalid signature or expired timestamp")
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Invalid signature or expired timestamp"}
        )

    # 4. Parse payload
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        logger.error("Paddle webhook payload is not valid JSON")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": "Invalid JSON"}
        )

    event_id = payload.get("event_id")
    event_type = payload.get("event_type")
    data = payload.get("data", {})

    if not event_id or not event_type:
        logger.warning("Paddle webhook payload missing event_id or event_type")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": "Missing event_id or event_type"}
        )

    # 5. Idempotency check
    existing_event = session.get(ProcessedWebhook, event_id)
    if existing_event:
        logger.info(f"Paddle webhook {event_id} ({event_type}) was already processed. Acknowledging with 200.")
        return {"received": True, "duplicate": True}

    custom_data = data.get("custom_data") or {}

    # 6. Event Dispatching
    logger.info(f"Processing Paddle webhook: event_id={event_id}, event_type={event_type}")

    try:
        family = _find_family(session, data, custom_data)

        if event_type in ("subscription.created", "subscription.updated"):
            sub_id = data.get("id")
            customer_id = data.get("customer_id")
            sub_status = data.get("status", "active")

            items = data.get("items", [])
            price_id = items[0].get("price", {}).get("id") if items else None

            plan_code = custom_data.get("plan_code")
            target_plan, target_members = _resolve_plan_type_and_members(plan_code, price_id)

            period_end = None
            billing_period = data.get("current_billing_period")
            if billing_period:
                period_end = _parse_iso_datetime(billing_period.get("ends_at"))

            scheduled_change = data.get("scheduled_change")
            sched_action = None
            sched_effective_at = None
            if scheduled_change:
                sched_action = scheduled_change.get("action")
                sched_effective_at = _parse_iso_datetime(scheduled_change.get("effective_at"))

            if family:
                family.paddle_subscription_id = sub_id
                if customer_id:
                    family.paddle_customer_id = customer_id
                if price_id:
                    family.paddle_price_id = price_id
                if target_plan:
                    family.plan_type = target_plan
                if target_members:
                    family.max_members = target_members

                family.subscription_status = sub_status
                if period_end:
                    family.current_period_end = period_end

                family.scheduled_change_action = sched_action
                family.scheduled_change_effective_at = sched_effective_at

                session.add(family)
                logger.info(
                    f"Updated Family {family.id}: plan_type={family.plan_type}, "
                    f"status={family.subscription_status}, period_end={family.current_period_end}"
                )
            else:
                logger.warning(
                    f"No matching Family found for Paddle event {event_id} ({event_type}), "
                    f"sub_id={sub_id}, customer_id={customer_id}"
                )

        elif event_type == "subscription.canceled":
            sub_id = data.get("id")
            if family:
                family.subscription_status = "canceled"
                family.scheduled_change_action = None
                family.scheduled_change_effective_at = None

                # Check if current_period_end has already passed
                now_utc = datetime.now(timezone.utc)
                if family.current_period_end and family.current_period_end <= now_utc:
                    family.plan_type = "free"
                    family.max_members = 5

                session.add(family)
                logger.info(f"Subscription canceled for Family {family.id}. Status set to 'canceled'.")
            else:
                logger.warning(f"Family not found for subscription.canceled sub_id={sub_id}")

        elif event_type == "transaction.completed":
            tx_id = data.get("id")
            customer_id = data.get("customer_id")
            if family:
                if customer_id and not family.paddle_customer_id:
                    family.paddle_customer_id = customer_id
                family.telegram_payment_charge_id = tx_id
                session.add(family)
                logger.info(f"Linked transaction {tx_id} to Family {family.id}")

        # 7. Record processed webhook in idempotency ledger
        processed_record = ProcessedWebhook(
            event_id=event_id,
            event_type=event_type,
            received_at=datetime.now(timezone.utc)
        )
        session.add(processed_record)
        session.commit()

        return {"received": True}

    except Exception as e:
        session.rollback()
        logger.error(f"Error handling Paddle webhook event {event_id}: {e}", exc_info=True)
        # Returning 500 tells Paddle to retry on internal application errors
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal processing error"}
        )
