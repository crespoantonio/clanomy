from fastapi import APIRouter, Header, HTTPException, Depends, BackgroundTasks, Request
from pydantic import BaseModel
from typing import Optional, Dict, Any
from src.core.config import settings
from src.services.messaging_service import MessagingService
from src.services.ai_orchestrator import AIOrchestrator
from src.services.telegram_service import TelegramService
from src.services.family_service import FamilyService
from src.db.session import get_session
from sqlmodel import Session
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/telegram", tags=["Telegram Webhook"])

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

    # Resolve or create the user and family
    service = MessagingService(session)
    user_data = {
        "id": user_id,
        "username": from_user.get("username"),
        "first_name": from_user.get("first_name"),
        "last_name": from_user.get("last_name")
    }
    
    user, family = service.get_or_create_user_and_family(user_data)
    telegram_service = TelegramService()

    text = message.get("text")
    voice = message.get("voice")
    
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
        chat_id=chat_id
    )

    return {"status": "ok"}
