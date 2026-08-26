from fastapi import APIRouter, Header, HTTPException, Depends, BackgroundTasks, Request
from pydantic import BaseModel
from typing import Optional, Dict, Any
import time
import uuid
import logging
from sqlmodel import Session, select

from src.core.config import settings
from src.services.messaging_service import MessagingService
from src.services.ai_orchestrator import AIOrchestrator
from src.services.telegram_service import TelegramService
from src.services.family_service import FamilyService
from src.services.subscription_service import (
    extract_plan_and_family_id,
    handle_successful_payment,
    handle_subscription_expiry,
    handle_payment_failure
)
from src.db.session import get_session
from src.db.models import User, Family, Transaction

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/telegram", tags=["Telegram Webhook"])

_user_last_msg: Dict[int, float] = {}

def _is_query_or_command(text: Optional[str]) -> bool:
    if not text:
        return False
    t = text.strip().lower()
    if t.startswith("/"):
        return True
    if "confirm delete" in t or "delete account" in t:
        return True
    if t.startswith(("export", "notion", "invite", "create family", "leave family", "remove member", "family info", "my family", "upgrade")):
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
    # Verify the secret token from Telegram
    if not x_telegram_bot_api_secret_token or x_telegram_bot_api_secret_token != settings.MESSAGING_WEBHOOK_SECRET:
        logger.warning("Invalid Telegram webhook secret token attempt.")
        raise HTTPException(status_code=403, detail="Invalid secret token")

    payload = await request.json()
    telegram_service = TelegramService()

    # 1. Handle pre_checkout_query
    if "pre_checkout_query" in payload:
        pre_checkout = payload["pre_checkout_query"]
        query_id = pre_checkout.get("id")
        if not query_id:
            logger.error("Missing pre_checkout_query id")
            raise HTTPException(status_code=400, detail="Missing query_id")
        invoice_payload = pre_checkout.get("invoice_payload", "")

        from src.services.subscription_service import validate_invoice_payload
        try:
            validate_invoice_payload(invoice_payload)
            await telegram_service.answer_pre_checkout_query(
                pre_checkout_query_id=query_id,
                ok=True
            )
        except ValueError as e:
            logger.warning(f"Rejecting pre_checkout_query {query_id} for payload '{invoice_payload}': {e}")
            await telegram_service.answer_pre_checkout_query(
                pre_checkout_query_id=query_id,
                ok=False,
                error_message="Invalid or unsupported subscription plan."
            )
        return {"status": "ok"}
    
    # Fast exit for non-message updates (e.g. edited_message, inline_query)
    if "message" not in payload:
        return {"status": "ok"}
        
    message = payload["message"]
    chat = message.get("chat", {})
    from_user = message.get("from", {})
    
    # We only care about private chats for now
    if chat.get("type") != "private":
        return {"status": "ok"}
        
    user_id = from_user.get("id")
    chat_id = chat.get("id")
    
    if not user_id or not chat_id:
        return {"status": "ok"}

    # Per-user cooldown check to prevent spam / DoS
    if settings.USER_COOLDOWN_SECONDS > 0:
        now = time.time()
        last_time = _user_last_msg.get(chat_id, 0.0)
        if (now - last_time) < settings.USER_COOLDOWN_SECONDS:
            logger.warning(f"Throttling rapid messages from chat_id {chat_id}")
            return {"status": "ok"}
        _user_last_msg[chat_id] = now

    # Access control: If ALLOWED_TELEGRAM_USERS is configured (e.g. self-hosted privacy hardening),
    # restrict access only to listed usernames or user IDs.
    if settings.ALLOWED_TELEGRAM_USERS and settings.ALLOWED_TELEGRAM_USERS.strip():
        allowed_list = [entry.strip().lstrip("@").lower() for entry in settings.ALLOWED_TELEGRAM_USERS.split(",") if entry.strip()]
        user_username = (from_user.get("username") or "").lower()
        user_id_str = str(user_id)
        
        if user_username not in allowed_list and user_id_str not in allowed_list:
            logger.warning(f"Unauthorized access attempt from user_id={user_id}, username={user_username}")
            denial_msg = (
                "🔒 <b>Private Instance</b>\n\n"
                "This Clanomy bot instance is private and restricted to authorized users."
            )
            background_tasks.add_task(telegram_service.send_message, chat_id=chat_id, text=denial_msg)
            return {"status": "ok"}

    # Resolve or create the user and family
    service = MessagingService(session)
    user_data = {
        "id": user_id,
        "username": from_user.get("username"),
        "first_name": from_user.get("first_name"),
        "last_name": from_user.get("last_name")
    }
    
    user, family = service.get_or_create_user_and_family(user_data)

    # 2. Handle successful_payment
    successful_payment = message.get("successful_payment")
    if successful_payment:
        invoice_payload = successful_payment.get("invoice_payload", "")
        charge_id = successful_payment.get("telegram_payment_charge_id")
        expiration_timestamp = successful_payment.get("subscription_expiration_date")

        try:
            plan_type, payload_family_id = extract_plan_and_family_id(invoice_payload)
        except ValueError as e:
            logger.error(f"Invalid invoice payload in successful_payment: {e}")
            raise HTTPException(status_code=400, detail="Invalid invoice payload")

        target_family = family
        if payload_family_id:
            try:
                fam_uuid = uuid.UUID(payload_family_id)
                db_fam = session.get(Family, fam_uuid)
                if db_fam:
                    target_family = db_fam
            except ValueError:
                pass

        if not target_family:
            logger.error("Target family not found for successful payment.")
            raise HTTPException(status_code=400, detail="Target family not found")

        # Query existing members before plan transition to notify multi-member households if switching to solo_pro
        existing_members = session.exec(select(User).where(User.family_id == target_family.id)).all()
        was_multi_member = len(existing_members) > 1

        result = handle_successful_payment(
            session=session,
            family=target_family,
            invoice_payload=invoice_payload,
            charge_id=charge_id,
            expiration_timestamp=expiration_timestamp
        )

        if target_family.plan_type == "lifetime_pro" or result.get("status") == "ignored_lifetime":
            confirmation_text = (
                "⭐️ <b>Clanomy Lifetime Pro Active</b>\n\n"
                "Your workspace is enjoying permanent Lifetime Pro status. Thank you for your payment!"
            )
            background_tasks.add_task(telegram_service.send_message, chat_id=chat_id, text=confirmation_text)
        elif target_family.plan_type == "solo_pro":
            confirmation_text = (
                "🎉 <b>Welcome to Clanomy Solo Pro!</b>\n\n"
                "Your subscription is now active! You have unlocked unlimited voice and text transaction logging "
                "and AI queries for your personal workspace. Thank you for supporting Clanomy!"
            )
            background_tasks.add_task(telegram_service.send_message, chat_id=chat_id, text=confirmation_text)

            if was_multi_member:
                fam_service = FamilyService()
                for member in existing_members:
                    if member.telegram_id and not fam_service.is_family_admin(target_family.id, member.id):
                        member_notice = (
                            "ℹ️ <b>Workspace Plan Update</b>\n\n"
                            "Your workspace admin has updated the workspace to the <b>Solo Pro</b> plan. "
                            "Solo Pro is designed for an individual user.\n\n"
                            "To start your own personal workspace and keep logging transactions, "
                            "simply type /leavefamily."
                        )
                        background_tasks.add_task(
                            telegram_service.send_message,
                            chat_id=member.telegram_id,
                            text=member_notice
                        )
        elif target_family.plan_type == "family_pro":
            confirmation_text = (
                "🎉 <b>Welcome to Clanomy Family Pro!</b>\n\n"
                "Your subscription is now active! You have unlocked unlimited voice and text transaction logging, "
                "shared family ledger for up to 5 members, and real-time Notion mirroring. "
                "Thank you for supporting Clanomy!"
            )
            background_tasks.add_task(telegram_service.send_message, chat_id=chat_id, text=confirmation_text)

        return {"status": "ok"}

    # 3. Handle refunded_payment
    refunded_payment = message.get("refunded_payment")
    if refunded_payment:
        invoice_payload = refunded_payment.get("invoice_payload", "")
        
        try:
            _, payload_family_id = extract_plan_and_family_id(invoice_payload)
        except ValueError:
            payload_family_id = None
            
        target_family = family
        if payload_family_id:
            try:
                fam_uuid = uuid.UUID(payload_family_id)
                db_fam = session.get(Family, fam_uuid)
                if db_fam:
                    target_family = db_fam
            except ValueError:
                pass

        if target_family and target_family.plan_type != "lifetime_pro":
            handle_subscription_expiry(session, target_family)
            refund_msg = (
                "ℹ️ <b>Subscription Update:</b> Your payment was refunded. "
                "Your workspace has transitioned to the Free tier (30 logs/month). "
                "All your historical data, past entries, and Notion sync remain 100% safe."
            )
            background_tasks.add_task(telegram_service.send_message, chat_id=chat_id, text=refund_msg)
        return {"status": "ok"}

    # Check for unsupported media types (photos, documents, generic audio, videos, stickers, contacts, locations)
    unsupported_media_keys = ("document", "audio", "video", "video_note", "photo", "sticker", "contact", "location")
    if any(k in message for k in unsupported_media_keys):
        unsupported_msg = (
            "⚠️ <b>Unsupported Format</b>\n\n"
            "Clanomy only accepts native voice notes (hold the mic 🎙️ icon) or text messages (e.g. <i>'Spent $24 on lunch'</i>)."
        )
        background_tasks.add_task(telegram_service.send_message, chat_id=chat_id, text=unsupported_msg)
        return {"status": "ok"}

    text = message.get("text")
    voice = message.get("voice")
    message_id = message.get("message_id")

    # Guardrail: Enforce max text length
    if text and len(text) > settings.MAX_TEXT_LENGTH:
        length_msg = (
            f"📝 <b>Message Too Long</b>\n\n"
            f"Please keep transactions and queries under {settings.MAX_TEXT_LENGTH} characters "
            f"(received {len(text)} characters)."
        )
        background_tasks.add_task(telegram_service.send_message, chat_id=chat_id, text=length_msg)
        return {"status": "ok"}

    # Guardrail: Enforce max voice duration
    if voice:
        voice_duration = voice.get("duration", 0)
        if voice_duration > settings.MAX_VOICE_DURATION_SECONDS:
            duration_msg = (
                f"⏱️ <b>Voice Note Too Long</b>\n\n"
                f"Please keep voice logs under {settings.MAX_VOICE_DURATION_SECONDS} seconds "
                f"(recording was {voice_duration} seconds)."
            )
            background_tasks.add_task(telegram_service.send_message, chat_id=chat_id, text=duration_msg)
            return {"status": "ok"}
    
    # Process /start command
    if text and text.startswith("/start"):
        parts = text.split(maxsplit=1)
        if len(parts) > 1:
            payload_arg = parts[1].strip()
            if payload_arg.startswith("join_"):
                token = payload_arg[5:]
            else:
                token = payload_arg
            
            family_service = FamilyService()
            success, msg, _ = family_service.join_family_via_invite(token, user.id)
            background_tasks.add_task(telegram_service.send_message, chat_id=chat_id, text=msg)
            return {"status": "ok"}

        trial_badge = ""
        if family and family.plan_type == "trial":
            trial_badge = "⭐️ <b>60-Day Family Pro Trial:</b> You are enjoying 60 days of unlimited logs and family features for free!\n\n"
        elif family and family.plan_type == "free":
            trial_badge = "📦 <b>Plan:</b> Free Plan (30 free transaction logs per month). Type /upgrade anytime for unlimited logs.\n\n"

        welcome_text = (
            f"👋 <b>Welcome to {settings.PROJECT_NAME}, {from_user.get('first_name') or 'User'}!</b>\n\n"
            f"{trial_badge}"
            "Here is what you can do with Clanomy:\n"
            "🎙️ <b>Voice & Text Logging:</b> Send voice notes or type expenses & income (e.g. <i>'Spent $45 on groceries'</i> or <i>'Got $3,500 salary'</i>).\n"
            "💡 <b>Dual Income & Expense Tracking:</b> Automatically parses, categorizes, and updates your monthly cash flow.\n"
            "💬 <b>Ask AI & Cash Flow Queries:</b> Ask questions like <i>'How much did we spend on food this month?'</i> or <i>'What\\'s our net savings?'</i>.\n"
            "📊 <b>Notion Mirroring:</b> Real-time synchronization with your Notion database via /notion.\n"
            "👨‍👩‍👧‍👦 <b>Family Sharing:</b> Share a unified household ledger using /invite and manage members with /family.\n\n"
            "Go ahead and log your first transaction now, or ask a question!"
        )
        background_tasks.add_task(telegram_service.send_message, chat_id=chat_id, text=welcome_text)
        return {"status": "ok"}


    # Process /upgrade command
    if text and (text.strip().lower() == "/upgrade" or text.strip().lower().startswith("/upgrade ") or text.strip().lower() == "upgrade"):
        if not settings.ENABLE_SUBSCRIPTIONS:
            self_hosted_msg = (
                "🏠 <b>Self-Hosted Clanomy</b>\n\n"
                "You are running a self-hosted instance of Clanomy. All features (unlimited voice and text logging, "
                "multi-member family sharing, Notion syncing, natural language insights, and data exports) are "
                "<b>fully unlocked</b> with no quotas or subscriptions required!"
            )
            background_tasks.add_task(telegram_service.send_message, chat_id=chat_id, text=self_hosted_msg)
            return {"status": "ok"}

        parts = text.split()
        arg = parts[1].lower() if len(parts) > 1 else None
        
        family_id_str = str(family.id) if family else (str(user.family_id) if user and user.family_id else "")

        if arg in ["solo", "solo_pro", "single"]:
            background_tasks.add_task(
                telegram_service.send_subscription_invoice,
                chat_id=chat_id,
                plan_type="solo_pro",
                family_id=family_id_str
            )
            return {"status": "ok"}
        elif arg in ["family", "family_pro", "fam"]:
            background_tasks.add_task(
                telegram_service.send_subscription_invoice,
                chat_id=chat_id,
                plan_type="family_pro",
                family_id=family_id_str
            )
            return {"status": "ok"}
        else:
            intro_msg = (
                "⭐️ <b>Upgrade to Clanomy Pro</b>\n\n"
                "Choose the plan that fits your needs with seamless, auto-renewing Telegram Stars billing (Apple Pay / Google Pay / Card):\n\n"
                "1️⃣ <b>Solo Pro (150 Stars / month)</b>\n"
                "• Unlimited text & voice expense & income logging\n"
                "• AI Natural language queries & cash flow insights\n"
                "• CSV & JSON financial exports\n"
                "• 1 User\n\n"
                "2️⃣ <b>Family Pro (300 Stars / month)</b>\n"
                "• Everything in Solo Pro\n"
                "• Up to 5 Family Members with shared ledger\n"
                "• Real-time Notion database mirroring\n"
                "• Per-member spending attribution & budget visibility\n\n"
                "<i>Invoices for both options are attached below. Tap <b>Pay</b> on your chosen tier to activate immediately!</i>"
            )
            background_tasks.add_task(telegram_service.send_message, chat_id=chat_id, text=intro_msg)
            background_tasks.add_task(
                telegram_service.send_subscription_invoice,
                chat_id=chat_id,
                plan_type="solo_pro",
                family_id=family_id_str
            )
            background_tasks.add_task(
                telegram_service.send_subscription_invoice,
                chat_id=chat_id,
                plan_type="family_pro",
                family_id=family_id_str
            )
            return {"status": "ok"}

    # Determine if there is text or audio to process
    audio_file_id = None
    if voice:
        audio_file_id = voice.get("file_id")
        
    if not text and not audio_file_id:
        return {"status": "ok"}

    orchestrator = AIOrchestrator()

    # Early fast-fail quota check (< 5ms) before downloading audio or invoking AI services
    from src.services.subscription_service import can_log_transaction, check_and_reset_monthly_quota

    # Lazy monthly reset: commit reset if month changed
    if family and check_and_reset_monthly_quota(family):
        session.add(family)
        session.commit()

    is_voice = bool(audio_file_id)
    is_transaction_text = bool(text and not _is_query_or_command(text))

    if family and (is_voice or is_transaction_text):
        if not can_log_transaction(family):
            family_service = FamilyService()
            is_admin = family_service.is_family_admin(family.id, user.id)
            if is_admin:
                quota_msg = (
                    "⛔ <b>Monthly Free Limit Reached (30/30 logs)</b>\n\n"
                    "Your family has reached the limit of 30 free transaction logs for this month. "
                    "Type /upgrade to unlock unlimited logs for your household."
                )
            else:
                quota_msg = (
                    "⛔ <b>Monthly Free Limit Reached (30/30 logs)</b>\n\n"
                    "Your family has reached the limit of 30 free transaction logs for this month. "
                    "Please ask your family admin to upgrade the workspace via /upgrade."
                )
            background_tasks.add_task(telegram_service.send_message, chat_id=chat_id, text=quota_msg)
            return {"status": "ok"}

    # Process expense log in background
    background_tasks.add_task(
        orchestrator.orchestrate,
        user_id=str(user.id),
        text=text,
        audio_file_id=audio_file_id,
        chat_id=chat_id,
        message_id=message_id
    )

    return {"status": "ok"}

class LifecyclePayload(BaseModel):
    family_id: str
    charge_id: Optional[str] = None
    expiration_timestamp: Optional[int] = None

@router.post("/webhook/renewal")
async def handle_renewal(payload: LifecyclePayload, session: Session = Depends(get_session), x_telegram_bot_api_secret_token: Optional[str] = Header(None)):
    if not x_telegram_bot_api_secret_token or x_telegram_bot_api_secret_token != settings.MESSAGING_WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret token")
    from src.services.subscription_service import handle_recurring_renewal
    from src.db.models import Family
    import uuid
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
    if not x_telegram_bot_api_secret_token or x_telegram_bot_api_secret_token != settings.MESSAGING_WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret token")
    from src.services.subscription_service import handle_subscription_cancellation
    from src.db.models import Family
    import uuid
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
    if not x_telegram_bot_api_secret_token or x_telegram_bot_api_secret_token != settings.MESSAGING_WEBHOOK_SECRET:
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
                "Your workspace has transitioned to the Free tier (30 logs/month). "
                "All your historical data, past entries, and Notion sync remain 100% safe."
            )
            background_tasks.add_task(telegram_service.send_message, chat_id=admin_user.telegram_id, text=failure_msg)
            
    return {"status": "ok"}
