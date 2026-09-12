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
from src.db.models import Family, User, ProcessedWebhook
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


def _resolve_tier_display_name(plan_type: Optional[str], plan_code: Optional[str] = None) -> str:
    if plan_code:
        tier = get_tier_config(plan_code)
        if tier:
            return tier.title
    plan_map = {
        "solo_pro": "Solo Pro",
        "duo_pro": "Duo Pro",
        "family_pro": "Family Pro",
        "free": "Free"
    }
    return plan_map.get(plan_type or "", "Clanomy Pro")


async def _safe_send_telegram(chat_id: int, text: str) -> None:
    try:
        from src.services.telegram_service import TelegramService
        tg = TelegramService()
        await tg.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Failed to deliver Paddle Telegram notification to {chat_id}: {e}")


async def _broadcast_cancellation_to_family(
    session: Session,
    family: Family,
    tier_name: str,
    effective_end: Optional[datetime]
) -> None:
    from src.templates.telegram_messages import format_subscription_canceled_message, is_family_spanish
    is_sp = is_family_spanish(family, session)
    text = format_subscription_canceled_message(
        tier_name=tier_name,
        effective_end=effective_end,
        is_spanish=is_sp
    )
    users = session.exec(select(User).where(User.family_id == family.id)).all()
    for u in users:
        if u.telegram_id:
            await _safe_send_telegram(u.telegram_id, text)


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
        prev_plan = family.plan_type if family else None
        prev_status = family.subscription_status if family else None
        prev_sched_action = family.scheduled_change_action if family else None

        # Check for non-admin member graduation
        user_id_str = custom_data.get("user_id")
        paying_user = None
        if user_id_str:
            try:
                user_uuid = UUID(user_id_str)
                paying_user = session.get(User, user_uuid)
                if paying_user and family and paying_user.family_id == family.id and not paying_user.is_admin:
                    from src.services.family_service import FamilyService
                    fam_service = FamilyService()
                    plan_code_candidate = custom_data.get("plan_code")
                    graduated_family = fam_service.graduate_member_to_new_workspace(paying_user.id, target_plan=cand_plan or "solo_pro")
                    # Re-fetch managed instances within the active request session
                    family = session.get(Family, graduated_family.id) or graduated_family
                    paying_user = session.get(User, paying_user.id) or paying_user
                    logger.info(f"Graduated user {paying_user.id} into new workspace {family.id} on webhook")
            except Exception as grad_err:
                logger.error(f"Error checking member graduation on webhook: {grad_err}")

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
                session.flush()
                logger.info(
                    f"Updated Family {family.id}: plan_type={family.plan_type}, "
                    f"status={family.subscription_status}, period_end={family.current_period_end}"
                )

                tier_display = _resolve_tier_display_name(family.plan_type, plan_code)

                # 1. Activation Notification: ONLY to paying user/admin upon new activation / tier upgrade
                is_activation = (event_type == "subscription.created") or (prev_plan in ("free", None) and family.plan_type not in ("free", None)) or (prev_plan != family.plan_type and family.plan_type not in ("free", None))
                if is_activation and sub_status == "active":
                    if not paying_user:
                        paying_user = session.exec(select(User).where(User.family_id == family.id, User.is_admin == True)).first()
                        if not paying_user:
                            paying_user = session.exec(select(User).where(User.family_id == family.id)).first()

                    if paying_user and paying_user.telegram_id:
                        from src.templates.telegram_messages import format_subscription_activated_message, is_family_spanish
                        interval = "year" if ("annual" in (plan_code or "").lower() or "yearly" in (plan_code or "").lower()) else "month"
                        is_sp = is_family_spanish(family, session)
                        act_msg = format_subscription_activated_message(
                            tier_name=tier_display,
                            interval=interval,
                            period_end=family.current_period_end,
                            is_spanish=is_sp
                        )
                        await _safe_send_telegram(paying_user.telegram_id, act_msg)

                # 2. Scheduled Cancellation Notification: Broadcast to ALL family members
                if sched_action == "cancel" and prev_sched_action != "cancel":
                    effective_end = sched_effective_at or family.current_period_end
                    await _broadcast_cancellation_to_family(session, family, tier_display, effective_end)

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
                period_end_cmp = family.current_period_end
                if period_end_cmp and period_end_cmp.tzinfo is None:
                    period_end_cmp = period_end_cmp.replace(tzinfo=timezone.utc)
                if period_end_cmp and period_end_cmp <= now_utc:
                    family.plan_type = "free"
                    family.max_members = 5

                session.add(family)
                session.flush()
                logger.info(f"Subscription canceled for Family {family.id}. Status set to 'canceled'.")

                # If not previously notified via scheduled_change, broadcast cancellation to all family members
                if prev_status != "canceled" and prev_sched_action != "cancel":
                    tier_display = _resolve_tier_display_name(prev_plan, None)
                    await _broadcast_cancellation_to_family(session, family, tier_display, family.current_period_end)
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
