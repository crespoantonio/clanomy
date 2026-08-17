import time
import logging
import httpx
import datetime
import asyncio
from typing import Optional
from uuid import UUID
from sqlmodel import Session
from src.core.config import settings
from src.services.whisper_service import WhisperService
from src.services.extraction_service import ExtractionService
from src.db.session import engine
from src.db.models import User, Transaction
from src.core.encryption import EncryptionService
from src.services.telegram_service import TelegramService
from src.services.query_service import QueryService, ParsedQueryIntent
from src.services.export_service import ExportService
from src.services.account_service import AccountService
from src.services.family_service import FamilyService

logger = logging.getLogger(__name__)

class AIOrchestrator:
    def __init__(self):
        self.encryption_service = EncryptionService()

    def _persist_transaction(self, user_uuid: UUID, amount: str, concept: str, category: str) -> None:
        """
        Synchronous helper to write the transaction to the database.
        Runs inside a separate thread via asyncio.to_thread to keep the event loop unblocked.
        """
        with Session(engine) as session:
            try:
                user = session.get(User, user_uuid)
                if not user:
                    raise ValueError(f"User with id {user_uuid} not found.")
                if not user.family_id:
                    raise ValueError(f"User with id {user_uuid} is not associated with any family.")
                    
                transaction = Transaction(
                    user_id=user_uuid,
                    family_id=user.family_id,
                    amount=amount,
                    concept=concept,
                    category=category,
                    timestamp=datetime.datetime.now(datetime.timezone.utc)
                )
                session.add(transaction)
                session.commit()
            except Exception as e:
                session.rollback()
                raise e

    def _is_special_intent(self, text: str) -> bool:
        """Heuristic to check if text is likely a query, export, or account deletion request."""
        if text.strip() == "CONFIRM DELETE":
            return True
            
        special_intent_keywords = {
            "export", "download", "csv", "json", "backup",
            "how", "what", "spend", "spent", "total", "summary",
            "breakdown", "history", "compare", "report", "chart",
            "graph", "list", "show", "tell", "query",
            "delete", "remove", "erase", "forget", "purge", "confirm delete",
            "family", "invite", "join"
        }
        words = set(text.lower().split())
        # We also check if "confirm delete" or "delete account" is in the text directly
        text_lower = text.lower()
        if "confirm delete" in text_lower or "delete account" in text_lower or "create family" in text_lower or "invite link" in text_lower:
            return True
        if "/familytotal" in text_lower or "family total" in text_lower or "family spending" in text_lower or "our spending" in text_lower or "how much did we spend" in text_lower:
            return True
        return bool(words.intersection(special_intent_keywords))

    def _get_user_family_id(self, user_uuid: UUID) -> UUID:
        """Synchronous database helper to fetch family_id."""
        with Session(engine) as session:
            user = session.get(User, user_uuid)
            if not user or not user.family_id:
                raise ValueError("User not associated with a family")
            return user.family_id

    async def orchestrate(self, user_id: str, text: Optional[str], audio_file_id: Optional[str], chat_id: int):
        start_time = time.time()
        status = "success"
        response_text = ""
        extracted_data = None
        
        try:
            # Parse user_id once and validate UUID format
            try:
                user_uuid = UUID(user_id)
            except ValueError:
                raise ValueError(f"Invalid user_id format: {user_id}")

            # 1. Process Audio if provided
            if audio_file_id:
                try:
                    telegram_service = TelegramService()
                    audio_url = await telegram_service.get_file_url(audio_file_id)
                    if not audio_url:
                        raise ValueError(f"Could not resolve Telegram file_id: {audio_file_id}")
                        
                    whisper_service = WhisperService()
                    text, _ = await whisper_service.transcribe(audio_url=audio_url)
                    if not text:
                        raise ValueError("Transcription returned empty text.")
                except Exception as e:
                    logger.error(f"Transcription failed: {e}")
                    status = "error"
                    response_text = "I couldn't understand the audio. Could you please type it or try again?"
                    
            # 2. Extract Data if we have text and no previous error
            if text and status == "success":
                try:
                    # Apply keyword heuristic bypass to avoid double Ollama calls for simple expense logs
                    if self._is_special_intent(text):
                        raw_text = text.strip()
                        raw_lower = raw_text.lower()
                        if raw_text == "CONFIRM DELETE":
                            # Exact string match shortcut
                            parsed_query = ParsedQueryIntent(intent="delete_account", timeframe="all_time")
                        elif raw_lower.startswith("/createfamily") or raw_lower.startswith("create family"):
                            if raw_lower.startswith("/createfamily"):
                                name = raw_text[13:].strip()
                            else:
                                name = raw_text[13:].strip()
                            parsed_query = ParsedQueryIntent(intent="create_family", family_name=name)
                        elif raw_text == "/invite" or raw_lower in ["invite family member", "generate invite link", "generate invite", "invite to family"]:
                            parsed_query = ParsedQueryIntent(intent="generate_invite")
                        elif raw_text == "/family" or raw_lower in ["my family", "family info", "family members"]:
                            parsed_query = ParsedQueryIntent(intent="family_info")
                        elif raw_lower.startswith("/familytotal"):
                            parts = raw_lower.split()
                            timeframe = "this_month"
                            category = None
                            valid_timeframes = {"this_week", "last_week", "this_month", "last_month", "today", "yesterday", "all_time"}
                            for part in parts[1:]:
                                if part in valid_timeframes:
                                    timeframe = part
                                elif category is None:
                                    category = part
                            parsed_query = ParsedQueryIntent(intent="spending_summary", timeframe=timeframe, category=category, scope="family")
                        else:
                            query_service = QueryService()
                            parsed_query = await query_service.parse_intent(text)
                    else:
                        parsed_query = None
                    
                    if parsed_query and getattr(parsed_query, "intent", None) == "delete_account" and text.strip() == "CONFIRM DELETE":
                        account_service = AccountService()
                        success = await account_service.delete_account(user_uuid)
                        if success:
                            response_text = "✅ Your account and all associated transaction records have been permanently deleted from our database. Thank you for using FamFin-AI! If you ever wish to return, simply send /start."
                        else:
                            response_text = "Failed to delete account. Please try again later."
                    elif parsed_query and getattr(parsed_query, "intent", None) == "delete_account":
                        response_text = "⚠️ Are you sure you want to permanently delete your account and all associated financial records? This action is irreversible.\n\nTo confirm, please reply with: <b>CONFIRM DELETE</b>"
                    elif parsed_query and parsed_query.intent == "export_data":
                        # Handle Export
                        family_id = await asyncio.to_thread(self._get_user_family_id, user_uuid)
                        export_format = parsed_query.export_format or "csv"
                        export_service = ExportService()
                        await export_service.export_and_send(family_id, chat_id, export_format)
                        # We don't need to send a regular message since we sent a document
                        return {"status": "ok"}
                    elif parsed_query and parsed_query.intent == "spending_summary":
                        family_service = FamilyService()
                        family_info = await asyncio.to_thread(family_service.get_family_info, user_uuid)
                        family_id = family_info["id"]
                        
                        family_name = family_info["name"] if parsed_query.scope == "family" else None
                        member_names = [m.get("full_name") or m.get("username") or "User" for m in family_info["members"]] if parsed_query.scope == "family" else None
                        
                        user_name = None
                        reference_time = datetime.datetime.now(datetime.timezone.utc)
                        query_service = QueryService()
                        summary = await query_service.get_spending_summary(
                            family_id=family_id,
                            timeframe=parsed_query.timeframe,
                            category=parsed_query.category,
                            user_name=user_name,
                            reference_time=reference_time,
                            family_name=family_name,
                            member_names=member_names
                        )
                        response_text = summary
                    elif parsed_query and parsed_query.intent == "create_family":
                        family_service = FamilyService()
                        name = parsed_query.family_name or "My Family"
                        await asyncio.to_thread(family_service.create_family, user_uuid, name)
                        response_text = f"✅ Family group '{name}' has been created! To invite others, just ask me to 'generate an invite link'."
                    elif parsed_query and parsed_query.intent == "generate_invite":
                        family_service = FamilyService()
                        family_id = await asyncio.to_thread(self._get_user_family_id, user_uuid)
                        # Fetch bot username dynamically
                        telegram_service = TelegramService()
                        bot_username = await telegram_service.get_bot_username()
                        invite, link = await asyncio.to_thread(family_service.create_invite, family_id, user_uuid, bot_username)
                        response_text = f"🔗 Here is your family invite link:\n\n{link}\n\n⏳ This invite link will expire in 48 hours."
                    elif parsed_query and parsed_query.intent == "family_info":
                        family_service = FamilyService()
                        info = await asyncio.to_thread(family_service.get_family_info, user_uuid)
                        members = ", ".join([m.get("full_name") or m.get("username") or "User" for m in info["members"]])
                        response_text = f"👪 <b>Family Info: {info['name']}</b>\nMembers: {members}\nTransactions: {info['transactions_count']}\nActive Invites: {info['active_invites_count']}"
                    else:
                        # Default: log expense
                        extraction_service = ExtractionService()
                        result = await extraction_service.extract(text=text)
                        extracted_data = result.model_dump()
                        
                        # Construct success message
                        response_text = f"Saved {result.amount} {result.currency} for '{result.concept}' under category '{result.category}'."
                        
                        try:
                            # Persist Transaction
                            encrypted_amount = self.encryption_service.encrypt(f"{result.amount} {result.currency}")
                            encrypted_concept = self.encryption_service.encrypt(result.concept)
                            
                            await asyncio.to_thread(
                                self._persist_transaction,
                                user_uuid=user_uuid,
                                amount=encrypted_amount,
                                concept=encrypted_concept,
                                category=result.category
                            )
                        except Exception as e:
                            logger.error(f"Persistence failed: {e}")
                            status = "error"
                            response_text = "Failed to save transaction. Please try again later."
                except Exception as e:
                    logger.error(f"Extraction or routing failed: {e}")
                    status = "error"
                    response_text = "I couldn't extract the details from your message. Please make sure to include the amount and what it was for."
            elif not text and status == "success":
                status = "error"
                response_text = "No message or audio was provided."
                
        except Exception as e:
            logger.error(f"Unexpected error in orchestrator: {e}")
            status = "error"
            response_text = "An unexpected error occurred while processing your request."
            
        # 3. Direct Reply via Telegram API
        try:
            telegram_service = TelegramService()
            await telegram_service.send_message(chat_id=chat_id, text=response_text)
        except Exception as e:
            logger.error(f"Failed to send direct reply to Telegram: {e}")
            
        # 4. Log 3s Audit
        duration = time.time() - start_time
        logger.info(f"[3s Audit] Total pipeline orchestration took {duration:.2f} seconds (user_id: {user_id}, text: '{text}')")
