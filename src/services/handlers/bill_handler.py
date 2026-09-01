import logging
import datetime
import html
import re
from typing import Optional
from uuid import UUID
from sqlmodel import Session, select

from src.core.encryption import EncryptionService
from src.db.session import engine
from src.db.models import Transaction, ScheduledBill, User
from src.services.handlers.transaction_handler import format_currency, create_logged_task
from src.services.handlers.notion_handler import safe_mirror_to_notion

logger = logging.getLogger(__name__)


def check_and_settle_bill(
    family_id: UUID,
    tx_concept: str,
    tx_amount: float,
    tx_currency: str,
    tx_id: UUID,
    user_id: Optional[UUID] = None,
    encryption_service: Optional[EncryptionService] = None,
    session_factory=Session
) -> Optional[tuple[str, str]]:
    """
    Inspects pending ScheduledBills for the family.
    If a pending bill matches the transaction concept,
    marks the bill as 'paid' linked to tx_id, and returns (matched_concept, remaining_pending_str).
    Prioritizes bills created by/assigned to user_id.
    """
    enc_service = encryption_service or EncryptionService()
    with session_factory(engine) as session:
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
            dec_concept = enc_service.decrypt(b.concept)
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
            amt_str = enc_service.decrypt(rb.amount)
            if amt_str:
                parts = amt_str.strip().split()
                try:
                    a = float(parts[0])
                    c = parts[1].upper() if len(parts) > 1 else "USD"
                    rem_totals[c] = rem_totals.get(c, 0.0) + a
                except (ValueError, IndexError):
                    pass

        if rem_totals:
            rem_str = " + ".join([format_currency(amt, curr) for curr, amt in rem_totals.items()])
        else:
            rem_str = "$0"

        return matched_concept, rem_str


def settle_bill_without_amount(
    family_id: UUID,
    user_uuid: UUID,
    raw_text: str,
    is_spanish: bool,
    encryption_service: Optional[EncryptionService] = None,
    session_factory=Session
) -> Optional[str]:
    """
    Settles a pending scheduled bill when the user sends a payment claim without an amount
    (e.g., "Pagué la tarjeta visa", "Visa card paid").
    Prioritizes bills created by/assigned to user_uuid, falling back to other family members' bills.
    """
    enc_service = encryption_service or EncryptionService()
    with session_factory(engine) as session:
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
            dec_cpt = enc_service.decrypt(b.concept) or ""
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

        dec_amount_str = enc_service.decrypt(matched_bill.amount) or "0.00 USD"
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
        session.refresh(new_tx)
        tx_id = new_tx.id

        user = session.get(User, user_uuid)
        user_display_name = (user.full_name or user.username or "User") if user else "User"

    # Dispatch Notion mirror
    try:
        coro = safe_mirror_to_notion(
            family_id=family_id,
            amount=amt,
            currency=curr,
            concept=matched_concept,
            category=category,
            timestamp=now_dt,
            user_name=user_display_name,
            transaction_id=tx_id,
            tx_type="expense"
        )
        try:
            create_logged_task(coro, name="mirror_to_notion")
        except Exception:
            coro.close()
            raise
    except Exception as e:
        logger.warning(f"Could not dispatch Notion mirror task for settled bill: {e}")

    # Calculate remaining pending total for family
    with session_factory(engine) as session:
        remaining_bills = session.exec(
            select(ScheduledBill).where(
                ScheduledBill.family_id == family_id,
                ScheduledBill.status == "pending"
            )
        ).all()

        rem_totals = {}
        for rb in remaining_bills:
            amt_str = enc_service.decrypt(rb.amount)
            if amt_str:
                parts = amt_str.strip().split()
                try:
                    a = float(parts[0])
                    c = parts[1].upper() if len(parts) > 1 else "USD"
                    rem_totals[c] = rem_totals.get(c, 0.0) + a
                except (ValueError, IndexError):
                    pass

        if rem_totals:
            rem_str = " + ".join([format_currency(a_val, c_val) for c_val, a_val in rem_totals.items()])
        else:
            rem_str = "$0"

    fmt_paid = format_currency(amt, curr)
    if is_spanish:
        msg = (
            f"✅ <b>Factura registrada como pagada:</b>\n"
            f"• 💳 <b>{html.escape(matched_concept)}</b> ({fmt_paid})\n\n"
            f"<i>Se guardó como gasto en tu historial.</i>\n"
            f"📌 <b>Pendiente por pagar este mes:</b> {rem_str}"
        )
    else:
        msg = (
            f"✅ <b>Bill marked as paid:</b>\n"
            f"• 💳 <b>{html.escape(matched_concept)}</b> ({fmt_paid})\n\n"
            f"<i>Recorded as an expense in your history.</i>\n"
            f"📌 <b>Remaining pending bills:</b> {rem_str}"
        )
    return msg


def get_overdue_bills_reminder(
    family_id: UUID,
    is_spanish: bool = False,
    encryption_service: Optional[EncryptionService] = None,
    ref_time: Optional[datetime.datetime] = None,
    session_factory=Session
) -> str:
    """
    Checks if there are pending scheduled bills for the family due on or before today + 2 days.
    If so, returns a formatted reminder block to append to transaction responses.
    """
    enc_service = encryption_service or EncryptionService()
    reference_time = ref_time or datetime.datetime.now(datetime.timezone.utc)
    cutoff = reference_time + datetime.timedelta(days=2)

    with session_factory(engine) as session:
        pending_bills = session.exec(
            select(ScheduledBill).where(
                ScheduledBill.family_id == family_id,
                ScheduledBill.status == "pending"
            ).order_by(ScheduledBill.due_date.asc())
        ).all()

        if not pending_bills:
            return ""

        due_or_overdue = []
        for b in pending_bills:
            if b.due_date:
                b_due = b.due_date if b.due_date.tzinfo else b.due_date.replace(tzinfo=datetime.timezone.utc)
                if b_due <= cutoff:
                    due_or_overdue.append(b)

        if not due_or_overdue:
            return ""

        lines = []
        if is_spanish:
            lines.append("⚠️ <b>Recordatorio de Vencimientos:</b>\n<i>Tienes facturas programadas pendientes de pago:</i>")
            for b in due_or_overdue:
                dec_cpt = enc_service.decrypt(b.concept) or "Factura"
                amt_str = enc_service.decrypt(b.amount) or "0 USD"
                parts = amt_str.split()
                amt = float(parts[0]) if parts else 0.0
                curr = parts[1].upper() if len(parts) > 1 else "USD"
                fmt_amt = format_currency(amt, curr)
                due_fmt = b.due_date.strftime("%d/%m")
                status_note = "Venció el" if b.due_date.date() < reference_time.date() else "Vence el"
                lines.append(f"• 💳 <b>{html.escape(dec_cpt)}</b> ({fmt_amt}) — {status_note} {due_fmt}")
            lines.append('\n👉 <i>Si ya pagaste alguna, solo dime "Pagué [nombre]" (ej: "Pagué la visa") para registrarla.</i>')
        else:
            lines.append("⚠️ <b>Upcoming / Due Bills Reminder:</b>\n<i>You have pending scheduled bills:</i>")
            for b in due_or_overdue:
                dec_cpt = enc_service.decrypt(b.concept) or "Bill"
                amt_str = enc_service.decrypt(b.amount) or "0 USD"
                parts = amt_str.split()
                amt = float(parts[0]) if parts else 0.0
                curr = parts[1].upper() if len(parts) > 1 else "USD"
                fmt_amt = format_currency(amt, curr)
                due_fmt = b.due_date.strftime("%b %d")
                status_note = "Was due on" if b.due_date.date() < reference_time.date() else "Due on"
                lines.append(f"• 💳 <b>{html.escape(dec_cpt)}</b> ({fmt_amt}) — {status_note} {due_fmt}")
            lines.append('\n👉 <i>If you already paid any, simply tell me "Paid [name]" (e.g. "Paid the visa") to record it.</i>')

        return "\n".join(lines)
