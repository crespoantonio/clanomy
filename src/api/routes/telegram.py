"""
Telegram Webhook Route Handler for Clanomy.
Provides HTTP ingress for Telegram Bot webhook updates, lifecycle callbacks, and payment webhooks.
"""

from fastapi import APIRouter, Header, HTTPException, Depends, BackgroundTasks, Request
from pydantic import BaseModel
from typing import Optional, Dict, Any
import time
import uuid
from uuid import UUID
import logging
import asyncio
import re
import html
from collections import OrderedDict
from sqlmodel import Session, select

from src.core.config import settings
from src.core.security import verify_messaging_secret
from src.core.encryption import EncryptionService
from src.db.session import get_session, engine
from src.db.models import User, Family, ScheduledBill
from src.services.messaging_service import MessagingService
from src.services.ai_orchestrator import AIOrchestrator
from src.services.telegram_service import TelegramService
from src.services.family_service import FamilyService
from src.services.whisper_service import WhisperService
from src.services.billing.billing_service import BillingService
from src.services.handlers.command_handler import CommandHandler
from src.services.handlers.currency_handler import (
    handle_manage_currency,
    build_currency_keyboard,
    format_currency_menu_text,
    format_currency_success_text,
    CURRENCY_PAGES
)
from src.services.handlers.bill_handler import (
    build_bills_keyboard,
    build_bill_settlement_card,
    settle_bill_by_id,
    handle_bills_interactive
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
_pending_bill_edits: Dict[int, Dict[str, Any]] = {}


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

            if cb_data.startswith(("curr_p:", "curr_set:", "bills_p:", "bill_v:", "bill_pay:", "bill_edit:")):
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
                    success_text = format_currency_success_text(target_code)

                    if cb_id:
                        await telegram_service.answer_callback_query(
                            callback_query_id=cb_id,
                            text=f"Default currency set to {target_code}"
                        )

                    if message_id:
                        deleted = await telegram_service.delete_message(chat_id=chat_id, message_id=message_id)
                        if not deleted:
                            await telegram_service.edit_message_text(
                                chat_id=chat_id,
                                message_id=message_id,
                                text="<i>Currency selection completed.</i>",
                                reply_markup={"inline_keyboard": []}
                            )

                    await telegram_service.send_message(chat_id=chat_id, text=success_text)
                    return {"status": "ok"}

                elif cb_data.startswith("bills_p:"):
                    parts = cb_data.split(":")
                    page = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
                    tf_code = parts[2] if len(parts) > 2 else "this"
                    cmd_args = "next" if tf_code == "next" else ""
                    cmd_handler = CommandHandler()
                    menu_text, keyboard = await cmd_handler.handle_bills_interactive(user, family, args=cmd_args, page=page)
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

                elif cb_data.startswith("bill_v:"):
                    parts = cb_data.split(":")
                    try:
                        target_bill_id = UUID(parts[1])
                    except (ValueError, IndexError):
                        target_bill_id = None

                    if target_bill_id:
                        ret_page = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 1
                        tf_code = parts[3] if len(parts) > 3 else "this"
                        timeframe = "next_month" if tf_code == "next" else "this_month"
                        is_spanish = (from_user.get("language_code") or "").lower().startswith("es")
                        card_text, card_keyboard = build_bill_settlement_card(
                            bill_id=target_bill_id,
                            family_id=family.id,
                            return_page=ret_page,
                            timeframe=timeframe,
                            is_spanish=is_spanish
                        )
                        if message_id:
                            await telegram_service.edit_message_text(
                                chat_id=chat_id,
                                message_id=message_id,
                                text=card_text,
                                reply_markup=card_keyboard
                            )
                    if cb_id:
                        await telegram_service.answer_callback_query(callback_query_id=cb_id)
                    return {"status": "ok"}

                elif cb_data.startswith("bill_pay:"):
                    parts = cb_data.split(":")
                    try:
                        target_bill_id = UUID(parts[1])
                    except (ValueError, IndexError):
                        target_bill_id = None

                    tf_code = parts[2] if len(parts) > 2 else "this"
                    if target_bill_id:
                        is_spanish = (from_user.get("language_code") or "").lower().startswith("es")
                        success, res_msg = settle_bill_by_id(
                            bill_id=target_bill_id,
                            user_id=user.id,
                            family_id=family.id,
                            is_spanish=is_spanish
                        )
                        back_btn = "🔙 Volver a Facturas" if is_spanish else "🔙 Back to Bills"
                        back_kb = {"inline_keyboard": [[{"text": back_btn, "callback_data": f"bills_p:1:{tf_code}"}]]}
                        if message_id:
                            await telegram_service.edit_message_text(
                                chat_id=chat_id,
                                message_id=message_id,
                                text=res_msg,
                                reply_markup=back_kb
                            )
                        if cb_id:
                            toast = "¡Factura pagada!" if (is_spanish and success) else "Bill marked as paid!" if success else "Error"
                            await telegram_service.answer_callback_query(callback_query_id=cb_id, text=toast)
                    else:
                        if cb_id:
                            await telegram_service.answer_callback_query(callback_query_id=cb_id, text="Invalid bill")
                    return {"status": "ok"}

                elif cb_data.startswith("bill_edit:"):
                    parts = cb_data.split(":")
                    try:
                        target_bill_id = UUID(parts[1])
                    except (ValueError, IndexError):
                        target_bill_id = None

                    if target_bill_id:
                        with Session(engine) as s:
                            b = s.get(ScheduledBill, target_bill_id)
                            enc_s = EncryptionService()
                            cpt = (enc_s.decrypt(b.concept) if b else None) or "Bill"

                        _pending_bill_edits[user_id] = {
                            "bill_id": target_bill_id,
                            "concept": cpt,
                            "timestamp": time.time()
                        }

                        is_spanish = (from_user.get("language_code") or "").lower().startswith("es")
                        if is_spanish:
                            prompt = (
                                f'<a href="tg://bill/{target_bill_id}">&#8203;</a>'
                                f"✏️ <b>Pagar '{html.escape(cpt)}'</b>\n\n"
                                f"Responde con el monto pagado (ej: <code>45.50</code>) — <i>100% gratis</i>,\n"
                                f"o envía un audio <i>(consume 1 crédito de IA 🎙️)</i>.\n\n"
                                f"<i>(Escribe 'cancel' para abortar)</i>"
                            )
                            toast = "Responde con el nuevo monto"
                        else:
                            prompt = (
                                f'<a href="tg://bill/{target_bill_id}">&#8203;</a>'
                                f"✏️ <b>Settle '{html.escape(cpt)}'</b>\n\n"
                                f"Reply with the exact amount paid (e.g. <code>45.50</code>) — <i>100% free</i>,\n"
                                f"or send a voice note <i>(uses 1 AI log 🎙️)</i>.\n\n"
                                f"<i>(Send 'cancel' to abort)</i>"
                            )
                            toast = "Reply with the new amount"

                        await telegram_service.send_message(
                            chat_id=chat_id,
                            text=prompt,
                            reply_markup={"force_reply": True, "selective": True}
                        )
                        if cb_id:
                            await telegram_service.answer_callback_query(callback_query_id=cb_id, text=toast)
                    else:
                        if cb_id:
                            await telegram_service.answer_callback_query(callback_query_id=cb_id, text="Invalid bill")
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


        # Handle ForceReply response, reply to error, or bare amount for bill settlement override
        reply_to = message.get("reply_to_message")
        reply_to_text = (reply_to.get("text") or "") if reply_to else ""

        cached_edit = _pending_bill_edits.get(user_id)
        is_active_pending_edit = bool(cached_edit and (time.time() - cached_edit.get("timestamp", 0)) < 600)

        is_bill_reply = False
        if reply_to:
            if (
                "Settle '" in reply_to_text
                or "Pagar '" in reply_to_text
                or "[Bill ID: " in reply_to_text
                or is_active_pending_edit
            ):
                is_bill_reply = True
        elif is_active_pending_edit and text:
            clean_strip = text.strip()
            is_cancel = clean_strip.lower() in ("cancel", "cancelar", "/cancel", "abort")
            s_num = re.sub(r'[\$€£¥₹]', '', clean_strip).strip()
            s_num = re.sub(r'^[a-zA-Z]{3,4}\s+|\s+[a-zA-Z]{3,4}$', '', s_num, flags=re.IGNORECASE).strip()
            is_bare_amount = bool(
                re.match(r'^\d{1,6}(?:[.,]\d{1,2})?$', s_num)
                or re.match(r'^\d{1,3}(?:[.,]\d{3})+(?:[.,]\d{1,2})?$', s_num)
            )
            if is_cancel or is_bare_amount:
                is_bill_reply = True

        if is_bill_reply:
            target_bill_id = None
            # 1. Check in-memory pending edit cache (valid for 10 minutes)
            if cached_edit and (time.time() - cached_edit.get("timestamp", 0)) < 600:
                target_bill_id = cached_edit.get("bill_id")

            # 2. Check entities for invisible link tg://bill/<uuid>
            if not target_bill_id and reply_to:
                for ent in reply_to.get("entities", []):
                    if ent.get("type") == "text_link":
                        u = ent.get("url", "")
                        if u.startswith("tg://bill/"):
                            try:
                                target_bill_id = UUID(u.split("tg://bill/")[1])
                                break
                            except ValueError:
                                pass

            # 3. Check legacy text pattern [Bill ID: <uuid>]
            if not target_bill_id and "[Bill ID: " in reply_to_text:
                m_legacy = re.search(r'\[Bill ID:\s*([a-f0-9\-]+)\]', reply_to_text, re.IGNORECASE)
                if m_legacy:
                    try:
                        target_bill_id = UUID(m_legacy.group(1))
                    except ValueError:
                        pass

            # 4. Fallback: match concept name from prompt text quotes
            if not target_bill_id and reply_to_text and family:
                m_cpt = re.search(r"[‘'\"`]([^'\"`]+)[’'\"`]", reply_to_text)
                if m_cpt:
                    target_cpt = m_cpt.group(1).strip().lower()
                    enc_s = EncryptionService()
                    pending_bills = session.exec(
                        select(ScheduledBill).where(
                            ScheduledBill.family_id == family.id,
                            ScheduledBill.status == "pending"
                        )
                    ).all()
                    for pb in pending_bills:
                        dec = enc_s.decrypt(pb.concept)
                        if dec and dec.strip().lower() == target_cpt:
                            target_bill_id = pb.id
                            break

            if target_bill_id:
                user_lang = (from_user.get("language_code") or "").lower()
                is_spanish = user_lang.startswith("es")

                # Check if user cancelled
                if text and text.strip().lower() in ("cancel", "cancelar", "/cancel", "abort"):
                    _pending_bill_edits.pop(user_id, None)
                    cancel_msg = "❌ Pago de factura cancelado. La factura sigue pendiente." if is_spanish else "❌ Bill payment cancelled. The bill remains pending."
                    background_tasks.add_task(telegram_service.send_message, chat_id=chat_id, text=cancel_msg)
                    return {"status": "ok"}

                is_voice_override = False
                input_text = text
                if not input_text and voice:
                    is_voice_override = True
                    # Voice note consumes 1 AI usage: validate family quota first
                    if family:
                        if check_and_reset_monthly_quota(family):
                            session.add(family)
                            session.commit()
                        allowed, reason, limit_val = check_transaction_allowance(family)
                        if not allowed:
                            if user_id in _pending_bill_edits:
                                _pending_bill_edits[user_id]["timestamp"] = time.time()
                            if reason == "daily_limit":
                                daily_note = (
                                    "\n\n💡 <i>¡Aún puedes escribir el monto por texto gratis (ej: <code>45.50</code>) para pagar esta factura!</i>"
                                    if is_spanish else
                                    "\n\n💡 <i>You can still type the amount for free (e.g. <code>45.50</code>) to settle this bill!</i>"
                                )
                                quota_msg = DAILY_LIMIT_REACHED_MESSAGE.format(limit=limit_val) + daily_note
                            else:
                                quota_msg = (
                                    f"⛔ <b>Límite mensual de IA alcanzado ({family.monthly_tx_count}/{FREE_TIER_MONTHLY_LIMIT} registros)</b>\n\n"
                                    "Has alcanzado el límite mensual de registros con IA.\n"
                                    "¡Puedes escribir el monto por texto gratis (ej: <code>45.50</code>) para pagar esta factura!"
                                    if is_spanish else
                                    f"⛔ <b>Monthly AI Quota Reached ({family.monthly_tx_count}/{FREE_TIER_MONTHLY_LIMIT} logs)</b>\n\n"
                                    "You've reached your free monthly AI quota.\n"
                                    "You can still type the amount for free (e.g. <code>45.50</code>) to settle this bill!"
                                )
                            background_tasks.add_task(telegram_service.send_message, chat_id=chat_id, text=quota_msg)
                            return {"status": "ok"}

                    try:
                        audio_file_id = voice.get("file_id")
                        audio_bytes = await telegram_service.download_file_bytes(audio_file_id)
                        whisper_service = WhisperService()
                        transcribed, _ = await whisper_service.transcribe(audio_bytes=audio_bytes)
                        input_text = transcribed
                    except Exception as e:
                        logger.error(f"Error transcribing voice note for bill override: {e}")
                        input_text = None

                override_amt = None
                if input_text:
                    clean_input = input_text.strip()
                    if "." in clean_input and "," in clean_input:
                        if clean_input.rfind(",") > clean_input.rfind("."):
                            clean_input = clean_input.replace(".", "").replace(",", ".")
                        else:
                            clean_input = clean_input.replace(",", "")
                    else:
                        clean_input = clean_input.replace(",", ".")

                    m_num = re.search(r'(\d+(?:\.\d{1,2})?)', clean_input)
                    if m_num:
                        try:
                            val = float(m_num.group(1))
                            if val > 0:
                                override_amt = val
                        except ValueError:
                            pass

                if override_amt is not None:
                    _pending_bill_edits.pop(user_id, None)
                    success, settle_msg = settle_bill_by_id(
                        bill_id=target_bill_id,
                        user_id=user.id,
                        family_id=family.id,
                        override_amount=override_amt,
                        is_spanish=is_spanish
                    )
                    if success and is_voice_override and family:
                        family.monthly_tx_count = (family.monthly_tx_count or 0) + 1
                        family.daily_tx_count = (family.daily_tx_count or 0) + 1
                        session.add(family)
                        session.commit()

                    background_tasks.add_task(telegram_service.send_message, chat_id=chat_id, text=settle_msg)
                    return {"status": "ok"}
                else:
                    err_msg = (
                        "⚠️ No pude reconocer un monto válido. Por favor responde con un número (ej: 45.50) o escribe 'cancel'."
                        if is_spanish else
                        "⚠️ Could not recognize a valid amount. Please reply with a number (e.g. 45.50) or type 'cancel'."
                    )
                    background_tasks.add_task(telegram_service.send_message, chat_id=chat_id, text=err_msg)
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

            if clean_cmd in ("/bills", "/vencimientos"):
                menu_text, keyboard = await cmd_handler.handle_bills_interactive(user, family, cmd_args)
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
