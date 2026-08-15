from fastapi import APIRouter, Header, HTTPException, Depends, BackgroundTasks, Request
from pydantic import BaseModel
from typing import Optional, Dict, Any
from src.core.config import settings
from src.services.messaging_service import MessagingService
from src.services.ai_orchestrator import AIOrchestrator
from src.services.telegram_service import TelegramService
from src.db.session import get_session
from sqlmodel import Session
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/telegram", tags=["Telegram Webhook"])

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
    if text == "/start":
        welcome_text = (
            f"Welcome to {settings.PROJECT_NAME}, {from_user.get('first_name') or 'User'}!\n\n"
            "Your account is ready. You can now log your first expense by simply typing it, "
            "for example: '50 for lunch' or '100 for groceries'."
        )
        background_tasks.add_task(telegram_service.send_message, chat_id=chat_id, text=welcome_text)
        return {"status": "ok"}

    # Determine if there is text or audio to process
    audio_file_id = None
    if voice:
        audio_file_id = voice.get("file_id")
        
    if not text and not audio_file_id:
        return {"status": "ok"}

    # Process expense log in background
    orchestrator = AIOrchestrator()
    background_tasks.add_task(
        orchestrator.orchestrate,
        user_id=str(user.id),
        text=text,
        audio_file_id=audio_file_id,
        chat_id=chat_id
    )

    return {"status": "ok"}
