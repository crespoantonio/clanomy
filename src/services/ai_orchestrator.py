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
from src.services.notion_service import NotionService

logger = logging.getLogger(__name__)

class AIOrchestrator:
    def __init__(self):
        self.encryption_service = EncryptionService()

    def _persist_transaction(self, user_uuid: UUID, amount: str, concept: str, category: str) -> UUID:
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
                session.refresh(transaction)
                return transaction.id
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
        if "notion" in text_lower:
            return True
        return bool(words.intersection(special_intent_keywords))

    def _get_user_family_id(self, user_uuid: UUID) -> UUID:
        """Synchronous database helper to fetch family_id."""
        with Session(engine) as session:
            user = session.get(User, user_uuid)
            if not user or not user.family_id:
                raise ValueError("User not associated with a family")
            return user.family_id

    def _get_user_info(self, user_uuid: UUID) -> dict:
        """Synchronous database helper to fetch user info for mirroring."""
        with Session(engine) as session:
            user = session.get(User, user_uuid)
            if not user:
                raise ValueError("User not found")
            return {
                "family_id": user.family_id, 
                "display_name": user.full_name or user.username
            }

    async def _safe_mirror_to_notion(self, family_id: UUID, amount: float, currency: str, concept: str, category: str, timestamp: datetime.datetime, user_name: Optional[str], transaction_id: Optional[UUID] = None):
        """Background task for Notion Mirroring. Fails silently with logs."""
        try:
            with Session(engine) as session:
                notion_service = NotionService(session)
                await notion_service.mirror_transaction(
                    family_id=family_id,
                    amount=amount,
                    currency=currency,
                    concept=concept,
                    category=category,
                    timestamp=timestamp,
                    user_name=user_name,
                    transaction_id=transaction_id
                )
        except Exception as e:
            logger.error(f"[Notion Mirror] Uncaught error in background task: {e}")

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
                    elif parsed_query and parsed_query.intent == "notion_manage":
                        family_id = await asyncio.to_thread(self._get_user_family_id, user_uuid)
                        raw_text = text.strip()
                        raw_lower = raw_text.lower()
                        parts = raw_text.split()
                        
                        with Session(engine) as session:
                            notion_service = NotionService(session)
                            
                            if raw_lower == "/notion" or raw_lower == "connect notion":
                                response_text = (
                                    "🔗 <b>Connect your Notion Workspace</b>\n\n"
                                    "Follow these quick steps:\n"
                                    "1. Go to https://www.notion.so/my-integrations and create an <b>Internal Integration</b>.\n"
                                    "2. Copy the <b>Internal Integration Secret</b> (token).\n"
                                    "3. Open your Notion expenses database, click <b>•••</b> (top right) -> <b>Add connections</b>, and select your integration.\n"
                                    "4. Reply here with:\n"
                                    "   <code>/notion connect &lt;your_secret_token&gt;</code>"
                                )
                            elif raw_lower.startswith("/notion connect") or raw_lower.startswith("notion connect"):
                                if len(parts) < 3:
                                    response_text = "Please provide the secret token. Usage: <code>/notion connect &lt;your_secret_token&gt;</code>"
                                else:
                                    token = parts[2]
                                    db_id = parts[3] if len(parts) > 3 else None
                                    is_valid = await notion_service.validate_token(token)
                                    if not is_valid:
                                        response_text = "⚠️ <b>Invalid Token!</b> Please check your Integration Secret and try again."
                                    elif db_id:
                                        try:
                                            res = await notion_service.connect_database(family_id, token, db_id)
                                            response_text = f"✅ <b>Notion Workspace Connected!</b>\n\n📁 <b>Database:</b> {res['database_name']}\n🆔 <b>ID:</b> <code>{res['database_id']}</code>\n\nYour transactions are now linked and ready for automatic mirroring!"
                                        except Exception as e:
                                            response_text = f"⚠️ <b>Failed to connect database:</b> {e}"
                                    else:
                                        dbs = await notion_service.search_databases(token)
                                        if not dbs:
                                            response_text = (
                                                "⚠️ <b>No databases found!</b>\n"
                                                "Your Notion token is valid, but no databases have been shared with this integration yet.\n\n"
                                                "Please open your Notion database, click <b>•••</b> -> <b>Add connections</b>, select your integration, and run <code>/notion connect &lt;token&gt;</code> again."
                                            )
                                        else:
                                            family = session.get(Family, family_id)
                                            family.notion_api_key = self.encryption_service.encrypt(token)
                                            family.notion_database_id = None
                                            family.notion_database_name = None
                                            session.add(family)
                                            session.commit()
                                            
                                            db_list = "\n".join([f"{i+1}. 📊 <b>{db['title']}</b> (ID: <code>{db['id']}</code>)" for i, db in enumerate(dbs)])
                                            response_text = (
                                                f"📋 <b>Found {len(dbs)} Notion Database(s):</b>\n\n{db_list}\n\n"
                                                "Reply with: <code>/notion setdb &lt;number or ID&gt;</code> (e.g. <code>/notion setdb 1</code>)"
                                            )
                            elif raw_lower.startswith("/notion setdb") or raw_lower.startswith("notion setdb"):
                                if len(parts) < 3:
                                    response_text = "Please provide the database number or ID. Usage: <code>/notion setdb &lt;number or ID&gt;</code>"
                                else:
                                    target = parts[2]
                                    status = notion_service.get_family_notion_status(family_id)
                                    if not status["has_valid_token"]:
                                        response_text = "No Notion token found. Please run <code>/notion connect &lt;token&gt;</code> first."
                                    else:
                                        family = session.get(Family, family_id)
                                        token = self.encryption_service.decrypt(family.notion_api_key)
                                        dbs = await notion_service.search_databases(token)
                                        selected_db = None
                                        if target.isdigit():
                                            idx = int(target) - 1
                                            if 0 <= idx < len(dbs):
                                                selected_db = dbs[idx]
                                        else:
                                            selected_db = next((db for db in dbs if db["id"] == target), None)
                                        
                                        if not selected_db:
                                            response_text = "Database not found."
                                        else:
                                            res = await notion_service.connect_database(family_id, token, selected_db["id"], selected_db["title"])
                                            response_text = f"✅ <b>Notion Workspace Connected!</b>\n\n📁 <b>Database:</b> {res['database_name']}\n🆔 <b>ID:</b> <code>{res['database_id']}</code>\n\nYour transactions are now linked and ready for automatic mirroring!"
                            elif raw_lower == "/notion status" or raw_lower == "notion status":
                                status = notion_service.get_family_notion_status(family_id)
                                if status["is_connected"]:
                                    dt_str = status['connected_at'].strftime('%Y-%m-%d %H:%M UTC') if status.get('connected_at') else "N/A"
                                    response_text = f"📊 <b>Notion Connection Status:</b> Connected ✅\n📁 <b>Target Database:</b> {status['database_name']}\n🆔 <b>Database ID:</b> <code>{status['database_id']}</code>\n📅 <b>Connected:</b> {dt_str}"
                                else:
                                    response_text = "📊 <b>Notion Connection Status:</b> Not Connected ❌"
                            elif raw_lower == "/notion disconnect" or raw_lower == "disconnect notion":
                                notion_service.disconnect_workspace(family_id)
                                response_text = "🔌 <b>Notion Disconnected</b>\nYour Notion workspace connection has been removed. Transaction mirroring is now disabled."
                            elif raw_lower == "/notion test" or raw_lower == "notion test":
                                status = notion_service.get_family_notion_status(family_id)
                                if not status["is_connected"]:
                                    response_text = "⚠️ <b>Notion is not connected.</b>\nPlease run <code>/notion</code> to connect your workspace first."
                                else:
                                    try:
                                        res = await notion_service.test_connection_mirror(family_id)
                                        if res:
                                            response_text = f"✅ <b>Notion Mirror Test Successful!</b>\nCreated test record in database: <b>{res['database_name']}</b>\n🔗 <a href=\"{res['page_url']}\">View in Notion</a>"
                                        else:
                                            response_text = "⚠️ <b>Test Failed:</b> Could not verify connection."
                                    except Exception as e:
                                        response_text = f"⚠️ <b>Test Failed:</b> {e}"
                            elif raw_lower == "/notion sync" or raw_lower == "notion sync":
                                status = notion_service.get_family_notion_status(family_id)
                                if status["is_connected"]:
                                    res = await notion_service.sync_pending_transactions(family_id)
                                    synced = res.get("synced", 0)
                                    failed = res.get("failed", 0)
                                    db_name = status.get("database_name", "Notion")
                                    if synced > 0:
                                        response_text = f"✅ <b>Notion Sync Complete!</b>\nSuccessfully synchronized <b>{synced}</b> pending transaction(s) to <b>{db_name}</b>."
                                        if failed > 0:
                                            response_text += f"\n\n⚠️ Could not sync {failed} transaction(s)."
                                    elif synced == 0 and failed == 0:
                                        response_text = f"✅ <b>Notion Sync is Up to Date!</b>\nAll transactions are already synchronized with your Notion database <b>{db_name}</b>."
                                    elif synced == 0 and failed > 0:
                                        response_text = f"⚠️ <b>Notion Sync Failed:</b> Could not reach Notion API for {failed} transaction(s). The system will retry on your next sync or message."
                                else:
                                    response_text = "⚠️ <b>Notion is not connected.</b>\nPlease run <code>/notion</code> to connect your workspace first."
                            else:
                                response_text = "Unknown Notion command."
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
                            
                            tx_id = await asyncio.to_thread(
                                self._persist_transaction,
                                user_uuid=user_uuid,
                                amount=encrypted_amount,
                                concept=encrypted_concept,
                                category=result.category
                            )
                            
                            # Trigger background notion mirroring safely without affecting transaction response
                            try:
                                user_info = await asyncio.to_thread(self._get_user_info, user_uuid)
                                asyncio.create_task(self._safe_mirror_to_notion(
                                    family_id=user_info["family_id"],
                                    amount=result.amount,
                                    currency=result.currency,
                                    concept=result.concept,
                                    category=result.category,
                                    timestamp=datetime.datetime.now(datetime.timezone.utc),
                                    user_name=user_info["display_name"],
                                    transaction_id=tx_id
                                ))
                            except Exception as mirror_err:
                                logger.warning(f"[Notion Mirror] Failed to dispatch background mirror task: {mirror_err}")
                        except Exception as e:
                            logger.error(f"Persistence failed for user {user_id}. (Exception details omitted for security)")
                            status = "error"
                            response_text = "Failed to save transaction. Please try again later."
                except Exception as e:
                    logger.error(f"Extraction or routing failed for user {user_id}. (Exception details omitted for security)")
                    status = "error"
                    response_text = "I couldn't extract the details from your message. Please make sure to include the amount and what it was for."
            elif not text and status == "success":
                status = "error"
                response_text = "No message or audio was provided."
                
        except Exception as e:
            logger.error(f"Unexpected error in orchestrator for user {user_id}. (Exception details omitted for security)")
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
