import time
import logging
import datetime
import asyncio
import re
import html
from collections import defaultdict
from typing import Optional
from uuid import UUID
from sqlmodel import Session, select
from sqlalchemy import update as sa_update

from src.core.config import settings
from src.core.encryption import EncryptionService
from src.db.session import engine
from src.db.models import User, Transaction, Family, ScheduledBill
from src.services.whisper_service import WhisperService
from src.services.extraction import ExtractionService, UnifiedResult
from src.services.telegram_service import TelegramService
from src.services.query import QueryService, ParsedQueryIntent
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
    _user_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

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
        """
        Inspects pending ScheduledBills for the family.
        If a pending bill matches the transaction concept,
        marks the bill as 'paid' linked to tx_id, and returns (matched_concept, remaining_pending_str).
        Prioritizes bills created by/assigned to user_id.
        """
        with Session(engine) as session:
            pending_bills = session.exec(
                select(ScheduledBill).where(
                    ScheduledBill.family_id == family_id,
                    ScheduledBill.status == "pending"
                )
            ).all()

            if not pending_bills:
                return None

            def _norm(s: str) -> str:
                s = re.sub(r'\b(?:pagu[ée]|abon[ée]|paid|settled|cancel[ée])\b', '', s, flags=re.IGNORECASE)
                s = re.sub(r'\b(?:la|el|los|las|the|de|del|of|por|for|mi|my|tarjeta|card)\b', '', s, flags=re.IGNORECASE)
                s = re.sub(r'[\$€£]?\s*\b\d+(?:[.,]\d+)?\b(?:\s*[a-zA-Z]{3})?', '', s)
                s = re.sub(r'[^\w\s]', ' ', s)
                return " ".join(s.lower().split())

            clean_tx = _norm(tx_concept)
            tx_tokens = set(clean_tx.split())

            candidates = []
            for b in pending_bills:
                if not hasattr(b, "concept") or not b.concept:
                    continue
                dec_concept = self.encryption_service.decrypt(b.concept)
                if not dec_concept:
                    continue
                clean_b = _norm(dec_concept)
                b_tokens = set(clean_b.split())

                if clean_tx and clean_b:
                    if (clean_b in clean_tx) or (clean_tx in clean_b) or (tx_tokens and tx_tokens.issubset(b_tokens)) or (b_tokens and b_tokens.issubset(tx_tokens)) or (tx_tokens & b_tokens):
                        score = len(tx_tokens & b_tokens)
                        if clean_b in clean_tx or clean_tx in clean_b:
                            score += 5
                        if user_id is not None and b.user_id == user_id:
                            score += 10
                        candidates.append((score, b, dec_concept))

            if not candidates:
                return None

            candidates.sort(key=lambda x: x[0], reverse=True)
            best_score, matched_bill, matched_concept = candidates[0]

            matched_bill.status = "paid"
            matched_bill.paid_transaction_id = tx_id
            session.add(matched_bill)
            session.commit()

            # Calculate remaining pending total for this month
            remaining_bills = session.exec(
                select(ScheduledBill).where(
                    ScheduledBill.family_id == family_id,
                    ScheduledBill.status == "pending"
                )
            ).all()

            rem_totals = {}
            for rb in remaining_bills:
                amt_str = self.encryption_service.decrypt(rb.amount)
                if amt_str:
                    parts = amt_str.strip().split()
                    try:
                        a = float(parts[0])
                        c = parts[1].upper() if len(parts) > 1 else "USD"
                        rem_totals[c] = rem_totals.get(c, 0.0) + a
                    except (ValueError, IndexError):
                        pass

            if rem_totals:
                rem_str = " + ".join([_format_currency(amt, curr) for curr, amt in rem_totals.items()])
            else:
                rem_str = "$0"

            return matched_concept, rem_str

    def _settle_bill_without_amount(
        self,
        family_id: UUID,
        user_uuid: UUID,
        raw_text: str,
        is_spanish: bool
    ) -> Optional[str]:
        """
        Settles a pending scheduled bill when the user sends a payment claim without an amount
        (e.g., "Pagué la tarjeta visa", "Visa card paid").
        Prioritizes bills created by/assigned to user_uuid, falling back to other family members' bills.
        """
        with Session(engine) as session:
            pending_bills = session.exec(
                select(ScheduledBill).where(
                    ScheduledBill.family_id == family_id,
                    ScheduledBill.status == "pending"
                )
            ).all()

            if not pending_bills:
                return None

            def _norm(s: str) -> str:
                s = re.sub(r'\b(?:pagu[ée]|abon[ée]|paid|settled|cancel[ée]|liquid[ée]|pay)\b', '', s, flags=re.IGNORECASE)
                s = re.sub(r'\b(?:la|el|los|las|the|de|del|of|por|for|mi|my|tarjeta|card)\b', '', s, flags=re.IGNORECASE)
                s = re.sub(r'[\$€£]?\s*\b\d+(?:[.,]\d+)?\b(?:\s*[a-zA-Z]{3})?', '', s)
                s = re.sub(r'[^\w\s]', ' ', s)
                return " ".join(s.lower().split())

            clean_input = _norm(raw_text)
            input_tokens = set(clean_input.split())

            if not clean_input and not input_tokens:
                return None

            candidates = []
            for b in pending_bills:
                if not hasattr(b, "concept") or not b.concept:
                    continue
                dec_cpt = self.encryption_service.decrypt(b.concept) or ""
                clean_b = _norm(dec_cpt)
                b_tokens = set(clean_b.split())

                if clean_input and clean_b:
                    if (clean_b in clean_input) or (clean_input in clean_b) or (input_tokens and input_tokens.issubset(b_tokens)) or (b_tokens and b_tokens.issubset(input_tokens)) or (input_tokens & b_tokens):
                        score = len(input_tokens & b_tokens)
                        if clean_b in clean_input or clean_input in clean_b:
                            score += 5
                        if b.user_id == user_uuid:
                            score += 10
                        candidates.append((score, b, dec_cpt))

            if not candidates:
                return None

            candidates.sort(key=lambda x: x[0], reverse=True)
            best_score, matched_bill, matched_concept = candidates[0]

            dec_amount_str = self.encryption_service.decrypt(matched_bill.amount) or "0.00 USD"
            parts = dec_amount_str.strip().split()
            amt = float(parts[0]) if parts else 0.0
            curr = parts[1].upper() if len(parts) > 1 else "USD"
            category = matched_bill.category or "Rent/Bills"

            now_dt = datetime.datetime.now(datetime.timezone.utc)
            new_tx = Transaction(
                user_id=user_uuid,
                family_id=family_id,
                amount=matched_bill.amount,
                concept=matched_bill.concept,
                category=category,
                type="expense",
                timestamp=now_dt
            )
            session.add(new_tx)
            session.flush()

            matched_bill.status = "paid"
            matched_bill.paid_transaction_id = new_tx.id
            session.add(matched_bill)
            session.commit()

            tx_id = new_tx.id

        # Dispatch Notion mirror
        try:
            user_info = self._get_user_info(user_uuid)
            create_logged_task(self._safe_mirror_to_notion(
                family_id=family_id,
                amount=amt,
                currency=curr,
                concept=matched_concept,
                category=category,
                timestamp=now_dt,
                user_name=user_info.get("display_name", "User"),
                transaction_id=tx_id,
                tx_type="expense"
            ), name="mirror_to_notion")
        except Exception as e:
            logger.warning(f"Could not dispatch Notion mirror task for settled bill: {e}")

        # Calculate remaining pending total for family
        with Session(engine) as session:
            remaining_bills = session.exec(
                select(ScheduledBill).where(
                    ScheduledBill.family_id == family_id,
                    ScheduledBill.status == "pending"
                )
            ).all()

            rem_totals = {}
            for rb in remaining_bills:
                amt_str = self.encryption_service.decrypt(rb.amount)
                if amt_str:
                    parts = amt_str.strip().split()
                    try:
                        a = float(parts[0])
                        c = parts[1].upper() if len(parts) > 1 else "USD"
                        rem_totals[c] = rem_totals.get(c, 0.0) + a
                    except (ValueError, IndexError):
                        pass

            rem_str = " + ".join([_format_currency(a, c) for c, a in rem_totals.items()]) if rem_totals else "$0"

        formatted_amt = _format_currency(amt, curr)
        if is_spanish:
            return (
                f"✅ <b>¡Marcado como pagado!</b>\n"
                f"💳 <b>{html.escape(matched_concept)}</b> ({formatted_amt}) registrado en tus gastos.\n\n"
                f"⏳ Restante pendiente este mes: <b>{rem_str}</b>"
            )
        else:
            return (
                f"✅ <b>Marked as paid!</b>\n"
                f"💳 <b>{html.escape(matched_concept)}</b> ({formatted_amt}) recorded in your expenses.\n\n"
                f"⏳ Remaining pending this month: <b>{rem_str}</b>"
            )

    def _get_overdue_bills_reminder(
        self,
        family_id: UUID,
        reference_time: datetime.datetime,
        is_spanish: bool
    ) -> Optional[str]:
        """Checks for scheduled bills in the current month with due_date <= reference_time and returns a reminder block."""
        with Session(engine) as session:
            start_of_month = reference_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if reference_time.month == 12:
                next_month = reference_time.replace(year=reference_time.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            else:
                next_month = reference_time.replace(month=reference_time.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)

            bills = session.exec(
                select(ScheduledBill).where(
                    ScheduledBill.family_id == family_id,
                    ScheduledBill.status == "pending",
                    ScheduledBill.due_date < next_month
                ).order_by(ScheduledBill.due_date.asc())
            ).all()

            if not bills:
                return None

            # Check if any bills are due today or overdue (or due in next 2 days)
            due_or_overdue = [b for b in bills if b.due_date.date() <= (reference_time + datetime.timedelta(days=2)).date()]
            if not due_or_overdue:
                due_or_overdue = bills[:3]

            lines = []
            if is_spanish:
                lines.append("⚠️ <b>Recordatorio de Vencimientos:</b>\n<i>Tienes facturas programadas pendientes de pago:</i>")
                for b in due_or_overdue:
                    dec_cpt = self.encryption_service.decrypt(b.concept) or "Factura"
                    amt_str = self.encryption_service.decrypt(b.amount) or "0 USD"
                    parts = amt_str.split()
                    amt = float(parts[0]) if parts else 0.0
                    curr = parts[1].upper() if len(parts) > 1 else "USD"
                    fmt_amt = _format_currency(amt, curr)
                    due_fmt = b.due_date.strftime("%d/%m")
                    status_note = "Venció el" if b.due_date.date() < reference_time.date() else "Vence el"
                    lines.append(f"• 💳 <b>{html.escape(dec_cpt)}</b> ({fmt_amt}) — {status_note} {due_fmt}")
                lines.append('\n👉 <i>Si ya pagaste alguna, solo dime "Pagué [nombre]" (ej: "Pagué la visa") para registrarla.</i>')
            else:
                lines.append("⚠️ <b>Upcoming / Due Bills Reminder:</b>\n<i>You have pending scheduled bills:</i>")
                for b in due_or_overdue:
                    dec_cpt = self.encryption_service.decrypt(b.concept) or "Bill"
                    amt_str = self.encryption_service.decrypt(b.amount) or "0 USD"
                    parts = amt_str.split()
                    amt = float(parts[0]) if parts else 0.0
                    curr = parts[1].upper() if len(parts) > 1 else "USD"
                    fmt_amt = _format_currency(amt, curr)
                    due_fmt = b.due_date.strftime("%b %d")
                    status_note = "Was due on" if b.due_date.date() < reference_time.date() else "Due on"
                    lines.append(f"• 💳 <b>{html.escape(dec_cpt)}</b> ({fmt_amt}) — {status_note} {due_fmt}")
                lines.append('\n👉 <i>If you already paid any, simply tell me "Paid [name]" (e.g. "Paid the visa") to record it.</i>')

            return "\n".join(lines)

            return None

    def _get_monthly_cash_flow_snapshot(self, family_id: UUID, target_date: datetime.datetime, primary_currency: str = "USD") -> dict:
        """
        Queries and decrypts all transactions for the given family in the calendar month of target_date.
        Calculates Total In, Total Out, Net Savings, and Savings Rate percentage for the specified currency.
        """
        start_of_month = target_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if target_date.month == 12:
            next_month = target_date.replace(year=target_date.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            next_month = target_date.replace(month=target_date.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)

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
                    curr = parts[1].upper() if len(parts) > 1 else (primary_currency or "USD").upper()
                    if curr == (primary_currency or "USD").upper():
                        tx_type = getattr(tx, "tx_type", getattr(tx, "type", "expense")) or "expense"
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
        """
        Searches recent transactions for the user matching optional criteria.
        If no criteria specified, returns the most recent transaction.
        """
        recent_txs = session.exec(
            select(Transaction)
            .where(Transaction.user_id == user_uuid)
            .order_by(Transaction.timestamp.desc())
            .limit(10)
            .with_for_update()
        ).all()

        if not recent_txs:
            return None

        if target_amount is None and not target_currency and not target_concept:
            return recent_txs[0]

        target_curr_norm = target_currency.upper() if target_currency else None
        target_concept_norm = target_concept.lower().strip() if target_concept else None

        for tx in recent_txs:
            dec_amt_str = self.encryption_service.decrypt(tx.amount)
            dec_concept = self.encryption_service.decrypt(tx.concept) or ""
            if not dec_amt_str:
                continue
            parts = dec_amt_str.strip().split()
            a = float(parts[0]) if parts else 0.0
            c = parts[1].upper() if len(parts) > 1 else "USD"

            matches = True
            if target_amount is not None and abs(a - target_amount) > 0.01:
                matches = False
            if target_curr_norm and c != target_curr_norm:
                matches = False
            if target_concept_norm and target_concept_norm not in dec_concept.lower():
                matches = False

            if matches:
                return tx

        # If strict match didn't find anything, try matching on amount alone if specified
        if target_amount is not None:
            for tx in recent_txs:
                dec_amt_str = self.encryption_service.decrypt(tx.amount)
                if not dec_amt_str:
                    continue
                parts = dec_amt_str.strip().split()
                a = float(parts[0]) if parts else 0.0
                if abs(a - target_amount) <= 0.01:
                    return tx

        # Fallback to the latest transaction
        return recent_txs[0]

    def _handle_transaction_undo(self, user_uuid: UUID, parsed_query: Optional[ParsedQueryIntent] = None) -> str:
        """Removes a recent transaction logged by the user, recalculating monthly balance."""
        with Session(engine) as session:
            t_amt = parsed_query.target_amount if parsed_query else None
            t_curr = parsed_query.target_currency if parsed_query else None
            t_cpt = parsed_query.target_concept if parsed_query else None

            tx = self._find_target_transaction(
                session=session,
                user_uuid=user_uuid,
                target_amount=t_amt,
                target_currency=t_curr,
                target_concept=t_cpt
            )
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

            counterpart = None
            if category == "Exchange":
                recent_exchange_txs = session.exec(
                    select(Transaction)
                    .where(
                        Transaction.user_id == user_uuid,
                        Transaction.category == "Exchange",
                        Transaction.id != tx.id
                    )
                    .order_by(Transaction.timestamp.desc())
                    .limit(5)
                ).all()
                for cand in recent_exchange_txs:
                    if abs((cand.timestamp - tx_time).total_seconds()) <= 15:
                        counterpart = cand
                        break

            counterpart_info = None
            if counterpart:
                c_dec_amount = self.encryption_service.decrypt(counterpart.amount) or "0.00 USD"
                c_dec_concept = self.encryption_service.decrypt(counterpart.concept) or "Transaction"
                c_parts = c_dec_amount.strip().split()
                c_amt = float(c_parts[0]) if c_parts else 0.0
                c_curr = c_parts[1].upper() if len(c_parts) > 1 else "USD"
                c_type = getattr(counterpart, "tx_type", getattr(counterpart, "type", "income")) or "income"
                counterpart_info = {
                    "amount": c_amt,
                    "currency": c_curr,
                    "type": c_type,
                    "concept": c_dec_concept,
                    "notion_page_id": counterpart.notion_page_id
                }
                session.delete(counterpart)

            session.delete(tx)
            session.commit()

        if notion_page_id:
            try:
                create_logged_task(self._safe_archive_notion_page(family_id, notion_page_id), name="archive_notion_page")
            except Exception as e:
                logger.warning(f"Could not dispatch Notion archive task: {e}")

        if counterpart_info and counterpart_info.get("notion_page_id"):
            try:
                create_logged_task(self._safe_archive_notion_page(family_id, counterpart_info["notion_page_id"]), name="archive_counterpart_notion_page")
            except Exception as e:
                logger.warning(f"Could not dispatch counterpart Notion archive task: {e}")

        snapshot = self._get_monthly_cash_flow_snapshot(family_id, tx_time, curr)

        icon = "💰" if old_type == "income" else "💸"
        sign = "+" if old_type == "income" else "-"
        formatted_amt = _format_currency(amt, curr, show_sign=False)
        formatted_in = _format_currency(snapshot["total_in"], curr, show_sign=False)
        formatted_out = _format_currency(snapshot["total_out"], curr, show_sign=False)
        formatted_net = _format_currency(snapshot["net_savings"], curr, show_sign=True)
        pct_str = f" ({snapshot['savings_pct']}%)" if snapshot["total_in"] > 0 else ""

        safe_concept = html.escape(dec_concept)
        safe_category = html.escape(category)
        has_target = bool(parsed_query and (parsed_query.target_amount or parsed_query.target_currency or parsed_query.target_concept))

        if counterpart_info:
            c_icon = "💰" if counterpart_info["type"] == "income" else "💸"
            c_sign = "+" if counterpart_info["type"] == "income" else "-"
            c_formatted = _format_currency(counterpart_info["amount"], counterpart_info["currency"], show_sign=False)
            return (
                f"🗑️ <b>Removed currency exchange:</b>\n"
                f"• {icon} {sign}{formatted_amt} ({safe_category} - {safe_concept})\n"
                f"• {c_icon} {c_sign}{c_formatted} ({safe_category} - {html.escape(counterpart_info['concept'])})\n\n"
                f"📊 <b>Updated {snapshot['month_name']} Balance ({curr}):</b>\n"
                f"• Total In: {formatted_in}\n"
                f"• Total Out: {formatted_out}\n"
                f"• Net Savings: {formatted_net}{pct_str}"
            )

        title = "🗑️ <b>Removed transaction:</b>\n" if has_target else "🗑️ <b>Removed latest transaction:</b>\n"

        return (
            f"{title}"
            f"• {icon} {sign}{formatted_amt} ({safe_category} - {safe_concept})\n\n"
            f"📊 <b>Updated {snapshot['month_name']} Balance:</b>\n"
            f"• Total In: {formatted_in}\n"
            f"• Total Out: {formatted_out}\n"
            f"• Net Savings: {formatted_net}{pct_str}"
        )

    def _handle_transaction_correction(self, user_uuid: UUID, parsed_query: ParsedQueryIntent) -> str:
        """Modifies fields on the user's targeted or latest transaction and updates Notion / cash flow snapshot."""
        with Session(engine) as session:
            tx = self._find_target_transaction(
                session=session,
                user_uuid=user_uuid,
                target_amount=parsed_query.target_amount,
                target_currency=parsed_query.target_currency,
                target_concept=parsed_query.target_concept
            )
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

        safe_concept = html.escape(new_concept)
        safe_cat = html.escape(new_cat)
        has_target = bool(parsed_query and (parsed_query.target_amount or parsed_query.target_currency or parsed_query.target_concept))
        title = "✏️ <b>Updated transaction:</b>\n" if has_target else "✏️ <b>Updated latest transaction:</b>\n"

        return (
            f"{title}"
            f"• {icon} {sign}{formatted_amt} ({safe_cat} - {safe_concept}){type_note}\n\n"
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

        if getattr(parsed_query, "intent", None) == "delete_account" and raw_text.strip() == "CONFIRM DELETE":
            account_service = AccountService()
            success = await account_service.delete_account(user_uuid)
            if success:
                return "✅ Your account and all associated transaction records have been permanently deleted from our database. Thank you for using Clanomy! If you ever wish to return, simply send /start."
            return "Failed to delete account. Please try again later."

        elif getattr(parsed_query, "intent", None) == "delete_account":
            return "⚠️ Are you sure you want to permanently delete your account and all associated financial records? This action is irreversible.\n\nTo confirm, please reply with: <b>CONFIRM DELETE</b>"

        elif parsed_query.intent == "export_data":
            family_id = await asyncio.to_thread(self._get_user_family_id, user_uuid)
            ALLOWED_EXPORT_FORMATS = {"csv", "json"}
            raw_format = (parsed_query.export_format or "csv").lower()
            export_format = raw_format if raw_format in ALLOWED_EXPORT_FORMATS else "csv"
            export_service = ExportService()
            await export_service.export_and_send(family_id, chat_id, export_format)
            return None

        elif parsed_query.intent == "undo_last":
            return await asyncio.to_thread(self._handle_transaction_undo, user_uuid, parsed_query)

        elif parsed_query.intent == "edit_last":
            return await asyncio.to_thread(self._handle_transaction_correction, user_uuid, parsed_query)

        elif parsed_query.intent == "leave_family":
            family_service = FamilyService()
            success, msg, _ = await asyncio.to_thread(family_service.leave_family, user_uuid)
            return msg

        elif parsed_query.intent == "remove_member":
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
            return msg

        elif parsed_query.intent in ["spending_summary", "query_spending", "income_summary", "query_income", "earnings_summary", "net_cash_flow", "net_balance", "cash_flow_summary"]:
            family_service = FamilyService()
            family_info = await asyncio.to_thread(family_service.get_family_info, user_uuid)
            family_id = family_info["id"]
            family_currency = await asyncio.to_thread(family_service.get_family_default_currency, family_id) if hasattr(family_service, "get_family_default_currency") else "USD"
            
            family_name = family_info["name"] if parsed_query.scope == "family" else None
            member_names = [m.get("full_name") or m.get("username") or "User" for m in family_info["members"]] if parsed_query.scope == "family" else None
            
            user_name = None
            reference_time = datetime.datetime.now(datetime.timezone.utc)
            query_service = QueryService()

            if parsed_query.intent in ["income_summary", "query_income", "earnings_summary"]:
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
            elif parsed_query.intent in ["net_cash_flow", "net_balance", "cash_flow_summary"]:
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
            if parsed_query.intent in ["spending_summary", "query_spending", "net_cash_flow", "net_balance", "cash_flow_summary"]:
                if parsed_query.timeframe in ["this_month", "all_time", "current_month"] or not parsed_query.timeframe:
                    is_spanish = any(w in raw_lower for w in ["como", "cómo", "venimos", "mes", "gastos", "resumen", "balance", "pesos"])
                    overdue_block = await asyncio.to_thread(self._get_overdue_bills_reminder, family_id, reference_time, is_spanish)
                    if overdue_block:
                        summary_res += f"\n\n{overdue_block}"

            return summary_res

        elif parsed_query.intent == "upcoming_bills":
            family_id = await asyncio.to_thread(self._get_user_family_id, user_uuid)
            query_service = QueryService()
            return await query_service.get_upcoming_bills_summary(
                family_id=family_id,
                timeframe=parsed_query.timeframe or "this_month",
                raw_text=raw_text
            )

        elif parsed_query.intent == "create_family":
            family_service = FamilyService()
            name = parsed_query.family_name or "My Family"
            await asyncio.to_thread(family_service.create_family, user_uuid, name)
            safe_name = html.escape(name)
            return f"✅ Family group '{safe_name}' has been created! To invite others, just ask me to 'generate an invite link'."

        elif parsed_query.intent == "generate_invite":
            family_service = FamilyService()
            family_id = await asyncio.to_thread(self._get_user_family_id, user_uuid)
            telegram_service = TelegramService()
            bot_username = await telegram_service.get_bot_username()
            try:
                invite, link = await asyncio.to_thread(family_service.create_invite, family_id, user_uuid, bot_username)
                return f"🔗 Here is your family invite link:\n\n{link}\n\n⏳ This invite link will expire in 48 hours."
            except PlanLimitExceededError:
                return (
                    "⚠️ <b>Family Invites Require Family Pro</b>\n\n"
                    "Your workspace is currently on the <b>Solo Pro</b> tier (1 user limit). "
                    "To add family members and share a household ledger, please upgrade to <b>Family Pro</b> using /upgrade."
                )
            except ValueError as ve:
                return f"⚠️ {ve}"

        elif parsed_query.intent == "family_info":
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
            return (
                f"👪 <b>Family Workspace: {info['name']}</b>\n"
                f"📋 <b>Plan:</b> {plan_desc}\n"
                f"📊 <b>Monthly Logs:</b> {info.get('monthly_tx_count', 0)}\n\n"
                f"<b>Members:</b>\n{members_formatted}\n\n"
                f"<b>Total Transactions:</b> {info['transactions_count']}\n"
                f"<b>Active Invites:</b> {info['active_invites_count']}"
            )

        elif parsed_query.intent == "notion_manage":
            family_id = await asyncio.to_thread(self._get_user_family_id, user_uuid)
            with Session(engine) as session:
                family = session.get(Family, family_id)
                notion_service = NotionService(session)
                from src.services.subscription_service import has_unlimited_access
                if family and not has_unlimited_access(family):
                    return (
                        "⭐️ <b>Notion Mirroring is a Pro Feature</b>\n\n"
                        "Real-time Notion database synchronization is available on <b>Solo Pro</b> and <b>Family Pro</b> plans.\n\n"
                        "Type /upgrade to connect your Notion database."
                    )
                elif raw_lower == "/notion" or raw_lower == "connect notion":
                    return (
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
                        return "Please provide the secret token. Usage: <code>/notion connect &lt;your_secret_token&gt;</code>"
                    token = parts[2]
                    db_id = parts[3] if len(parts) > 3 else None
                    if message_id:
                        ts = TelegramService()
                        create_logged_task(ts.delete_message(chat_id, message_id), name="delete_secret_token_message")

                    is_valid = await notion_service.validate_token(token)
                    if not is_valid:
                        return "⚠️ <b>Invalid Token!</b> Please check your Integration Secret and try again.\n\n🔒 <i>Your secret token message was automatically deleted for security.</i>"
                    elif db_id:
                        try:
                            res = await notion_service.connect_database(family_id, token, db_id)
                            return f"✅ <b>Notion Workspace Connected!</b>\n\n📁 <b>Database:</b> {res['database_name']}\n🆔 <b>ID:</b> <code>{res['database_id']}</code>\n\nYour transactions are now linked and ready for automatic mirroring!\n\n🔒 <i>Your secret token message was automatically deleted for security.</i>"
                        except Exception as e:
                            logger.error(f"Failed to connect database: {e}")
                            return "⚠️ <b>Failed to connect database.</b> Please verify the database ID and try again.\n\n🔒 <i>Your secret token message was automatically deleted for security.</i>"
                    else:
                        dbs = await notion_service.search_databases(token)
                        if not dbs:
                            return (
                                "⚠️ <b>No databases found!</b>\n"
                                "Your Notion token is valid, but no databases have been shared with this integration yet.\n\n"
                                "Please open your Notion database, click <b>•••</b> -> <b>Add connections</b>, select your integration, and run <code>/notion connect &lt;token&gt;</code> again.\n\n"
                                "🔒 <i>Your secret token message was automatically deleted for security.</i>"
                            )
                        family = session.get(Family, family_id)
                        family.notion_api_key = self.encryption_service.encrypt(token)
                        family.notion_database_id = None
                        family.notion_database_name = None
                        session.add(family)
                        session.commit()
                        
                        db_list = "\n".join([f"{i+1}. 📊 <b>{db['title']}</b> (ID: <code>{db['id']}</code>)" for i, db in enumerate(dbs)])
                        return (
                            f"📋 <b>Found {len(dbs)} Notion Database(s):</b>\n\n{db_list}\n\n"
                            "Reply with: <code>/notion setdb &lt;number or ID&gt;</code> (e.g. <code>/notion setdb 1</code>)\n\n"
                            "🔒 <i>Your secret token message was automatically deleted for security.</i>"
                        )
                elif raw_lower.startswith("/notion setdb") or raw_lower.startswith("notion setdb"):
                    if len(parts) < 3:
                        return "Please provide the database number or ID. Usage: <code>/notion setdb &lt;number or ID&gt;</code>"
                    target = parts[2]
                    status = notion_service.get_family_notion_status(family_id)
                    if not status["has_valid_token"]:
                        return "No Notion token found. Please run <code>/notion connect &lt;token&gt;</code> first."
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
                        return "Database not found."
                    res = await notion_service.connect_database(family_id, token, selected_db["id"], selected_db["title"])
                    return f"✅ <b>Notion Workspace Connected!</b>\n\n📁 <b>Database:</b> {res['database_name']}\n🆔 <b>ID:</b> <code>{res['database_id']}</code>\n\nYour transactions are now linked and ready for automatic mirroring!"
                elif raw_lower == "/notion status" or raw_lower == "notion status":
                    status = notion_service.get_family_notion_status(family_id)
                    if status["is_connected"]:
                        dt_str = status['connected_at'].strftime('%Y-%m-%d %H:%M UTC') if status.get('connected_at') else "N/A"
                        return f"📊 <b>Notion Connection Status:</b> Connected ✅\n📁 <b>Target Database:</b> {status['database_name']}\n🆔 <b>Database ID:</b> <code>{status['database_id']}</code>\n📅 <b>Connected:</b> {dt_str}"
                    return "📊 <b>Notion Connection Status:</b> Not Connected ❌"
                elif raw_lower == "/notion disconnect" or raw_lower == "disconnect notion":
                    notion_service.disconnect_workspace(family_id)
                    return "🔌 <b>Notion Disconnected</b>\nYour Notion workspace connection has been removed. Transaction mirroring is now disabled."
                elif raw_lower == "/notion test" or raw_lower == "notion test":
                    status = notion_service.get_family_notion_status(family_id)
                    if not status["is_connected"]:
                        return "⚠️ <b>Notion is not connected.</b>\nPlease run <code>/notion</code> to connect your workspace first."
                    try:
                        res = await notion_service.test_connection_mirror(family_id)
                        if res:
                            return f"✅ <b>Notion Mirror Test Successful!</b>\nCreated test record in database: <b>{res['database_name']}</b>\n🔗 <a href=\"{res['page_url']}\">View in Notion</a>"
                        return "⚠️ <b>Test Failed:</b> Could not verify connection."
                    except Exception as e:
                        return f"⚠️ <b>Test Failed:</b> {e}"
                elif raw_lower == "/notion sync" or raw_lower == "notion sync":
                    status = notion_service.get_family_notion_status(family_id)
                    if status["is_connected"]:
                        res = await notion_service.sync_pending_transactions(family_id)
                        synced = res.get("synced", 0)
                        failed = res.get("failed", 0)
                        db_name = status.get("database_name", "Notion")
                        if synced > 0:
                            msg = f"✅ <b>Notion Sync Complete!</b>\nSuccessfully synchronized <b>{synced}</b> pending transaction(s) to <b>{db_name}</b>."
                            if failed > 0:
                                msg += f"\n\n⚠️ Could not sync {failed} transaction(s)."
                            return msg
                        elif synced == 0 and failed == 0:
                            return f"✅ <b>Notion Sync is Up to Date!</b>\nAll transactions are already synchronized with your Notion database <b>{db_name}</b>."
                        else:
                            return f"⚠️ <b>Notion Sync Failed:</b> Could not reach Notion API for {failed} transaction(s). The system will retry on your next sync or message."
                    return "⚠️ <b>Notion is not connected.</b>\nPlease run <code>/notion</code> to connect your workspace first."
                else:
                    return "Unknown Notion command."

        elif parsed_query.intent == "manage_currency":
            family_id = await asyncio.to_thread(self._get_user_family_id, user_uuid)
            family_service = FamilyService()
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
                    return (
                        f"✅ <b>Default Currency Updated to {new_curr}!</b>\n\n"
                        f"Any future expenses or income logged without specifying a currency (e.g. <i>\"spent 500 on lunch\"</i> or <i>\"300 pesos\"</i>) "
                        f"will now automatically default to <b>{new_curr}</b>."
                    )
                except ValueError as ve:
                    return f"⚠️ {ve}"
            else:
                curr = await asyncio.to_thread(family_service.get_family_default_currency, family_id)
                return (
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

        return "I couldn't process your request."

    async def orchestrate(self, user_id: str, text: Optional[str], audio_file_id: Optional[str], chat_id: int, message_id: Optional[int] = None):
        async with self._user_locks[str(user_id)]:
            await self._orchestrate_impl(user_id=user_id, text=text, audio_file_id=audio_file_id, chat_id=chat_id, message_id=message_id)

    async def _orchestrate_impl(self, user_id: str, text: Optional[str], audio_file_id: Optional[str], chat_id: int, message_id: Optional[int] = None):
        start_time = time.time()
        status = "success"
        response_text = ""
        
        try:
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
                    elif raw_text == "/leavefamily" or raw_lower in ["leave family", "leave the family", "leave group"]:
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
                        try:
                            family_id = await asyncio.to_thread(self._get_user_family_id, user_uuid)
                            family_service = FamilyService()
                            family_currency = await asyncio.to_thread(family_service.get_family_default_currency, family_id)
                        except Exception:
                            family_currency = "USD"

                        extraction_service = ExtractionService()
                        override_tx_time = None
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

                                    is_spanish = any(w in raw_lower for w in ["gastos", "fijos", "vencimiento", "vence", "prestamo", "préstamo", "tarjeta", "pesos", "pago", "cuentas", "facturas", "cambie", "cambié", "dolares", "dólares"])
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
                                            header = f"📋 <b>{len(txs)} Gasto(s) Registrado(s):</b>\n\n" if is_spanish else f"📋 <b>{len(txs)} Expense(s) Logged:</b>\n\n"
                                            parts.append(header)
                                            for t in txs:
                                                fmt_amt = _format_currency(t["amount"], t["currency"])
                                                parts.append(f"• 💸 <b>{html.escape(t['concept'])}:</b> {fmt_amt} ({html.escape(t['category'])})\n")

                                        if bills:
                                            tip = '\n\n💡 <i>Pregúntame "¿qué vence esta semana?" cuando quieras revisar tus vencimientos.</i>' if is_spanish else '\n\n💡 <i>Ask me "what bills are due this week?" whenever you want to check your upcoming obligations.</i>'
                                            parts.append(tip)

                                        response_text = "".join(parts)

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
                                except Exception as e:
                                    logger.error(f"Batch persistence failed for user {user_id}: {e}", exc_info=True)
                                    status = "error"
                                    response_text = "Failed to save transactions. Please try again later."

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

                                    try:
                                        user_info = await asyncio.to_thread(self._get_user_info, user_uuid)
                                        family_id = user_info["family_id"]
                                    except Exception as u_err:
                                        logger.warning(f"Failed to get user info: {u_err}")
                                        family_id = await asyncio.to_thread(self._get_user_family_id, user_uuid)
                                        user_info = {"display_name": "User"}

                                    date_str = ""
                                    if getattr(unified, "transaction_date", None):
                                        date_str = f" (logged for {transaction_time.strftime('%b %d, %Y')})"

                                    if tx_type == "income":
                                        snapshot = await asyncio.to_thread(
                                            self._get_monthly_cash_flow_snapshot,
                                            family_id=family_id,
                                            target_date=transaction_time,
                                            primary_currency=tx_currency
                                        )

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
