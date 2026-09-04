import time
import logging
import datetime
import asyncio
import re
import html
from collections import defaultdict, OrderedDict
from typing import Optional
from uuid import UUID
from sqlmodel import Session, select
from sqlalchemy import update as sa_update

from src.core.config import settings
from src.core.enums import IntentType
from src.core.encryption import EncryptionService
from src.db.session import engine
from src.db.models import User, Transaction, Family, ScheduledBill
from src.services.whisper_service import WhisperService
from src.services.extraction import ExtractionService, UnifiedResult, PayloadTruncatedError
from src.services.handlers.batch_tracker import BatchTracker
from src.services.telegram_service import TelegramService
from src.services.query import QueryService, ParsedQueryIntent
from src.services.export_service import ExportService
from src.services.account_service import AccountService
from src.services.family_service import FamilyService, PlanLimitExceededError
from src.services.notion_service import NotionService
from src.services.handlers.family_handler import (
    handle_create_family,
    handle_generate_invite,
    handle_family_info,
    handle_leave_family,
    handle_remove_member
)
from src.services.handlers.account_handler import handle_delete_account
from src.services.handlers.currency_handler import handle_manage_currency
from src.services.handlers.notion_handler import (
    handle_notion_manage,
    safe_mirror_to_notion,
    safe_update_notion_page,
    safe_archive_notion_page
)
from src.services.handlers.transaction_handler import (
    format_currency as _format_currency,
    get_monthly_cash_flow_snapshot,
    find_target_transaction,
    handle_transaction_undo,
    handle_transaction_correction
)
from src.services.handlers.bill_handler import (
    check_and_settle_bill,
    settle_bill_without_amount,
    get_overdue_bills_reminder
)

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

class _BoundedLockStore:
    """LRU-bounded dictionary of asyncio.Lock instances.

    Evicts the least-recently-used lock when ``max_entries`` is exceeded,
    preventing unbounded memory growth over months of production usage.
    Mirrors the BoundedCooldownStore pattern in the webhook route.
    """
    def __init__(self, max_entries: int = 10_000):
        self._locks: OrderedDict[str, asyncio.Lock] = OrderedDict()
        self._max = max_entries

    def __getitem__(self, key: str) -> asyncio.Lock:
        if key in self._locks:
            self._locks.move_to_end(key)
            return self._locks[key]
        lock = asyncio.Lock()
        self._locks[key] = lock
        if len(self._locks) > self._max:
            self._locks.popitem(last=False)
        return lock

class AIOrchestrator:
    _user_locks = _BoundedLockStore()

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

    def _persist_batch_items(
        self,
        user_uuid: UUID,
        family_id: UUID,
        items: list,
        family_currency: str,
        ref_time: datetime.datetime
    ) -> list:
        results = []
        with Session(engine) as session:
            try:
                tx_count = 0
                for item in items:
                    curr = item.currency or family_currency or "USD"
                    cpt = item.concept.strip() if item.concept else "Expense"
                    cat = item.category or "Other"
                    amt = item.amount
                    tx_type = getattr(item, "type", "expense") or "expense"
                    item_date = item.to_datetime(ref_time)

                    enc_amt = self.encryption_service.encrypt(f"{amt} {curr}")
                    enc_cpt = self.encryption_service.encrypt(cpt)

                    if item.is_scheduled_bill:
                        bill = ScheduledBill(
                            family_id=family_id,
                            user_id=user_uuid,
                            amount=enc_amt,
                            concept=enc_cpt,
                            category=cat,
                            due_date=item_date,
                            status="pending"
                        )
                        session.add(bill)
                        session.flush()
                        results.append({
                            "kind": "bill",
                            "concept": cpt,
                            "amount": amt,
                            "currency": curr,
                            "due_date": item_date,
                            "category": cat,
                            "id": bill.id
                        })
                    else:
                        tx = Transaction(
                            family_id=family_id,
                            user_id=user_uuid,
                            amount=enc_amt,
                            concept=enc_cpt,
                            category=cat,
                            timestamp=item_date,
                            type=tx_type
                        )
                        session.add(tx)
                        session.flush()
                        tx_count += 1
                        results.append({
                            "kind": "transaction",
                            "concept": cpt,
                            "amount": amt,
                            "currency": curr,
                            "timestamp": item_date,
                            "category": cat,
                            "id": tx.id,
                            "tx_type": tx_type
                        })

                if tx_count > 0:
                    session.execute(
                        sa_update(Family)
                        .where(Family.id == family_id)
                        .values(monthly_tx_count=Family.monthly_tx_count + tx_count)
                    )

                session.commit()
                return results
            except Exception as e:
                session.rollback()
                raise e

    def _check_and_settle_bill(
        self,
        family_id: UUID,
        tx_concept: str,
        tx_amount: float,
        tx_currency: str,
        tx_id: UUID,
        user_id: Optional[UUID] = None
    ) -> Optional[tuple[str, str]]:
        """Inspects pending ScheduledBills and marks matching bills paid."""
        return check_and_settle_bill(family_id, tx_concept, tx_amount, tx_currency, tx_id, user_id, self.encryption_service, session_factory=Session)

    def _settle_bill_without_amount(
        self,
        family_id: UUID,
        user_uuid: UUID,
        raw_text: str,
        is_spanish: bool
    ) -> Optional[str]:
        """Settles a pending scheduled bill from a payment claim without an amount."""
        return settle_bill_without_amount(family_id, user_uuid, raw_text, is_spanish, self.encryption_service, session_factory=Session)

    def _get_overdue_bills_reminder(
        self,
        family_id: UUID,
        is_spanish: bool = False,
        reference_time: Optional[datetime.datetime] = None
    ) -> str:
        """Returns formatted reminder block for upcoming/overdue bills."""
        return get_overdue_bills_reminder(family_id, is_spanish, self.encryption_service, reference_time, session_factory=Session)

    def _get_monthly_cash_flow_snapshot(
        self,
        family_id: UUID,
        target_date: datetime.datetime,
        primary_currency: str = "USD"
    ) -> dict:
        """Calculates monthly cash flow snapshot for family."""
        return get_monthly_cash_flow_snapshot(family_id, target_date, primary_currency, self.encryption_service, session_factory=Session)

    def _get_user_family_id(self, user_uuid: UUID) -> UUID:
        """Synchronous database helper to fetch family_id."""
        with Session(engine) as session:
            user = session.get(User, user_uuid)
            if not user or not user.family_id:
                raise ValueError("User not associated with a family")
            return user.family_id

    def _get_user_info(self, user_uuid: UUID) -> dict:
        """Helper to fetch user information (display name, username, telegram_id, family_id)."""
        with Session(engine) as session:
            user = session.get(User, user_uuid)
            if not user:
                raise ValueError("User not found")
            return {
                "display_name": user.full_name or user.username or "User",
                "username": user.username,
                "telegram_id": user.telegram_id,
                "family_id": user.family_id
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

    def _find_target_transaction(
        self,
        session: Session,
        user_uuid: UUID,
        target_amount: Optional[float] = None,
        target_currency: Optional[str] = None,
        target_concept: Optional[str] = None
    ) -> Optional[Transaction]:
        return find_target_transaction(session, user_uuid, target_amount, target_currency, target_concept, self.encryption_service)

    def _handle_transaction_undo(self, user_uuid: UUID, parsed_query: Optional[ParsedQueryIntent] = None) -> str:
        return handle_transaction_undo(user_uuid, parsed_query, self.encryption_service, session_factory=Session)

    def _handle_transaction_correction(self, user_uuid: UUID, parsed_query: ParsedQueryIntent) -> str:
        return handle_transaction_correction(user_uuid, parsed_query, self.encryption_service, session_factory=Session)

    async def _safe_mirror_to_notion(self, family_id: UUID, amount: float, currency: str, concept: str, category: str, timestamp: datetime.datetime, user_name: Optional[str], transaction_id: Optional[UUID] = None, tx_type: str = "expense"):
        return await safe_mirror_to_notion(family_id, amount, currency, concept, category, timestamp, user_name, transaction_id, tx_type)

    async def _safe_update_notion_page(self, family_id: UUID, page_id: str, amount: float, currency: str, concept: str, category: str, timestamp: datetime.datetime, user_name: Optional[str], tx_type: str = "expense"):
        return await safe_update_notion_page(family_id, page_id, amount, currency, concept, category, timestamp, user_name, tx_type)

    async def _safe_archive_notion_page(self, family_id: UUID, page_id: str):
        return await safe_archive_notion_page(family_id, page_id)

    async def _execute_parsed_query(
        self,
        parsed_query: ParsedQueryIntent,
        raw_text: str,
        user_uuid: UUID,
        chat_id: int,
        message_id: Optional[int] = None
    ) -> Optional[str]:
        """
        Executes a parsed query intent and returns the response text.
        """
        raw_lower = raw_text.lower().strip()
        parts = raw_text.split()
        intent_str = getattr(parsed_query, "intent", None) or ""

        if intent_str == IntentType.DELETE_ACCOUNT or intent_str == "delete_account":
            return await handle_delete_account(user_uuid, raw_text)

        elif intent_str == IntentType.EXPORT_DATA or intent_str == "export_data":
            family_id = await asyncio.to_thread(self._get_user_family_id, user_uuid)
            ALLOWED_EXPORT_FORMATS = {"csv", "json"}
            raw_format = (parsed_query.export_format or "csv").lower()
            export_format = raw_format if raw_format in ALLOWED_EXPORT_FORMATS else "csv"
            export_service = ExportService()
            await export_service.export_and_send(family_id, chat_id, export_format)
            return None

        elif intent_str == IntentType.UNDO_LAST or intent_str == "undo_last":
            return await asyncio.to_thread(self._handle_transaction_undo, user_uuid, parsed_query)

        elif intent_str == IntentType.EDIT_LAST or intent_str == "edit_last":
            return await asyncio.to_thread(self._handle_transaction_correction, user_uuid, parsed_query)

        elif intent_str == IntentType.LEAVE_FAMILY or intent_str == "leave_family":
            return await handle_leave_family(user_uuid, raw_text)

        elif intent_str == IntentType.REMOVE_MEMBER or intent_str == "remove_member":
            return await handle_remove_member(user_uuid, parsed_query.target_member)

        elif intent_str in [
            IntentType.SPENDING_SUMMARY, "spending_summary",
            IntentType.QUERY_SPENDING, "query_spending",
            IntentType.INCOME_SUMMARY, "income_summary",
            IntentType.QUERY_INCOME, "query_income",
            IntentType.EARNINGS_SUMMARY, "earnings_summary",
            IntentType.NET_CASH_FLOW, "net_cash_flow",
            IntentType.NET_BALANCE, "net_balance",
            IntentType.CASH_FLOW_SUMMARY, "cash_flow_summary"
        ]:
            family_service = FamilyService()
            family_info = await asyncio.to_thread(family_service.get_family_info, user_uuid)
            family_id = family_info["id"]
            family_currency = await asyncio.to_thread(family_service.get_family_default_currency, family_id) if hasattr(family_service, "get_family_default_currency") else "USD"
            
            family_name = family_info["name"] if parsed_query.scope == "family" else None
            member_names = [m.get("full_name") or m.get("username") or "User" for m in family_info["members"]] if parsed_query.scope == "family" else None
            
            user_name = None
            reference_time = datetime.datetime.now(datetime.timezone.utc)
            query_service = QueryService()

            if intent_str in [IntentType.INCOME_SUMMARY, "income_summary", IntentType.QUERY_INCOME, "query_income", IntentType.EARNINGS_SUMMARY, "earnings_summary"]:
                summary_res = await query_service.get_income_summary(
                    family_id=family_id,
                    timeframe=parsed_query.timeframe,
                    category=parsed_query.category,
                    user_name=user_name,
                    reference_time=reference_time,
                    family_name=family_name,
                    member_names=member_names,
                    primary_currency=family_currency
                )
            elif intent_str in [IntentType.NET_CASH_FLOW, "net_cash_flow", IntentType.NET_BALANCE, "net_balance", IntentType.CASH_FLOW_SUMMARY, "cash_flow_summary"]:
                summary_res = await query_service.get_net_cash_flow_summary(
                    family_id=family_id,
                    timeframe=parsed_query.timeframe,
                    user_name=user_name,
                    reference_time=reference_time,
                    family_name=family_name,
                    member_names=member_names,
                    primary_currency=family_currency
                )
            else:
                summary_res = await query_service.get_spending_summary(
                    family_id=family_id,
                    timeframe=parsed_query.timeframe,
                    category=parsed_query.category,
                    user_name=user_name,
                    reference_time=reference_time,
                    family_name=family_name,
                    member_names=member_names,
                    primary_currency=family_currency
                )

            # Proactive reminder for due/overdue scheduled bills when inquiring about current status/month
            if intent_str in [IntentType.SPENDING_SUMMARY, "spending_summary", IntentType.QUERY_SPENDING, "query_spending", IntentType.NET_CASH_FLOW, "net_cash_flow", IntentType.NET_BALANCE, "net_balance", IntentType.CASH_FLOW_SUMMARY, "cash_flow_summary"]:
                if parsed_query.timeframe in ["this_month", "all_time", "current_month"] or not parsed_query.timeframe:
                    is_spanish = any(w in raw_lower for w in ["como", "cómo", "venimos", "mes", "gastos", "resumen", "balance", "pesos"])
                    overdue_block = await asyncio.to_thread(self._get_overdue_bills_reminder, family_id, is_spanish, reference_time)
                    if overdue_block:
                        summary_res += f"\n\n{overdue_block}"

            # Append friendly shortcut pro-tip if asked in natural language
            plan_type = family_info.get("plan_type", "free")
            if not raw_text.strip().startswith("/"):
                if plan_type == "free":
                    summary_res += "\n\n💡 <i>Pro-tip: Type /month or /me anytime for an instant response that doesn't use your monthly AI quota!</i>"
                else:
                    summary_res += "\n\n💡 <i>Pro-tip: Type /month or /me anytime for an instant response!</i>"

            return summary_res

        elif intent_str == IntentType.UPCOMING_BILLS or intent_str == "upcoming_bills":
            family_id = await asyncio.to_thread(self._get_user_family_id, user_uuid)
            query_service = QueryService()
            bills_res = await query_service.get_upcoming_bills_summary(
                family_id=family_id,
                timeframe=parsed_query.timeframe or "this_month",
                raw_text=raw_text
            )
            if not raw_text.strip().startswith("/"):
                family_service = FamilyService()
                f_info = await asyncio.to_thread(family_service.get_family_info, user_uuid)
                p_type = f_info.get("plan_type", "free")
                if p_type == "free":
                    bills_res += "\n\n💡 <i>Pro-tip: Type /bills anytime for an instant check that doesn't use your monthly AI quota!</i>"
                else:
                    bills_res += "\n\n💡 <i>Pro-tip: Type /bills anytime for an instant check!</i>"
            return bills_res

        elif intent_str == IntentType.CREATE_FAMILY or intent_str == "create_family":
            return await handle_create_family(user_uuid, parsed_query.family_name)

        elif intent_str == IntentType.GENERATE_INVITE or intent_str == "generate_invite":
            family_id = await asyncio.to_thread(self._get_user_family_id, user_uuid)
            return await handle_generate_invite(user_uuid, family_id)

        elif intent_str == IntentType.FAMILY_INFO or intent_str == "family_info":
            return await handle_family_info(user_uuid)

        elif intent_str == IntentType.NOTION_MANAGE or intent_str == "notion_manage":
            family_id = await asyncio.to_thread(self._get_user_family_id, user_uuid)
            return await handle_notion_manage(raw_text, family_id, chat_id, message_id)

        elif intent_str == IntentType.MANAGE_CURRENCY or intent_str == "manage_currency":
            family_id = await asyncio.to_thread(self._get_user_family_id, user_uuid)
            return await handle_manage_currency(user_uuid, family_id, raw_text)

        return "I couldn't process your request."

    async def orchestrate(self, user_id: str, text: Optional[str], audio_file_id: Optional[str], chat_id: int, message_id: Optional[int] = None):
        async with self._user_locks[str(user_id)]:
            await self._orchestrate_impl(
                user_id=user_id,
                text=text,
                audio_file_id=audio_file_id,
                chat_id=chat_id,
                message_id=message_id,
                send_telegram=True,
                dry_run=False
            )

    async def simulate_message(
        self,
        text: str,
        default_currency: str = "USD",
        dry_run: bool = True,
        user_id: Optional[str] = None,
        family_id: Optional[str] = None,
        extraction_service: Optional[ExtractionService] = None
    ) -> dict:
        uid = user_id or "00000000-0000-0000-0000-000000000001"
        return await self._orchestrate_impl(
            user_id=uid,
            text=text,
            audio_file_id=None,
            chat_id=None,
            message_id=None,
            send_telegram=False,
            dry_run=dry_run,
            default_currency=default_currency,
            extraction_service=extraction_service
        )

    async def _orchestrate_impl(
        self,
        user_id: str,
        text: Optional[str],
        audio_file_id: Optional[str],
        chat_id: Optional[int] = None,
        message_id: Optional[int] = None,
        send_telegram: bool = True,
        dry_run: bool = False,
        default_currency: Optional[str] = None,
        extraction_service: Optional[ExtractionService] = None
    ) -> dict:
        start_time = time.time()
        status = "success"
        response_text = ""
        all_items = []
        unified = None
        
        try:
            try:
                user_uuid = UUID(user_id)
            except ValueError:
                if dry_run:
                    import uuid as _uuid
                    user_uuid = _uuid.UUID("00000000-0000-0000-0000-000000000001")
                else:
                    raise ValueError(f"Invalid user_id format: {user_id}")

            # 1. Process Audio if provided
            if audio_file_id:
                try:
                    telegram_service = TelegramService()
                    audio_bytes = await telegram_service.download_file_bytes(audio_file_id)
                    whisper_service = WhisperService()
                    text, _ = await whisper_service.transcribe(audio_bytes=audio_bytes)
                    if not text:
                        raise ValueError("Transcription returned empty text.")
                except Exception as e:
                    logger.error(f"Transcription failed: {e}")
                    status = "error"
                    response_text = "I couldn't understand the audio. Could you please type it or try again?"
                    
            # 2. Process Text (Fast-path deterministic commands or Unified Classification & Extraction)
            if text and status == "success":
                try:
                    raw_text = text.strip()
                    raw_lower = raw_text.lower()

                    # Fast-path deterministic command and shortcut matching
                    deterministic_intent = None
                    if raw_text == "CONFIRM DELETE":
                        deterministic_intent = ParsedQueryIntent(intent="delete_account", timeframe="all_time")
                    elif raw_lower in [
                        "/undo", "undo", "undo last", "undo latest", "delete last", "delete the last",
                        "delete last log", "delete the last log", "delete last transaction",
                        "delete the last transaction", "remove last log", "remove the last log",
                        "remove last transaction", "remove the last transaction",
                        "delete last expense", "delete last income", "deshacer", "deshacer último", "borrar el último"
                    ]:
                        deterministic_intent = ParsedQueryIntent(intent="undo_last")
                    elif re.match(r"^change (the )?(last|latest)? ?(one|log|transaction)? ?to income$", raw_lower) or raw_lower in ["change to income", "make it income", "it was income", "switch to income", "cambiar a ingreso", "cambiar el último a ingreso"]:
                        deterministic_intent = ParsedQueryIntent(intent="edit_last", new_type="income", new_category="Salary")
                    elif re.match(r"^change (the )?(last|latest)? ?(one|log|transaction)? ?to expense$", raw_lower) or raw_lower in ["change to expense", "make it expense", "it was expense", "switch to expense", "cambiar a gasto", "cambiar el último a gasto"]:
                        deterministic_intent = ParsedQueryIntent(intent="edit_last", new_type="expense", new_category="Other")
                    elif m := (re.match(r"^change (the )?(last|latest)? ?amount to (\d+(?:[.,]\d{1,2})?)\s*([a-zA-Z$€£]*)$", raw_lower) or re.match(r"^(?:actualizar|cambiar) (?:el )?(?:último|ultimo)? ?(?:monto|importe)? ?a (\d+(?:[.,]\d{1,2})?)\s*([a-zA-Z$€£]*)$", raw_lower)):
                        amt_val = float(m.group(3).replace(",", "."))
                        curr_raw = m.group(4).strip() if len(m.groups()) >= 4 and m.group(4) else ""
                        curr_map = {"$": "USD", "€": "EUR", "£": "GBP", "usd": "USD", "eur": "EUR", "gbp": "GBP", "dollars": "USD", "euros": "EUR", "pounds": "GBP", "pesos": "ARS", "ars": "ARS"}
                        curr_val = curr_map.get(curr_raw.lower(), curr_raw.upper() if len(curr_raw) == 3 else None)
                        deterministic_intent = ParsedQueryIntent(intent="edit_last", new_amount=amt_val, new_currency=curr_val)
                    elif m := (re.match(r"^change (the )?(last|latest)? ?category to (.+)$", raw_lower) or re.match(r"^(?:actualizar|cambiar) (?:la )?(?:última|ultima)? ?categor[íi]a a (.+)$", raw_lower)):
                        cat_val = m.group(3).strip()
                        deterministic_intent = ParsedQueryIntent(intent="edit_last", new_category=cat_val)
                    elif m := (re.match(r"^change (the )?(last|latest)? ?concept to (.+)$", raw_lower) or re.match(r"^(?:actualizar|cambiar) (?:el )?(?:último|ultimo)? ?concepto a (.+)$", raw_lower)):
                        concept_val = m.group(3).strip()
                        deterministic_intent = ParsedQueryIntent(intent="edit_last", new_concept=concept_val)
                    elif raw_lower.startswith("/createfamily") or raw_lower.startswith("create family"):
                        name = raw_text[13:].strip() if raw_lower.startswith("/createfamily") else raw_text[13:].strip()
                        deterministic_intent = ParsedQueryIntent(intent="create_family", family_name=name)
                    elif raw_text in ("/leavefamily", "/leavefamily confirm", "/leavefamily confirmar") or raw_lower in [
                        "leave family", "leave the family", "leave group", "confirm leave", "confirmar salir",
                        "leave family confirm", "leave family confirmar"
                    ]:
                        deterministic_intent = ParsedQueryIntent(intent="leave_family")
                    elif raw_lower.startswith("/removemember") or raw_lower.startswith("remove member"):
                        target = raw_text[13:].strip() if raw_lower.startswith("/removemember") else raw_text[13:].strip()
                        deterministic_intent = ParsedQueryIntent(intent="remove_member", target_member=target)
                    elif raw_text == "/invite" or raw_lower in ["invite", "invite link", "invite family member", "generate invite link", "generate invite", "invite to family"]:
                        deterministic_intent = ParsedQueryIntent(intent="generate_invite")
                    elif raw_text == "/family" or raw_lower in ["my family", "family info", "family members"]:
                        deterministic_intent = ParsedQueryIntent(intent="family_info")
                    elif raw_lower.startswith("/currency") or raw_lower == "currency" or raw_lower.startswith("currency ") or raw_lower.startswith("cambiar moneda") or raw_lower.startswith("set currency") or raw_lower.startswith("mi moneda es"):
                        deterministic_intent = ParsedQueryIntent(intent="manage_currency")
                    elif raw_lower.startswith("/notion"):
                        deterministic_intent = ParsedQueryIntent(intent="notion_manage")
                    elif raw_lower in ["/bills", "/vencimientos", "bills", "vencimientos", "facturas pendientes", "upcoming bills"]:
                        deterministic_intent = ParsedQueryIntent(intent="upcoming_bills", timeframe="this_month")
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
                        deterministic_intent = ParsedQueryIntent(intent="spending_summary", timeframe=timeframe, category=category, scope="family")
                    elif raw_text.startswith("/"):
                        query_service = QueryService()
                        deterministic_intent = await query_service.parse_intent(text)

                    if deterministic_intent is not None:
                        res = await self._execute_parsed_query(deterministic_intent, raw_text, user_uuid, chat_id, message_id)
                        if res is None:
                            return {"status": "ok"}
                        response_text = res
                    else:
                        # Unified Single-Call Classification & Extraction
                        if not dry_run:
                            try:
                                family_id = await asyncio.to_thread(self._get_user_family_id, user_uuid)
                                family_service = FamilyService()
                                family_currency = await asyncio.to_thread(family_service.get_family_default_currency, family_id)
                            except Exception:
                                family_id = None
                                family_currency = default_currency or "USD"
                        else:
                            family_id = None
                            family_currency = default_currency or "USD"

                        # Track daily AI message usage for this workspace
                        if family_id and not dry_run:
                            try:
                                with Session(engine) as d_sess:
                                    d_sess.execute(
                                        sa_update(Family)
                                        .where(Family.id == family_id)
                                        .values(daily_tx_count=Family.daily_tx_count + 1)
                                    )
                                    d_sess.commit()
                            except Exception as d_err:
                                logger.warning(f"Could not increment daily_tx_count: {d_err}")

                        extraction_service = extraction_service or ExtractionService()
                        override_tx_time = None
                        try:
                            if hasattr(extraction_service, "classify_and_extract"):
                                unified = await extraction_service.classify_and_extract(text=text, default_currency=family_currency)
                            else:
                                ex = await extraction_service.extract(text=text, default_currency=family_currency)
                                amt = getattr(ex, "amount", None)
                                if not isinstance(amt, (int, float)):
                                    amt = None
                                curr = getattr(ex, "currency", None)
                                if not isinstance(curr, str):
                                    curr = family_currency or "USD"
                                cat = getattr(ex, "category", None)
                                if not isinstance(cat, str):
                                    cat = "Other"
                                cpt = getattr(ex, "concept", None)
                                if not isinstance(cpt, str):
                                    cpt = text.strip()
                                tp = getattr(ex, "type", None)
                                if not isinstance(tp, str):
                                    tp = "expense"
                                t_date = getattr(ex, "transaction_date", None)
                                if not isinstance(t_date, str):
                                    t_date = None

                                unified = UnifiedResult(
                                    action="log_transaction",
                                    type=tp,
                                    amount=amt,
                                    category=cat,
                                    concept=cpt,
                                    currency=curr,
                                    transaction_date=t_date
                                )
                                if hasattr(ex, "to_datetime") and callable(ex.to_datetime):
                                    try:
                                        override_tx_time = ex.to_datetime()
                                    except Exception:
                                        pass
                        except PayloadTruncatedError:
                            is_spanish = any(w in raw_lower for w in ["gastos", "fijos", "vencimiento", "vence", "prestamo", "préstamo", "tarjeta", "pesos", "pago", "cuentas", "facturas", "cambie", "cambié", "dolares", "dólares"])
                            if is_spanish:
                                response_text = (
                                    "⚠️ <b>Lista demasiado extensa:</b>\n\n"
                                    "Por tu seguridad financiera, no se guardó ningún gasto parcial de este mensaje.\n"
                                    "Por favor, divide la lista y envíala en 2 mensajes más cortos."
                                )
                            else:
                                response_text = (
                                    "⚠️ <b>List is too long:</b>\n\n"
                                    "For your financial safety, no partial transactions were saved.\n"
                                    "Please split your list and send it in 2 smaller messages."
                                )
                            try:
                                tg_svc = TelegramService()
                                await tg_svc.send_message(chat_id=chat_id, text=response_text)
                            except Exception as e:
                                logger.error(f"Failed to send direct reply to Telegram: {e}")
                            return {"status": "ok", "response": response_text}

                        if unified.action == "undo_last":
                            parsed_query = ParsedQueryIntent(
                                intent="undo_last",
                                target_amount=unified.target_amount,
                                target_currency=unified.target_currency,
                                target_concept=unified.target_concept
                            )
                            response_text = await asyncio.to_thread(self._handle_transaction_undo, user_uuid, parsed_query)
                        elif unified.action == "edit_last":
                            parsed_query = ParsedQueryIntent(
                                intent="edit_last",
                                new_type=unified.new_type,
                                new_amount=unified.new_amount,
                                new_currency=unified.new_currency,
                                new_category=unified.new_category,
                                new_concept=unified.new_concept,
                                target_amount=unified.target_amount,
                                target_currency=unified.target_currency,
                                target_concept=unified.target_concept
                            )
                            response_text = await asyncio.to_thread(self._handle_transaction_correction, user_uuid, parsed_query)
                        elif unified.action == "query":
                            query_service = QueryService()
                            parsed_query = await query_service.parse_intent(text)
                            res = await self._execute_parsed_query(parsed_query, raw_text, user_uuid, chat_id, message_id)
                            if res is None:
                                return {"status": "ok"}
                            response_text = res
                        else:
                            # action == "log_transaction"
                            all_items = unified.get_all_items() if hasattr(unified, "get_all_items") else []
                            if len(all_items) > 1 or (len(all_items) == 1 and all_items[0].is_scheduled_bill):
                                if not dry_run:
                                    try:
                                        user_info = await asyncio.to_thread(self._get_user_info, user_uuid)
                                        family_id = user_info["family_id"]
                                    except Exception as u_err:
                                        logger.warning(f"Failed to get user info: {u_err}")
                                        family_id = await asyncio.to_thread(self._get_user_family_id, user_uuid)
                                        user_info = {"display_name": "User"}

                                    try:
                                        batch_results = await asyncio.to_thread(
                                            self._persist_batch_items,
                                            user_uuid=user_uuid,
                                            family_id=family_id,
                                            items=all_items,
                                            family_currency=family_currency,
                                            ref_time=datetime.datetime.now(datetime.timezone.utc)
                                        )
                                        batch_tx_ids = [r["id"] for r in batch_results if r.get("kind") == "transaction"]
                                        if batch_tx_ids:
                                            BatchTracker.set_last_batch(user_uuid, batch_tx_ids)
                                    except Exception as e:
                                        logger.error(f"Batch persistence failed for user {user_id}: {e}", exc_info=True)
                                        status = "error"
                                        response_text = "Failed to save transactions. Please try again later."
                                        batch_results = []
                                else:
                                    user_info = {"display_name": "User"}
                                    batch_results = []
                                    ref_now = datetime.datetime.now(datetime.timezone.utc)
                                    for item in all_items:
                                        curr = item.currency or family_currency or "USD"
                                        cpt = item.concept.strip() if item.concept else "Expense"
                                        cat = item.category or "Other"
                                        amt = item.amount
                                        tx_type = getattr(item, "type", "expense") or "expense"
                                        item_date = item.to_datetime(ref_now) if hasattr(item, "to_datetime") else ref_now
                                        if getattr(item, "is_scheduled_bill", False):
                                            batch_results.append({
                                                "kind": "bill",
                                                "concept": cpt,
                                                "amount": amt,
                                                "currency": curr,
                                                "due_date": item_date,
                                                "category": cat,
                                                "id": None
                                            })
                                        else:
                                            batch_results.append({
                                                "kind": "transaction",
                                                "concept": cpt,
                                                "amount": amt,
                                                "currency": curr,
                                                "timestamp": item_date,
                                                "category": cat,
                                                "id": None,
                                                "tx_type": tx_type
                                            })

                                is_spanish = any(w in raw_lower for w in ["gastos", "gasto", "gaste", "gasté", "fijos", "vencimiento", "vence", "prestamo", "préstamo", "tarjeta", "pesos", "pago", "cuentas", "facturas", "cambie", "cambié", "dolares", "dólares", "cobre", "cobré", "ingreso", "ingresos", "sueldo", "almacen", "almacén", "super", "súper", "verdu", "nafta", " y ", " en ", " de ", "para "])
                                bills = [r for r in batch_results if r["kind"] == "bill"]
                                txs = [r for r in batch_results if r["kind"] == "transaction"]

                                is_exchange = getattr(unified, "is_exchange", False) or (
                                    len(txs) == 2 and
                                    len(bills) == 0 and
                                    any(t["tx_type"] == "expense" for t in txs) and
                                    any(t["tx_type"] == "income" for t in txs) and
                                    all(t["category"] == "Exchange" for t in txs)
                                )

                                if is_exchange:
                                    sold = next(t for t in txs if t["tx_type"] == "expense")
                                    recv = next(t for t in txs if t["tx_type"] == "income")
                                    fmt_sold = _format_currency(sold["amount"], sold["currency"], show_sign=False)
                                    fmt_recv = _format_currency(recv["amount"], recv["currency"], show_sign=False)
                                    rate_val = getattr(unified, "exchange_rate", None)
                                    if not rate_val and sold["amount"] > 0:
                                        rate_val = round(recv["amount"] / sold["amount"], 4)

                                    if is_spanish:
                                        rate_line = f"\n• 📊 Cotización: 1 {sold['currency']} = {_format_currency(rate_val, recv['currency'], show_sign=False)}" if rate_val else ""
                                        response_text = (
                                            f"💱 <b>Cambio de Moneda Registrado:</b>\n"
                                            f"• 💸 Entregaste: -{fmt_sold}\n"
                                            f"• 💰 Recibiste: +{fmt_recv}"
                                            f"{rate_line}\n\n"
                                            f"🏷️ <i>Categorizado bajo <b>Exchange</b> para no distorsionar ingresos o gastos operativos del mes.</i>"
                                        )
                                    else:
                                        rate_line = f"\n• 📊 Rate: 1 {sold['currency']} = {_format_currency(rate_val, recv['currency'], show_sign=False)}" if rate_val else ""
                                        response_text = (
                                            f"💱 <b>Currency Exchange Logged:</b>\n"
                                            f"• 💸 Sold: -{fmt_sold}\n"
                                            f"• 💰 Received: +{fmt_recv}"
                                            f"{rate_line}\n\n"
                                            f"🏷️ <i>Categorized under <b>Exchange</b> to keep operational income & expenses clean.</i>"
                                        )
                                else:
                                    parts = []
                                    if bills:
                                        header = f"📋 <b>{len(bills)} Factura(s) Programada(s):</b>\n\n" if is_spanish else f"📋 <b>{len(bills)} Scheduled Bill(s):</b>\n\n"
                                        parts.append(header)
                                        for b in bills:
                                            fmt_amt = _format_currency(b["amount"], b["currency"])
                                            due_str = b["due_date"].strftime("%d/%m")
                                            if is_spanish:
                                                day_name = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"][b["due_date"].weekday()]
                                                parts.append(f"• 💳 <b>{html.escape(b['concept'])}:</b> {fmt_amt} <i>(Vence: {day_name} {due_str})</i>\n")
                                            else:
                                                day_name = b["due_date"].strftime("%a")
                                                parts.append(f"• 💳 <b>{html.escape(b['concept'])}:</b> {fmt_amt} <i>(Due: {day_name} {due_str})</i>\n")

                                        totals = {}
                                        for b in bills:
                                            totals[b["currency"]] = totals.get(b["currency"], 0.0) + b["amount"]
                                        tot_str = " + ".join([_format_currency(amt, curr) for curr, amt in totals.items()])
                                        if is_spanish:
                                            parts.append(f"\n📌 <b>Total pendiente por pagar:</b> {tot_str}")
                                        else:
                                            parts.append(f"\n📌 <b>Total pending to pay:</b> {tot_str}")

                                    if txs:
                                        if parts:
                                            parts.append("\n\n")
                                        incomes = [t for t in txs if t.get("tx_type") == "income"]
                                        expenses = [t for t in txs if t.get("tx_type") != "income"]
                                        if len(incomes) > 0 and len(expenses) == 0:
                                            header = f"📋 <b>{len(txs)} Ingreso(s) Registrado(s):</b>\n\n" if is_spanish else f"📋 <b>{len(txs)} Income(s) Logged:</b>\n\n"
                                        elif len(expenses) > 0 and len(incomes) == 0:
                                            header = f"📋 <b>{len(txs)} Gasto(s) Registrado(s):</b>\n\n" if is_spanish else f"📋 <b>{len(txs)} Expense(s) Logged:</b>\n\n"
                                        else:
                                            header = f"📋 <b>{len(txs)} Transacciones Registradas:</b>\n\n" if is_spanish else f"📋 <b>{len(txs)} Transactions Logged:</b>\n\n"
                                        parts.append(header)
                                        for t in txs:
                                            is_inc = t.get("tx_type") == "income"
                                            icon = "💰" if is_inc else "💸"
                                            fmt_amt = _format_currency(t["amount"], t["currency"], show_sign=is_inc)
                                            parts.append(f"• {icon} <b>{html.escape(t['concept'])}:</b> {fmt_amt} ({html.escape(t['category'])})\n")

                                    if bills:
                                        tip = '\n\n💡 <i>Pregúntame "¿qué vence esta semana?" cuando quieras revisar tus vencimientos.</i>' if is_spanish else '\n\n💡 <i>Ask me "what bills are due this week?" whenever you want to check your upcoming obligations.</i>'
                                        parts.append(tip)

                                    response_text = "".join(parts)

                                if not dry_run:
                                    for t in txs:
                                        try:
                                            create_logged_task(self._safe_mirror_to_notion(
                                                family_id=family_id,
                                                amount=t["amount"],
                                                currency=t["currency"],
                                                concept=t["concept"],
                                                category=t["category"],
                                                timestamp=t["timestamp"],
                                                user_name=user_info.get("display_name", "User"),
                                                transaction_id=t["id"],
                                                tx_type=t["tx_type"]
                                            ), name="mirror_to_notion")
                                        except Exception:
                                            pass

                            elif unified.amount is None:
                                is_spanish = any(w in raw_lower for w in ["pagué", "pague", "aboné", "abone", "tarjeta", "pesos", "factura", "prestamo", "préstamo", "cuentas", "luz", "gas", "agua"])
                                is_payment_claim = bool(re.search(r'\b(?:pagu[eé]|paid|abon[eé]|liquid[eé]|cancel[eé]|pay)\b', raw_lower))
                                if is_payment_claim:
                                    settle_res = await asyncio.to_thread(
                                        self._settle_bill_without_amount,
                                        family_id=family_id,
                                        user_uuid=user_uuid,
                                        raw_text=raw_text,
                                        is_spanish=is_spanish
                                    )
                                    if settle_res:
                                        response_text = settle_res
                                    else:
                                        concept_hint = re.sub(r'\b(?:pagu[eé]|paid|abon[eé]|liquid[eé]|cancel[eé]|pay|la|el|los|las|the|de|del|por|for|mi|my)\b', '', raw_text, flags=re.IGNORECASE).strip()
                                        if is_spanish:
                                            response_text = f"ℹ️ No encontré ninguna factura pendiente para '{html.escape(concept_hint or raw_text)}'. ¿Cuánto fue el monto que pagaste?"
                                        else:
                                            response_text = f"ℹ️ I couldn't find an upcoming bill matching '{html.escape(concept_hint or raw_text)}'. What was the amount paid?"
                                else:
                                    query_service = QueryService()
                                    parsed_query = await query_service.parse_intent(text)
                                    if parsed_query.intent != "log_expense":
                                        res = await self._execute_parsed_query(parsed_query, raw_text, user_uuid, chat_id, message_id)
                                        if res is None:
                                            return {"status": "ok"}
                                        response_text = res
                                    else:
                                        response_text = "I couldn't extract the details from your message. Please make sure to include the amount and what it was for."
                            else:
                                transaction_time = override_tx_time if override_tx_time is not None else unified.to_datetime()
                                tx_amount = unified.amount
                                tx_currency = unified.currency or family_currency or "USD"
                                tx_concept = unified.concept or text.strip()
                                tx_category = unified.category or "Other"
                                tx_type = unified.type or "expense"

                                if not dry_run:
                                    try:
                                        # Persist Transaction
                                        encrypted_amount = self.encryption_service.encrypt(f"{tx_amount} {tx_currency}")
                                        encrypted_concept = self.encryption_service.encrypt(tx_concept)

                                        tx_id = await asyncio.to_thread(
                                            self._persist_transaction,
                                            user_uuid=user_uuid,
                                            amount=encrypted_amount,
                                            concept=encrypted_concept,
                                            category=tx_category,
                                            timestamp=transaction_time,
                                            tx_type=tx_type
                                        )
                                        if tx_id:
                                            BatchTracker.set_last_batch(user_uuid, [tx_id])

                                        try:
                                            user_info = await asyncio.to_thread(self._get_user_info, user_uuid)
                                            family_id = user_info["family_id"]
                                        except Exception as u_err:
                                            logger.warning(f"Failed to get user info: {u_err}")
                                            family_id = await asyncio.to_thread(self._get_user_family_id, user_uuid)
                                            user_info = {"display_name": "User"}
                                    except Exception as p_err:
                                        logger.error(f"Persistence failed for user {user_id}: {p_err}", exc_info=True)
                                        tx_id = None
                                        user_info = {"display_name": "User"}
                                else:
                                    tx_id = None
                                    user_info = {"display_name": "User"}

                                    date_str = ""
                                    if getattr(unified, "transaction_date", None):
                                        date_str = f" (logged for {transaction_time.strftime('%b %d, %Y')})"

                                    if tx_type == "income":
                                        if not dry_run and family_id:
                                            snapshot = await asyncio.to_thread(
                                                self._get_monthly_cash_flow_snapshot,
                                                family_id=family_id,
                                                target_date=transaction_time,
                                                primary_currency=tx_currency
                                            )
                                        else:
                                            snapshot = {
                                                "month_name": transaction_time.strftime("%B"),
                                                "total_in": tx_amount,
                                                "total_out": 0.0,
                                                "net_savings": tx_amount,
                                                "savings_pct": 100
                                            }

                                        safe_concept = html.escape(tx_concept)
                                        safe_cat = html.escape(tx_category)
                                        if tx_concept.strip().lower() == tx_category.strip().lower():
                                            concept_detail = f"({safe_cat})"
                                        else:
                                            concept_detail = f"({safe_cat} - {safe_concept})"

                                        formatted_amt = _format_currency(tx_amount, tx_currency, show_sign=True)
                                        formatted_in = _format_currency(snapshot["total_in"], tx_currency, show_sign=False)
                                        formatted_out = _format_currency(snapshot["total_out"], tx_currency, show_sign=False)
                                        formatted_net = _format_currency(snapshot["net_savings"], tx_currency, show_sign=True)
                                        pct_str = f" ({snapshot['savings_pct']}%)" if snapshot["total_in"] > 0 else ""

                                        response_text = (
                                            f"💰 Income Logged: {formatted_amt} {concept_detail}{date_str}\n"
                                            f"📊 {snapshot['month_name']} Snapshot:\n"
                                            f"• Total In: {formatted_in}\n"
                                            f"• Total Out: {formatted_out}\n"
                                            f"• Net Savings: {formatted_net}{pct_str}"
                                        )
                                    else:
                                        safe_concept = html.escape(tx_concept)
                                        safe_cat = html.escape(tx_category)
                                        response_text = f"Saved {tx_amount} {tx_currency} for '{safe_concept}' under category '{safe_cat}'{date_str}."

                                        settlement = None
                                        if not dry_run:
                                            # Check and settle matching pending bill
                                            settlement = await asyncio.to_thread(
                                                self._check_and_settle_bill,
                                                family_id=family_id,
                                                tx_concept=tx_concept,
                                                tx_amount=tx_amount,
                                                tx_currency=tx_currency,
                                                tx_id=tx_id,
                                                user_id=user_uuid
                                            )
                                        if settlement:
                                            matched_concept, remaining_pending = settlement
                                            is_spanish = any(w in raw_lower for w in ["pagué", "pague", "aboné", "abone", "tarjeta", "prestamo", "préstamo", "factura", "gastos", "pesos"])
                                            if is_spanish:
                                                response_text += f"\n\n✅ <b>¡Marcado como pagado!</b>\n💳 <b>{html.escape(matched_concept)}</b> registrado en tus gastos.\n⏳ Restante pendiente este mes: <b>{remaining_pending}</b>"
                                            else:
                                                response_text += f"\n\n✅ <b>Marked as paid!</b>\n💳 <b>{html.escape(matched_concept)}</b> recorded in your expenses.\n⏳ Remaining pending this month: <b>{remaining_pending}</b>"

                                    if not dry_run:
                                        # Trigger background notion mirroring safely without affecting transaction response
                                        try:
                                            create_logged_task(self._safe_mirror_to_notion(
                                                family_id=family_id,
                                                amount=tx_amount,
                                                currency=tx_currency,
                                                concept=tx_concept,
                                                category=tx_category,
                                                timestamp=transaction_time,
                                                user_name=user_info["display_name"],
                                                transaction_id=tx_id,
                                                tx_type=tx_type
                                            ), name="mirror_to_notion")
                                        except Exception as mirror_err:
                                            logger.warning(f"[Notion Mirror] Failed to dispatch background mirror task: {mirror_err}")
                except Exception as e:
                    logger.error(f"Extraction or routing failed for user {user_id}. (Exception details omitted for security)", exc_info=True)
                    status = "error"
                    response_text = "I couldn't extract the details from your message. Please make sure to include the amount and what it was for."
            elif not text and status == "success":
                status = "error"
                response_text = "No message or audio was provided."
                
        except Exception as e:
            from src.core.security import sanitize_exception_message
            sanitized_err = sanitize_exception_message(e)
            logger.error(f"Unexpected error in orchestrator for user {user_id}: {sanitized_err}", exc_info=True)
            status = "error"
            response_text = "An unexpected error occurred while processing your request."
            
        # 3. Direct Reply via Telegram API
        if send_telegram and chat_id:
            try:
                telegram_service = TelegramService()
                await telegram_service.send_message(chat_id=chat_id, text=response_text)
            except Exception as e:
                logger.error(f"Failed to send direct reply to Telegram: {e}")
            
        # 4. Log 3s Audit
        duration = time.time() - start_time
        logger.info(f"[3s Audit] Total pipeline orchestration took {duration:.2f} seconds (user_id: {user_id}, text_len: {len(text or '')})")

        extracted_items = []
        if all_items:
            extracted_items = [i.model_dump() if hasattr(i, "model_dump") else i for i in all_items]
        elif unified and getattr(unified, "action", None) == "log_transaction" and unified.amount is not None:
            extracted_items = [unified.model_dump() if hasattr(unified, "model_dump") else unified]

        return {
            "status": status,
            "user_message": text,
            "bot_response": response_text,
            "action": getattr(unified, "action", None) if unified else None,
            "item_count": len(extracted_items),
            "items": extracted_items,
            "duration_seconds": round(duration, 3)
        }
