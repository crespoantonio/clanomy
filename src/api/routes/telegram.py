"""
Telegram Webhook Route Handler for Clanomy.
Provides HTTP ingress for Telegram Bot webhook updates, lifecycle callbacks, and payment webhooks.
"""

from fastapi import APIRouter, Header, HTTPException, Depends, BackgroundTasks, Request
from pydantic import BaseModel
from typing import Optional
import time
import uuid
import logging
import asyncio
from collections import OrderedDict
from sqlmodel import Session, select

from src.core.config import settings
from src.core.security import verify_messaging_secret
from src.db.session import get_session
from src.db.models import User, Family
from src.services.messaging_service import MessagingService
from src.services.ai_orchestrator import AIOrchestrator
from src.services.telegram_service import TelegramService
from src.services.family_service import FamilyService
from src.services.billing.billing_service import BillingService
from src.services.handlers.command_handler import CommandHandler
from src.services.handlers.currency_handler import (
    handle_manage_currency,
    build_currency_keyboard,
    format_currency_menu_text,
    format_currency_success_text,
    CURRENCY_PAGES
)
from src.core.subscription_config import FREE_TIER_MONTHLY_LIMIT
from src.services.subscription_service import (
    can_log_transaction,
    check_transaction_allowance,
    check_and_reset_monthly_quota,
    handle_recurring_renewal,
    handle_subscription_cancellation,
    handle_payment_failure
)
from src.templates.telegram_messages import (
    UNAUTHORIZED_ACCESS_MESSAGE,
    UNSUPPORTED_FORMAT_MESSAGE,
    DAILY_LIMIT_REACHED_MESSAGE,
    format_message_too_long,
    format_voice_too_long,
    format_voice_too_large,
    format_welcome_message
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/telegram", tags=["Telegram Webhook"])


class BoundedCooldownStore:
    def __init__(self, max_entries: int = 10000):
        self.store: OrderedDict[int, float] = OrderedDict()
        self.max_entries = max_entries

    def is_throttled(self, chat_id: int, cooldown_seconds: float) -> bool:
        if cooldown_seconds <= 0:
            return False
        now = time.time()
        last_time = self.store.get(chat_id, 0.0)
        if (now - last_time) < cooldown_seconds:
            return True
        self.store[chat_id] = now
        if len(self.store) > self.max_entries:
            self.store.popitem(last=False)
        return False


_cooldown_store = BoundedCooldownStore()
_tz_finder = None


def get_timezone_finder():
    global _tz_finder
    if _tz_finder is None:
        from timezonefinder import TimezoneFinder
        _tz_finder = TimezoneFinder()
    return _tz_finder


def _is_query_or_command(text: Optional[str]) -> bool:
    if not text:
        return False
    t = text.strip().lower()
    if t.startswith("/"):
        return True
    if "confirm delete" in t or "delete account" in t or "confirm leave" in t or "confirmar salir" in t:
        return True
    if t.startswith(("export", "notion", "invite", "create family", "leave family", "remove member", "family info", "my family", "upgrade", "tier", "tiers", "plan", "plans", "pricing")):
        return True
    if t.startswith(("how", "what", "show", "tell", "list", "summary", "breakdown", "report", "chart", "compare")):
        return True
    if "how much" in t or "spending summary" in t or "cash flow" in t or "net balance" in t:
        return True
    if "undo" in t or "change" in t or "delete last" in t or "remove last" in t:
        return True
    return False


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_telegram_bot_api_secret_token: Optional[str] = Header(None),
    session: Session = Depends(get_session)
):
    if not verify_messaging_secret(x_telegram_bot_api_secret_token):
        logger.warning("Invalid Telegram webhook secret token attempt.")
        raise HTTPException(status_code=403, detail="Invalid secret token")

    payload = await request.json()
    telegram_service = TelegramService()
    billing_service = BillingService(telegram_service)

    if "callback_query" in payload:
        cb = payload["callback_query"]
        cb_id = cb.get("id")
        cb_data = cb.get("data", "")
        from_user = cb.get("from", {})
        cb_message = cb.get("message", {})
        cb_chat = cb_message.get("chat", {})
        chat_id = cb_chat.get("id") or from_user.get("id")
        message_id = cb_message.get("message_id")
        user_id = from_user.get("id")

        if not user_id or not chat_id:
            return {"status": "ok"}

        try:
            if settings.ALLOWED_TELEGRAM_USERS and settings.ALLOWED_TELEGRAM_USERS.strip():
                allowed_list = [entry.strip().lstrip("@").lower() for entry in settings.ALLOWED_TELEGRAM_USERS.split(",") if entry.strip()]
                user_uname = (from_user.get("username") or "").lower()
                if user_uname not in allowed_list and str(user_id) not in allowed_list:
                    logger.warning(f"Unauthorized Telegram callback interaction from user: {user_uname} ({user_id})")
                    if cb_id:
                        await telegram_service.answer_callback_query(callback_query_id=cb_id, text="Unauthorized")
                    return {"status": "ok"}

            if cb_data == "noop":
                if cb_id:
                    await telegram_service.answer_callback_query(callback_query_id=cb_id)
                return {"status": "ok"}

            if cb_data.startswith("curr_p:") or cb_data.startswith("curr_set:"):
                service = MessagingService(session)
                user_data = {
                    "id": user_id,
                    "telegram_id": user_id,
                    "username": from_user.get("username"),
                    "first_name": from_user.get("first_name"),
                    "last_name": from_user.get("last_name")
                }
                user, family = service.get_or_create_user_and_family(user_data)
                if not family:
                    logger.warning(f"No family found for callback query user {user_id}")
                    if cb_id:
                        await telegram_service.answer_callback_query(callback_query_id=cb_id, text="Household not found")
                    return {"status": "ok"}

                family_service = FamilyService()

                if cb_data.startswith("curr_p:"):
                    try:
                        page = int(cb_data.split(":", 1)[1])
                    except ValueError:
                        page = 1
                    active_curr = await asyncio.to_thread(family_service.get_family_default_currency, family.id)
                    menu_text = format_currency_menu_text(active_curr)
                    keyboard = build_currency_keyboard(page=page, active_currency=active_curr)
                    if message_id:
                        await telegram_service.edit_message_text(
                            chat_id=chat_id,
                            message_id=message_id,
                            text=menu_text,
                            reply_markup=keyboard
                        )
                    if cb_id:
                        await telegram_service.answer_callback_query(callback_query_id=cb_id)
                    return {"status": "ok"}

                elif cb_data.startswith("curr_set:"):
                    target_code = cb_data.split(":", 1)[1].upper()
                    await asyncio.to_thread(family_service.set_family_default_currency, family.id, target_code)
                    target_page = 1
                    for idx, p_list in enumerate(CURRENCY_PAGES):
                        if any(c[0] == target_code for c in p_list):
                            target_page = idx + 1
                            break
                    keyboard = build_currency_keyboard(page=target_page, active_currency=target_code)
                    success_text = format_currency_success_text(target_code)
                    if message_id:
                        await telegram_service.edit_message_text(
                            chat_id=chat_id,
                            message_id=message_id,
                            text=success_text,
                            reply_markup=keyboard
                        )
                    if cb_id:
                        await telegram_service.answer_callback_query(
                            callback_query_id=cb_id,
                            text=f"Default currency set to {target_code}"
                        )
                    return {"status": "ok"}

            if cb_id:
                await telegram_service.answer_callback_query(callback_query_id=cb_id)
            return {"status": "ok"}
        except Exception as e:
            logger.error(f"Error handling Telegram callback query for user {user_id}: {e}", exc_info=True)
            if cb_id:
                try:
                    await telegram_service.answer_callback_query(callback_query_id=cb_id, text="Error processing selection.")
                except Exception:
                    pass
            return {"status": "ok"}

    if "message" not in payload:
        logger.info(f"Ignoring non-message Telegram update (keys: {list(payload.keys())})")
        return {"status": "ok"}

    message = payload["message"]
    chat = message.get("chat", {})
    from_user = message.get("from", {})

    if chat.get("type") != "private":
        return {"status": "ok"}

    user_id = from_user.get("id")
    chat_id = chat.get("id")
    if not user_id or not chat_id:
        return {"status": "ok"}

    text = message.get("text")
    voice = message.get("voice")
    message_id = message.get("message_id")

    if _cooldown_store.is_throttled(chat_id, settings.USER_COOLDOWN_SECONDS):
        logger.warning(f"Throttling rapid messages from chat_id {chat_id}")
        return {"status": "ok"}

    if settings.ALLOWED_TELEGRAM_USERS and settings.ALLOWED_TELEGRAM_USERS.strip():
        allowed_list = [entry.strip().lstrip("@").lower() for entry in settings.ALLOWED_TELEGRAM_USERS.split(",") if entry.strip()]
        user_username = (from_user.get("username") or "").lower()
        if user_username not in allowed_list and str(user_id) not in allowed_list:
            logger.warning(f"Unauthorized access attempt from user_id={user_id}, username={user_username}")
            background_tasks.add_task(telegram_service.send_message, chat_id=chat_id, text=UNAUTHORIZED_ACCESS_MESSAGE)
            return {"status": "ok"}

    try:
        service = MessagingService(session)
        user_data = {
            "id": user_id,
            "telegram_id": user_id,
            "username": from_user.get("username"),
            "first_name": from_user.get("first_name"),
            "last_name": from_user.get("last_name"),
        }
        user, family = service.get_or_create_user_and_family(user_data)

        # Handle native Telegram location pin for 1-tap timezone calibration
        if "location" in message and isinstance(message["location"], dict):
            loc = message["location"]
            lat = loc.get("latitude")
            lon = loc.get("longitude")
            if lat is not None and lon is not None:
                try:
                    tf = get_timezone_finder()
                    tz_name = tf.timezone_at(lat=float(lat), lng=float(lon))
                except Exception as e:
                    logger.warning(f"Error determining timezone from location ({lat}, {lon}): {e}")
                    tz_name = None

                if tz_name:
                    family_service = FamilyService()
                    await asyncio.to_thread(family_service.set_user_timezone, user.id, tz_name)
                    user.timezone = tz_name
                    conf_msg = (
                        f"📍 <b>Location Detected & Calibrated!</b>\n\n"
                        f"Your active timezone has been automatically set to <b>{tz_name}</b>.\n"
                        f"Your daily summaries (/today, /me) and date filters are now aligned to your local time."
                    )
                else:
                    conf_msg = "⚠️ Could not determine the timezone from this location pin. Please configure it manually using <code>/timezone &lt;city&gt;</code>."
                
                background_tasks.add_task(telegram_service.send_message, chat_id=chat_id, text=conf_msg)
                return {"status": "ok"}

        # Validate unsupported media & lengths
        unsupported_media_keys = ("document", "audio", "video", "video_note", "photo", "sticker", "contact")
        if any(k in message for k in unsupported_media_keys):
            background_tasks.add_task(telegram_service.send_message, chat_id=chat_id, text=UNSUPPORTED_FORMAT_MESSAGE)
            return {"status": "ok"}

        if text and len(text) > settings.MAX_TEXT_LENGTH:
            background_tasks.add_task(
                telegram_service.send_message,
                chat_id=chat_id,
                text=format_message_too_long(settings.MAX_TEXT_LENGTH, len(text))
            )
            return {"status": "ok"}

        if voice and voice.get("duration", 0) > settings.MAX_VOICE_DURATION_SECONDS:
            background_tasks.add_task(
                telegram_service.send_message,
                chat_id=chat_id,
                text=format_voice_too_long(settings.MAX_VOICE_DURATION_SECONDS, voice.get("duration", 0))
            )
            return {"status": "ok"}

        if voice and voice.get("file_size", 0) > settings.MAX_AUDIO_SIZE_BYTES:
            max_mb = settings.MAX_AUDIO_SIZE_BYTES / (1024 * 1024)
            recv_mb = voice.get("file_size", 0) / (1024 * 1024)
            background_tasks.add_task(
                telegram_service.send_message,
                chat_id=chat_id,
                text=format_voice_too_large(max_mb, recv_mb)
            )
            return {"status": "ok"}


        # Handle /start command
        if text and text.startswith("/start"):
            parts = text.split(maxsplit=1)
            if len(parts) > 1:
                token = parts[1].strip()
                if token.startswith("join_"):
                    token = token[5:]
                family_service = FamilyService()
                _, msg, _ = family_service.join_family_via_invite(token, user.id)
                background_tasks.add_task(telegram_service.send_message, chat_id=chat_id, text=msg)
                return {"status": "ok"}

            welcome_msg = format_welcome_message(user, family, from_user)
            background_tasks.add_task(telegram_service.send_message, chat_id=chat_id, text=welcome_msg)
            return {"status": "ok"}

        # Fast-Path Deterministic Slash Commands
        if text and text.strip().startswith("/"):
            clean_cmd = text.strip().split()[0].lower()
            cmd_args = " ".join(text.strip().split()[1:]) if len(text.strip().split()) > 1 else ""
            cmd_handler = CommandHandler()

            dispatch_map = {
                "/month": cmd_handler.handle_month,
                "/resumen": cmd_handler.handle_month,
                "/me": cmd_handler.handle_me,
                "/yo": cmd_handler.handle_me,
                "/today": cmd_handler.handle_today,
                "/hoy": cmd_handler.handle_today,
                "/bills": cmd_handler.handle_bills,
                "/vencimientos": cmd_handler.handle_bills,
                "/balance": cmd_handler.handle_balance,
                "/saldo": cmd_handler.handle_balance,
                "/timezone": cmd_handler.handle_timezone,
                "/zonahoraria": cmd_handler.handle_timezone,
                "/undo": lambda u, f, *a: cmd_handler.handle_undo(u, f),
                "/deshacer": lambda u, f, *a: cmd_handler.handle_undo(u, f),
                "/help": lambda u, f, *a: cmd_handler.handle_help(u, f),
                "/ayuda": lambda u, f, *a: cmd_handler.handle_help(u, f),
            }

            if clean_cmd in ("/currency", "/moneda"):
                menu_text, keyboard = await handle_manage_currency(user.id, family.id, cmd_args)
                background_tasks.add_task(
                    telegram_service.send_message,
                    chat_id=chat_id,
                    text=menu_text,
                    reply_markup=keyboard
                )
                return {"status": "ok"}

            if clean_cmd in dispatch_map:
                res_text = await dispatch_map[clean_cmd](user, family, cmd_args)
                background_tasks.add_task(telegram_service.send_message, chat_id=chat_id, text=res_text)
                return {"status": "ok"}

        # Handle /billing /portal command
        if text and text.strip().lower() in ("/billing", "/portal", "/cancel"):
            return await billing_service.handle_billing_command(background_tasks, user, family, chat_id)

        # Handle /upgrade, /tier, /plan, /pricing commands
        if text:
            clean_cmd = text.strip().lower()
            first_word = clean_cmd.split()[0]
            if first_word in (
                "/upgrade", "upgrade",
                "/tier", "tier",
                "/tiers", "tiers",
                "/plan", "plan",
                "/plans", "plans",
                "/pricing", "pricing"
            ):
                return await billing_service.handle_upgrade_command(background_tasks, text, user, family, chat_id)

        # Determine audio or text
        audio_file_id = voice.get("file_id") if voice else None
        if not text and not audio_file_id:
            return {"status": "ok"}

        # Quota check
        if family and check_and_reset_monthly_quota(family):
            session.add(family)
            session.commit()

        is_voice = bool(audio_file_id)
        is_tx_text = bool(text and not _is_query_or_command(text))
        if family and (is_voice or is_tx_text):
            allowed, reason, limit_val = check_transaction_allowance(family)
            if not allowed:
                if reason == "daily_limit":
                    quota_msg = DAILY_LIMIT_REACHED_MESSAGE.format(limit=limit_val)
                else:
                    is_admin = FamilyService().is_family_admin(family.id, user.id)
                    if is_admin:
                        quota_msg = (
                            f"⛔ <b>Monthly Free Limit Reached ({FREE_TIER_MONTHLY_LIMIT}/{FREE_TIER_MONTHLY_LIMIT} logs)</b>\n\n"
                            f"Your family has reached the limit of {FREE_TIER_MONTHLY_LIMIT} free transaction logs for this month. "
                            "Type /upgrade to unlock unlimited AI logs, or continue using our unlimited free commands (/month, /me, /balance, /bills)."
                        )
                    else:
                        quota_msg = (
                            f"⛔ <b>Monthly Free Limit Reached ({FREE_TIER_MONTHLY_LIMIT}/{FREE_TIER_MONTHLY_LIMIT} logs)</b>\n\n"
                            f"Your family has reached the limit of {FREE_TIER_MONTHLY_LIMIT} free transaction logs for this month. "
                            "Please ask your family admin to upgrade the workspace via /upgrade, or continue using our unlimited free commands (/month, /me, /balance, /bills)."
                        )
                background_tasks.add_task(telegram_service.send_message, chat_id=chat_id, text=quota_msg)
                return {"status": "ok"}

        orchestrator = AIOrchestrator()
        background_tasks.add_task(
            orchestrator.orchestrate,
            user_id=str(user.id),
            text=text,
            audio_file_id=audio_file_id,
            chat_id=chat_id,
            message_id=message_id
        )
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Error handling Telegram webhook message for user_id={user_id}, chat_id={chat_id}: {e}", exc_info=True)
        return {"status": "error", "detail": "Internal processing error"}


class LifecyclePayload(BaseModel):
    family_id: str
    charge_id: Optional[str] = None
    expiration_timestamp: Optional[int] = None


@router.post("/webhook/renewal")
async def handle_renewal(payload: LifecyclePayload, session: Session = Depends(get_session), x_telegram_bot_api_secret_token: Optional[str] = Header(None)):
    if not verify_messaging_secret(x_telegram_bot_api_secret_token):
        logger.warning("Invalid Telegram webhook secret token attempt.")
        raise HTTPException(status_code=403, detail="Invalid secret token")
    try:
        family = session.get(Family, uuid.UUID(payload.family_id))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid family_id")
    if not family:
        raise HTTPException(status_code=404, detail="Family not found")
        
    handle_recurring_renewal(
        session=session,
        family=family,
        charge_id=payload.charge_id,
        expiration_timestamp=payload.expiration_timestamp
    )
    return {"status": "ok"}


@router.post("/webhook/cancellation")
async def handle_cancellation(payload: LifecyclePayload, session: Session = Depends(get_session), x_telegram_bot_api_secret_token: Optional[str] = Header(None)):
    if not verify_messaging_secret(x_telegram_bot_api_secret_token):
        logger.warning("Invalid Telegram webhook secret token attempt.")
        raise HTTPException(status_code=403, detail="Invalid secret token")
    try:
        family = session.get(Family, uuid.UUID(payload.family_id))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid family_id")
    if not family:
        raise HTTPException(status_code=404, detail="Family not found")
        
    handle_subscription_cancellation(session=session, family=family)
    return {"status": "ok"}


@router.post("/webhook/failure")
async def handle_failure(
    payload: LifecyclePayload, 
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session), 
    x_telegram_bot_api_secret_token: Optional[str] = Header(None)
):
    if not verify_messaging_secret(x_telegram_bot_api_secret_token):
        logger.warning("Invalid Telegram webhook secret token attempt.")
        raise HTTPException(status_code=403, detail="Invalid secret token")

    try:
        family = session.get(Family, uuid.UUID(payload.family_id))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid family_id")
    if not family:
        raise HTTPException(status_code=404, detail="Family not found")
        
    if family.plan_type != "lifetime_pro":
        handle_payment_failure(session=session, family=family)
        
        users = session.exec(select(User).where(User.family_id == family.id)).all()
        fam_service = FamilyService()
        admin_user = next((u for u in users if fam_service.is_family_admin(family.id, u.id)), users[0] if users else None)
        if admin_user and admin_user.telegram_id:
            telegram_service = TelegramService()
            failure_msg = (
                "⚠️ <b>Subscription Expired/Failed:</b> Your workspace payment failed or expired. "
                f"Your workspace has transitioned to the Free tier ({FREE_TIER_MONTHLY_LIMIT} logs/month). "
                "All your historical data, past entries, and Notion sync remain 100% safe."
            )
            background_tasks.add_task(telegram_service.send_message, chat_id=admin_user.telegram_id, text=failure_msg)
            
    return {"status": "ok"}
