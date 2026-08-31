import time
import logging
import httpx
import datetime
import asyncio
import re
from typing import Optional
from uuid import UUID
from sqlmodel import Session, select
from sqlalchemy import update as sa_update
from src.core.config import settings
from src.services.whisper_service import WhisperService
from src.services.extraction_service import ExtractionService
from src.db.session import engine
from src.db.models import User, Transaction, Family
from src.core.encryption import EncryptionService
from src.services.telegram_service import TelegramService
from src.services.query_service import QueryService, ParsedQueryIntent
from src.services.export_service import ExportService
from src.services.account_service import AccountService
from src.services.family_service import FamilyService, PlanLimitExceededError
from src.services.notion_service import NotionService

logger = logging.getLogger(__name__)

def create_logged_task(coro, *, name: Optional[str] = None) -> asyncio.Task:
    """
    Creates an asyncio task with an attached done callback to log any unhandled exceptions.
    Prevents silent failure of fire-and-forget background coroutines.
    """
    try:
        task = asyncio.create_task(coro, name=name) if name else asyncio.create_task(coro)
    except TypeError:
        task = asyncio.create_task(coro)

    def _handle_task_result(t: asyncio.Task):
        if t.cancelled():
            return
        exc = t.exception()
        if exc:
            task_name = getattr(t, "get_name", lambda: "unnamed_task")()
            logger.error(f"Unhandled exception in background task '{task_name}': {exc}", exc_info=exc)
    task.add_done_callback(_handle_task_result)
    return task

def _format_currency(amount: float, currency: str = "USD", show_sign: bool = False) -> str:
    curr_upper = (currency or settings.DEFAULT_CURRENCY or "USD").upper()
    symbols = {
        "USD": "$",
        "EUR": "€",
        "GBP": "£",
        "ARS": "$",
        "MXN": "$",
        "CLP": "$",
        "COP": "$",
        "UYU": "$",
        "BRL": "R$",
        "PEN": "S/"
    }
    sym = symbols.get(curr_upper, "")
    sign = "-" if (amount or 0.0) < 0 else ("+" if show_sign and (amount or 0.0) > 0 else "")
    abs_amt = abs(amount or 0.0)
    return f"{sign}{sym}{abs_amt:,.2f} {curr_upper}".strip()

class AIOrchestrator:
    def __init__(self):
        self.encryption_service = EncryptionService()

    def _persist_transaction(
        self,
        user_uuid: UUID,
        amount: str,
        concept: str,
        category: str,
        timestamp: Optional[datetime.datetime] = None,
        tx_type: str = "expense"
    ) -> UUID:
        """
        Synchronous helper to write the transaction to the database.
        :param tx_type: Type of transaction (expense/income)
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
                    tx_type=tx_type,
                    timestamp=timestamp or datetime.datetime.now(datetime.timezone.utc)
                )
                session.add(transaction)

                # Atomic SQL increment to avoid race conditions under concurrency
                session.execute(
                    sa_update(Family)
                    .where(Family.id == user.family_id)
                    .values(monthly_tx_count=Family.monthly_tx_count + 1)
                )

                session.commit()
                session.refresh(transaction)
                return transaction.id
            except Exception as e:
                session.rollback()
                raise e

    def _get_monthly_cash_flow_snapshot(self, family_id: UUID, target_date: datetime.datetime, primary_currency: str = "USD") -> dict:
        """
        Queries and decrypts all transactions for the given family in the calendar month of target_date.
        Calculates Total In, Total Out, Net Savings, and Savings Rate percentage.
        """
        start_of_month = target_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if target_date.month == 12:
            next_month = target_date.replace(year=target_date.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            next_month = target_date.replace(month=target_date.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)
        end_of_month = next_month - datetime.timedelta(microseconds=1)

        with Session(engine) as session:
            statement = select(Transaction).where(
                Transaction.family_id == family_id,
                Transaction.timestamp >= start_of_month,
                Transaction.timestamp < next_month
            )
            transactions = session.exec(statement).all()

            total_in = 0.0
            total_out = 0.0

            for tx in transactions:
                try:
                    decrypted_amount_str = self.encryption_service.decrypt(tx.amount)
                    if not decrypted_amount_str:
                        continue
                    parts = decrypted_amount_str.strip().split()
                    amt = float(parts[0]) if parts else 0.0
                    curr = parts[1].upper() if len(parts) > 1 else "USD"
                    
                    if curr == primary_currency.upper():
                        tx_type = getattr(tx, "tx_type", "expense") or "expense"
                        if tx_type == "income":
                            total_in += amt
                        else:
                            total_out += amt
                except Exception as e:
                    logger.warning(f"Failed to decrypt transaction {tx.id} for cash flow snapshot: {e}")

            net_savings = total_in - total_out
            savings_pct = round((net_savings / total_in) * 100) if total_in > 0 else 0

            return {
                "month_name": target_date.strftime("%B"),
                "total_in": round(total_in, 2),
                "total_out": round(total_out, 2),
                "net_savings": round(net_savings, 2),
                "savings_pct": savings_pct,
                "currency": primary_currency
            }

    def _is_special_intent(self, text: str) -> bool:
        """
        Determines whether the incoming text should be routed to the QueryService / command parser
        instead of the standard transaction logging flow.
        """
        if not text:
            return False
            
        text_clean = text.strip()
        if text_clean.startswith("/"):
            return True
            
        special_intent_keywords = {
            "export", "download", "csv", "json", "backup",
            "how", "what", "spend", "spent", "total", "summary",
            "breakdown", "history", "compare", "report", "chart",
            "graph", "list", "show", "tell", "query",
            "delete", "remove", "erase", "forget", "purge", "confirm delete",
            "family", "invite", "join",
            "earn", "earned", "earning", "earnings", "income", "salary",
            "bonus", "freelance", "net", "cashflow", "cash flow", "balance",
            "leftover", "left over", "surplus", "deficit", "saved", "savings", "profit",
            "undo", "change", "edit", "correct", "fix",
            "currency", "moneda"
        }
        words = set(text.lower().split())
        text_lower = text.lower()
        if "/currency" in text_lower or "currency" in text_lower or "moneda" in text_lower or "cambiar moneda" in text_lower or "set currency" in text_lower:
            return True
        if "confirm delete" in text_lower or "delete account" in text_lower or "create family" in text_lower or "/createfamily" in text_lower or "invite" in text_lower or "/join_" in text_lower:
            return True
        if "/leavefamily" in text_lower or "leave family" in text_lower or "/removemember" in text_lower or "remove member" in text_lower:
            return True
        if "/familytotal" in text_lower or "family total" in text_lower or "family spending" in text_lower or "our spending" in text_lower or "how much did we spend" in text_lower:
            return True
        if "net balance" in text_lower or "cash flow" in text_lower or "net savings" in text_lower or "how much did we earn" in text_lower or "how much did i earn" in text_lower or "how much did we make" in text_lower or "how much did i make" in text_lower:
            return True
        if "notion" in text_lower or "undo" in text_lower or "change" in text_lower or "delete last" in text_lower or "remove last" in text_lower:
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

    def _get_latest_transaction(self, user_uuid: UUID) -> Optional[Transaction]:
        """Synchronous database helper to fetch the user's most recent transaction."""
        with Session(engine) as session:
            statement = (
                select(Transaction)
                .where(Transaction.user_id == user_uuid)
                .order_by(Transaction.timestamp.desc())
                .limit(1)
            )
            return session.exec(statement).first()

    def _handle_transaction_undo(self, user_uuid: UUID) -> str:
        """Removes the latest transaction logged by the user, recalculating monthly balance."""
        with Session(engine) as session:
            statement = (
                select(Transaction)
                .where(Transaction.user_id == user_uuid)
                .order_by(Transaction.timestamp.desc())
                .limit(1)
            )
            tx = session.exec(statement).first()
            if not tx:
                return "ℹ️ You don't have any recent transactions to undo."

            dec_amount = self.encryption_service.decrypt(tx.amount) or "0.00 USD"
            dec_concept = self.encryption_service.decrypt(tx.concept) or "Transaction"
            parts = dec_amount.strip().split()
            amt = float(parts[0]) if parts else 0.0
            curr = parts[1].upper() if len(parts) > 1 else "USD"
            old_type = getattr(tx, "tx_type", getattr(tx, "type", "expense")) or "expense"
            category = tx.category
            notion_page_id = tx.notion_page_id
            family_id = tx.family_id
            tx_time = tx.timestamp

            session.delete(tx)
            session.commit()

        if notion_page_id:
            try:
                create_logged_task(self._safe_archive_notion_page(family_id, notion_page_id), name="archive_notion_page")
            except Exception as e:
                logger.warning(f"Could not dispatch Notion archive task: {e}")

        snapshot = self._get_monthly_cash_flow_snapshot(family_id, tx_time, curr)

        icon = "💰" if old_type == "income" else "💸"
        sign = "+" if old_type == "income" else "-"
        formatted_amt = _format_currency(amt, curr, show_sign=False)
        formatted_in = _format_currency(snapshot["total_in"], curr, show_sign=False)
        formatted_out = _format_currency(snapshot["total_out"], curr, show_sign=False)
        formatted_net = _format_currency(snapshot["net_savings"], curr, show_sign=True)
        pct_str = f" ({snapshot['savings_pct']}%)" if snapshot["total_in"] > 0 else ""

        return (
            f"🗑️ <b>Removed latest transaction:</b>\n"
            f"• {icon} {sign}{formatted_amt} ({category} - {dec_concept})\n\n"
            f"📊 <b>Updated {snapshot['month_name']} Balance:</b>\n"
            f"• Total In: {formatted_in}\n"
            f"• Total Out: {formatted_out}\n"
            f"• Net Savings: {formatted_net}{pct_str}"
        )

    def _handle_transaction_correction(self, user_uuid: UUID, parsed_query: ParsedQueryIntent) -> str:
        """Modifies fields on the user's latest transaction and updates Notion / cash flow snapshot."""
        with Session(engine) as session:
            statement = (
                select(Transaction)
                .where(Transaction.user_id == user_uuid)
                .order_by(Transaction.timestamp.desc())
                .limit(1)
            )
            tx = session.exec(statement).first()
            if not tx:
                return "ℹ️ You don't have any recent transactions to update."

            dec_amount = self.encryption_service.decrypt(tx.amount) or "0.00 USD"
            dec_concept = self.encryption_service.decrypt(tx.concept) or "Transaction"
            parts = dec_amount.strip().split()
            current_amt = float(parts[0]) if parts else 0.0
            current_curr = parts[1].upper() if len(parts) > 1 else "USD"
            current_type = getattr(tx, "tx_type", getattr(tx, "type", "expense")) or "expense"
            current_cat = tx.category

            new_type = parsed_query.new_type or current_type
            new_amt = parsed_query.new_amount if parsed_query.new_amount is not None else current_amt
            new_curr = (parsed_query.new_currency.upper() if parsed_query.new_currency else current_curr)
            new_cat = parsed_query.new_category or current_cat
            new_concept = parsed_query.new_concept or dec_concept

            tx.type = new_type
            if hasattr(tx, "tx_type"):
                tx.tx_type = new_type
            tx.category = new_cat
            tx.amount = self.encryption_service.encrypt(f"{new_amt:.2f} {new_curr}")
            tx.concept = self.encryption_service.encrypt(new_concept)

            session.add(tx)
            session.commit()
            session.refresh(tx)

            notion_page_id = tx.notion_page_id
            family_id = tx.family_id
            tx_time = tx.timestamp

        if notion_page_id:
            try:
                user_info = self._get_user_info(user_uuid)
                create_logged_task(self._safe_update_notion_page(
                    family_id=family_id,
                    page_id=notion_page_id,
                    amount=new_amt,
                    currency=new_curr,
                    concept=new_concept,
                    category=new_cat,
                    timestamp=tx_time,
                    user_name=user_info.get("display_name"),
                    tx_type=new_type
                ), name="update_notion_page")
            except Exception as e:
                logger.warning(f"Could not dispatch Notion update task: {e}")

        snapshot = self._get_monthly_cash_flow_snapshot(family_id, tx_time, new_curr)

        type_note = ""
        if current_type != new_type:
            old_label = "Expense 💸" if current_type == "expense" else "Income 💰"
            new_label = "Income 💰" if new_type == "income" else "Expense 💸"
            type_note = f"\n<i>[Switched from {old_label} to {new_label}]</i>"

        icon = "💰" if new_type == "income" else "💸"
        sign = "+" if new_type == "income" else "-"
        formatted_amt = _format_currency(new_amt, new_curr, show_sign=False)
        formatted_in = _format_currency(snapshot["total_in"], new_curr, show_sign=False)
        formatted_out = _format_currency(snapshot["total_out"], new_curr, show_sign=False)
        formatted_net = _format_currency(snapshot["net_savings"], new_curr, show_sign=True)
        pct_str = f" ({snapshot['savings_pct']}%)" if snapshot["total_in"] > 0 else ""

        return (
            f"✏️ <b>Updated latest transaction:</b>\n"
            f"• {icon} {sign}{formatted_amt} ({new_cat} - {new_concept}){type_note}\n\n"
            f"📊 <b>Updated {snapshot['month_name']} Balance:</b>\n"
            f"• Total In: {formatted_in}\n"
            f"• Total Out: {formatted_out}\n"
            f"• Net Savings: {formatted_net}{pct_str}"
        )

    async def _safe_mirror_to_notion(self, family_id: UUID, amount: float, currency: str, concept: str, category: str, timestamp: datetime.datetime, user_name: Optional[str], transaction_id: Optional[UUID] = None, tx_type: str = "expense"):
        """Background task for Notion Mirroring. Fails silently with logs."""
        try:
            with Session(engine) as session:
                family = session.get(Family, family_id)
                from src.services.subscription_service import has_unlimited_access
                if family and not has_unlimited_access(family):
                    return
                notion_service = NotionService(session)
                await notion_service.mirror_transaction(
                    family_id=family_id,
                    amount=amount,
                    currency=currency,
                    concept=concept,
                    category=category,
                    timestamp=timestamp,
                    user_name=user_name,
                    transaction_id=transaction_id,
                    tx_type=tx_type
                )
        except Exception as e:
            logger.error(f"[Notion Mirror] Uncaught error in background task: {e}")

    async def _safe_update_notion_page(self, family_id: UUID, page_id: str, amount: float, currency: str, concept: str, category: str, timestamp: datetime.datetime, user_name: Optional[str] = None, tx_type: str = "expense"):
        """Background task for Notion Page Update. Fails silently with logs."""
        try:
            with Session(engine) as session:
                notion_service = NotionService(session)
                await notion_service.update_transaction_page(
                    family_id=family_id,
                    page_id=page_id,
                    amount=amount,
                    currency=currency,
                    concept=concept,
                    category=category,
                    timestamp=timestamp,
                    user_name=user_name,
                    tx_type=tx_type
                )
        except Exception as e:
            logger.error(f"[Notion Mirror] Uncaught error in update background task: {e}")

    async def _safe_archive_notion_page(self, family_id: UUID, page_id: str):
        """Background task for Notion Page Archival. Fails silently with logs."""
        try:
            with Session(engine) as session:
                notion_service = NotionService(session)
                await notion_service.archive_transaction_page(family_id=family_id, page_id=page_id)
        except Exception as e:
            logger.error(f"[Notion Mirror] Uncaught error in archive background task: {e}")

    async def orchestrate(self, user_id: str, text: Optional[str], audio_file_id: Optional[str], chat_id: int, message_id: Optional[int] = None):
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
                        elif raw_lower in ["/undo", "undo", "undo last", "undo latest", "delete last", "delete the last", "delete last log", "delete the last log", "delete last transaction", "delete the last transaction", "remove last log", "remove the last log", "remove last transaction", "remove the last transaction", "delete last expense", "delete last income"]:
                            parsed_query = ParsedQueryIntent(intent="undo_last")
                        elif re.match(r"^change (the )?(last|latest)? ?(one|log|transaction)? ?to income$", raw_lower) or raw_lower in ["change to income", "make it income", "it was income", "switch to income"]:
                            parsed_query = ParsedQueryIntent(intent="edit_last", new_type="income", new_category="Salary")
                        elif re.match(r"^change (the )?(last|latest)? ?(one|log|transaction)? ?to expense$", raw_lower) or raw_lower in ["change to expense", "make it expense", "it was expense", "switch to expense"]:
                            parsed_query = ParsedQueryIntent(intent="edit_last", new_type="expense", new_category="Other")
                        elif m := re.match(r"^change (the )?(last|latest)? ?amount to (\d+(?:[.,]\d{1,2})?)\s*([a-zA-Z$€£]*)$", raw_lower):
                            amt_val = float(m.group(3).replace(",", "."))
                            curr_raw = m.group(4).strip()
                            curr_map = {"$": "USD", "€": "EUR", "£": "GBP", "usd": "USD", "eur": "EUR", "gbp": "GBP", "dollars": "USD", "euros": "EUR", "pounds": "GBP"}
                            curr_val = curr_map.get(curr_raw.lower(), curr_raw.upper() if len(curr_raw) == 3 else None)
                            parsed_query = ParsedQueryIntent(intent="edit_last", new_amount=amt_val, new_currency=curr_val)
                        elif m := re.match(r"^change (the )?(last|latest)? ?category to (.+)$", raw_lower):
                            cat_val = m.group(3).strip()
                            parsed_query = ParsedQueryIntent(intent="edit_last", new_category=cat_val)
                        elif m := re.match(r"^change (the )?(last|latest)? ?concept to (.+)$", raw_lower):
                            concept_val = m.group(3).strip()
                            parsed_query = ParsedQueryIntent(intent="edit_last", new_concept=concept_val)
                        elif raw_lower.startswith("/createfamily") or raw_lower.startswith("create family"):
                            if raw_lower.startswith("/createfamily"):
                                name = raw_text[13:].strip()
                            else:
                                name = raw_text[13:].strip()
                            parsed_query = ParsedQueryIntent(intent="create_family", family_name=name)
                        elif raw_text == "/leavefamily" or raw_lower in ["leave family", "leave the family", "leave group"]:
                            parsed_query = ParsedQueryIntent(intent="leave_family")
                        elif raw_lower.startswith("/removemember") or raw_lower.startswith("remove member"):
                            if raw_lower.startswith("/removemember"):
                                target = raw_text[13:].strip()
                            else:
                                target = raw_text[13:].strip()
                            parsed_query = ParsedQueryIntent(intent="remove_member", target_member=target)
                        elif raw_text == "/invite" or raw_lower in ["invite", "invite link", "invite family member", "generate invite link", "generate invite", "invite to family"]:
                            parsed_query = ParsedQueryIntent(intent="generate_invite")
                        elif raw_text == "/family" or raw_lower in ["my family", "family info", "family members"]:
                            parsed_query = ParsedQueryIntent(intent="family_info")
                        elif raw_lower.startswith("/currency") or raw_lower == "currency" or raw_lower.startswith("currency ") or raw_lower.startswith("cambiar moneda") or raw_lower.startswith("set currency") or raw_lower.startswith("mi moneda es"):
                            parsed_query = ParsedQueryIntent(intent="manage_currency")
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
                            response_text = "✅ Your account and all associated transaction records have been permanently deleted from our database. Thank you for using Clanomy! If you ever wish to return, simply send /start."
                        else:
                            response_text = "Failed to delete account. Please try again later."
                    elif parsed_query and getattr(parsed_query, "intent", None) == "delete_account":
                        response_text = "⚠️ Are you sure you want to permanently delete your account and all associated financial records? This action is irreversible.\n\nTo confirm, please reply with: <b>CONFIRM DELETE</b>"
                    elif parsed_query and parsed_query.intent == "export_data":
                        # Handle Export
                        family_id = await asyncio.to_thread(self._get_user_family_id, user_uuid)
                        ALLOWED_EXPORT_FORMATS = {"csv", "json"}
                        raw_format = (parsed_query.export_format or "csv").lower()
                        export_format = raw_format if raw_format in ALLOWED_EXPORT_FORMATS else "csv"
                        export_service = ExportService()
                        await export_service.export_and_send(family_id, chat_id, export_format)
                        # We don't need to send a regular message since we sent a document
                        return {"status": "ok"}
                    elif parsed_query and parsed_query.intent == "undo_last":
                        response_text = await asyncio.to_thread(self._handle_transaction_undo, user_uuid)
                    elif parsed_query and parsed_query.intent == "edit_last":
                        response_text = await asyncio.to_thread(self._handle_transaction_correction, user_uuid, parsed_query)
                    elif parsed_query and parsed_query.intent == "leave_family":
                        family_service = FamilyService()
                        success, msg, _ = await asyncio.to_thread(family_service.leave_family, user_uuid)
                        response_text = msg
                    elif parsed_query and parsed_query.intent == "remove_member":
                        family_service = FamilyService()
                        target = parsed_query.target_member or ""
                        success, msg, removed_user, _ = await asyncio.to_thread(family_service.remove_member, user_uuid, target)
                        if success and removed_user and removed_user.telegram_id:
                            telegram_service = TelegramService()
                            create_logged_task(
                                telegram_service.send_message(
                                    chat_id=removed_user.telegram_id,
                                    text="ℹ️ You have been removed from the family workspace by the admin. A new personal workspace has been created for you with all your personal transaction history intact."
                                ),
                                name="notify_removed_member"
                            )
                        response_text = msg
                    elif parsed_query and parsed_query.intent in ["spending_summary", "query_spending", "income_summary", "query_income", "earnings_summary", "net_cash_flow", "net_balance", "cash_flow_summary"]:
                        family_service = FamilyService()
                        family_info = await asyncio.to_thread(family_service.get_family_info, user_uuid)
                        family_id = family_info["id"]
                        
                        family_name = family_info["name"] if parsed_query.scope == "family" else None
                        member_names = [m.get("full_name") or m.get("username") or "User" for m in family_info["members"]] if parsed_query.scope == "family" else None
                        
                        user_name = None
                        reference_time = datetime.datetime.now(datetime.timezone.utc)
                        query_service = QueryService()

                        if parsed_query.intent in ["income_summary", "query_income", "earnings_summary"]:
                            summary = await query_service.get_income_summary(
                                family_id=family_id,
                                timeframe=parsed_query.timeframe,
                                category=parsed_query.category,
                                user_name=user_name,
                                reference_time=reference_time,
                                family_name=family_name,
                                member_names=member_names
                            )
                        elif parsed_query.intent in ["net_cash_flow", "net_balance", "cash_flow_summary"]:
                            summary = await query_service.get_net_cash_flow_summary(
                                family_id=family_id,
                                timeframe=parsed_query.timeframe,
                                user_name=user_name,
                                reference_time=reference_time,
                                family_name=family_name,
                                member_names=member_names
                            )
                        else:
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
                        try:
                            invite, link = await asyncio.to_thread(family_service.create_invite, family_id, user_uuid, bot_username)
                            response_text = f"🔗 Here is your family invite link:\n\n{link}\n\n⏳ This invite link will expire in 48 hours."
                        except PlanLimitExceededError:
                            response_text = (
                                "⚠️ <b>Family Invites Require Family Pro</b>\n\n"
                                "Your workspace is currently on the <b>Solo Pro</b> tier (1 user limit). "
                                "To add family members and share a household ledger, please upgrade to <b>Family Pro</b> using /upgrade."
                            )
                        except ValueError as ve:
                            response_text = f"⚠️ {ve}"


                    elif parsed_query and parsed_query.intent == "family_info":
                        family_service = FamilyService()
                        info = await asyncio.to_thread(family_service.get_family_info, user_uuid)
                        members_str = []
                        for m in info["members"]:
                            name = m.get("full_name") or m.get("username") or "User"
                            handle = f" (@{m['username']})" if m.get("username") else ""
                            role = " 👑 (Admin)" if m.get("is_admin") else ""
                            members_str.append(f"• {name}{handle}{role}")
                        members_formatted = "\n".join(members_str)
                        plan_desc = info.get("plan_type", "free").replace("_", " ").title()
                        response_text = (
                            f"👪 <b>Family Workspace: {info['name']}</b>\n"
                            f"📋 <b>Plan:</b> {plan_desc}\n"
                            f"📊 <b>Monthly Logs:</b> {info.get('monthly_tx_count', 0)}\n\n"
                            f"<b>Members:</b>\n{members_formatted}\n\n"
                            f"<b>Total Transactions:</b> {info['transactions_count']}\n"
                            f"<b>Active Invites:</b> {info['active_invites_count']}"
                        )
                    elif parsed_query and parsed_query.intent == "notion_manage":
                        family_id = await asyncio.to_thread(self._get_user_family_id, user_uuid)
                        raw_text = text.strip()
                        raw_lower = raw_text.lower()
                        parts = raw_text.split()
                        
                        with Session(engine) as session:
                            family = session.get(Family, family_id)
                            notion_service = NotionService(session)
                            from src.services.subscription_service import has_unlimited_access
                            if family and not has_unlimited_access(family):
                                response_text = (
                                    "⭐️ <b>Notion Mirroring is a Pro Feature</b>\n\n"
                                    "Real-time Notion database synchronization is available on <b>Solo Pro</b> and <b>Family Pro</b> plans.\n\n"
                                    "Type /upgrade to connect your Notion database."
                                )
                            elif raw_lower == "/notion" or raw_lower == "connect notion":
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
                                    
                                    # Auto-delete message containing the secret token for security
                                    if message_id:
                                        ts = TelegramService()
                                        create_logged_task(ts.delete_message(chat_id, message_id), name="delete_secret_token_message")

                                    is_valid = await notion_service.validate_token(token)
                                    if not is_valid:
                                        response_text = "⚠️ <b>Invalid Token!</b> Please check your Integration Secret and try again.\n\n🔒 <i>Your secret token message was automatically deleted for security.</i>"
                                    elif db_id:
                                        try:
                                            res = await notion_service.connect_database(family_id, token, db_id)
                                            response_text = f"✅ <b>Notion Workspace Connected!</b>\n\n📁 <b>Database:</b> {res['database_name']}\n🆔 <b>ID:</b> <code>{res['database_id']}</code>\n\nYour transactions are now linked and ready for automatic mirroring!\n\n🔒 <i>Your secret token message was automatically deleted for security.</i>"
                                        except Exception as e:
                                            logger.error(f"Failed to connect database: {e}")
                                            response_text = "⚠️ <b>Failed to connect database.</b> Please verify the database ID and try again.\n\n🔒 <i>Your secret token message was automatically deleted for security.</i>"
                                    else:
                                        dbs = await notion_service.search_databases(token)
                                        if not dbs:
                                            response_text = (
                                                "⚠️ <b>No databases found!</b>\n"
                                                "Your Notion token is valid, but no databases have been shared with this integration yet.\n\n"
                                                "Please open your Notion database, click <b>•••</b> -> <b>Add connections</b>, select your integration, and run <code>/notion connect &lt;token&gt;</code> again.\n\n"
                                                "🔒 <i>Your secret token message was automatically deleted for security.</i>"
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
                                                "Reply with: <code>/notion setdb &lt;number or ID&gt;</code> (e.g. <code>/notion setdb 1</code>)\n\n"
                                                "🔒 <i>Your secret token message was automatically deleted for security.</i>"
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
                    elif parsed_query and parsed_query.intent == "manage_currency":
                        family_id = await asyncio.to_thread(self._get_user_family_id, user_uuid)
                        family_service = FamilyService()
                        parts = text.strip().split()
                        
                        target_curr = None
                        if len(parts) >= 2 and parts[1].lower() not in ["help", "info", "a", "to", "es"]:
                            target_curr = parts[-1].strip().upper()
                        elif len(parts) >= 3 and parts[1].lower() in ["a", "to", "es"]:
                            target_curr = parts[2].strip().upper()
                        elif len(parts) == 1 and parts[0].startswith("/currency") and len(parts[0]) > 9:
                            target_curr = parts[0][9:].strip().upper()
                            
                        if target_curr:
                            try:
                                new_curr = await asyncio.to_thread(family_service.set_family_default_currency, family_id, target_curr)
                                response_text = (
                                    f"✅ <b>Default Currency Updated to {new_curr}!</b>\n\n"
                                    f"Any future expenses or income logged without specifying a currency (e.g. <i>\"spent 500 on lunch\"</i> or <i>\"300 pesos\"</i>) "
                                    f"will now automatically default to <b>{new_curr}</b>."
                                )
                            except ValueError as ve:
                                response_text = f"⚠️ {ve}"
                        else:
                            curr = await asyncio.to_thread(family_service.get_family_default_currency, family_id)
                            response_text = (
                                f"💵 <b>Household Default Currency:</b> <code>{curr}</code>\n\n"
                                "To update your household default currency, reply with:\n"
                                "• <code>/currency USD</code> (US Dollar)\n"
                                "• <code>/currency ARS</code> (Argentine Peso)\n"
                                "• <code>/currency MXN</code> (Mexican Peso)\n"
                                "• <code>/currency EUR</code> (Euro)\n"
                                "• <code>/currency CLP</code> (Chilean Peso)\n"
                                "• <code>/currency COP</code> (Colombian Peso)\n"
                                "• <code>/currency &lt;ISO_CODE&gt;</code> (Any 3-letter currency)"
                            )
                    else:
                        # Default: log expense or income
                        family_id = await asyncio.to_thread(self._get_user_family_id, user_uuid)
                        family_service = FamilyService()
                        family_currency = await asyncio.to_thread(family_service.get_family_default_currency, family_id)

                        extraction_service = ExtractionService()
                        result = await extraction_service.extract(text=text, default_currency=family_currency)
                        extracted_data = result.model_dump()
                        
                        transaction_time = result.to_datetime()
                        
                        try:
                            # Persist Transaction
                            encrypted_amount = self.encryption_service.encrypt(f"{result.amount} {result.currency}")
                            encrypted_concept = self.encryption_service.encrypt(result.concept)
                            
                            tx_id = await asyncio.to_thread(
                                self._persist_transaction,
                                user_uuid=user_uuid,
                                amount=encrypted_amount,
                                concept=encrypted_concept,
                                category=result.category,
                                timestamp=transaction_time,
                                tx_type=result.type
                            )
                            
                            try:
                                user_info = await asyncio.to_thread(self._get_user_info, user_uuid)
                                family_id = user_info["family_id"]
                            except Exception as u_err:
                                logger.warning(f"Failed to get user info: {u_err}")
                                family_id = await asyncio.to_thread(self._get_user_family_id, user_uuid)
                                user_info = {"display_name": "User"}

                            # Construct response message based on transaction type
                            date_str = ""
                            if getattr(result, "transaction_date", None):
                                date_str = f" (logged for {transaction_time.strftime('%b %d, %Y')})"
                            if result.type == "income":
                                snapshot = await asyncio.to_thread(
                                    self._get_monthly_cash_flow_snapshot,
                                    family_id=family_id,
                                    target_date=transaction_time,
                                    primary_currency=result.currency
                                )
                                
                                if (result.concept or "").strip().lower() == (result.category or "").strip().lower():
                                    concept_detail = f"({result.category})"
                                else:
                                    concept_detail = f"({result.category} - {result.concept})"
                                    
                                
                                    
                                formatted_amt = _format_currency(result.amount, result.currency, show_sign=True)
                                formatted_in = _format_currency(snapshot["total_in"], result.currency, show_sign=False)
                                formatted_out = _format_currency(snapshot["total_out"], result.currency, show_sign=False)
                                formatted_net = _format_currency(snapshot["net_savings"], result.currency, show_sign=True)
                                pct_str = f" ({snapshot['savings_pct']}%)" if snapshot["total_in"] > 0 else ""
                                
                                response_text = (
                                    f"💰 Income Logged: {formatted_amt} {concept_detail}{date_str}\n"
                                    f"📊 {snapshot['month_name']} Snapshot:\n"
                                    f"• Total In: {formatted_in}\n"
                                    f"• Total Out: {formatted_out}\n"
                                    f"• Net Savings: {formatted_net}{pct_str}"
                                )
                            else:
                                
                                response_text = f"Saved {result.amount} {result.currency} for '{result.concept}' under category '{result.category}'{date_str}."

                            # Trigger background notion mirroring safely without affecting transaction response
                            try:
                                create_logged_task(self._safe_mirror_to_notion(
                                    family_id=family_id,
                                    amount=result.amount,
                                    currency=result.currency,
                                    concept=result.concept,
                                    category=result.category,
                                    timestamp=transaction_time,
                                    user_name=user_info["display_name"],
                                    transaction_id=tx_id,
                                    tx_type=result.type
                                ), name="mirror_to_notion")
                            except Exception as mirror_err:
                                logger.warning(f"[Notion Mirror] Failed to dispatch background mirror task: {mirror_err}")
                        except Exception as e:
                            logger.error(f"Persistence failed for user {user_id}. (Exception details omitted for security)")
                            status = "error"
                            response_text = "Failed to save transaction. Please try again later."
                except Exception as e:
                    logger.error(f"Extraction or routing failed for user {user_id}. (Exception details omitted for security)", exc_info=True)
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
        logger.info(f"[3s Audit] Total pipeline orchestration took {duration:.2f} seconds (user_id: {user_id}, text_len: {len(text or '')})")
