import logging
import datetime
import html
import re
import asyncio
from typing import Optional, Tuple, Dict, Any, List
from uuid import UUID
from sqlmodel import Session, select

from src.core.encryption import EncryptionService
from src.db.session import engine
from src.db.models import Transaction, ScheduledBill, User, Family
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


def build_bills_keyboard(
    bills: List[Any],
    page: int = 1,
    timeframe: str = "this_month",
    page_size: int = 4
) -> Optional[Dict[str, Any]]:
    """
    Builds a paginated Telegram inline keyboard for upcoming scheduled bills.
    Limits to page_size bills per page with Prev / Next pagination controls.
    """
    if not bills:
        return None

    total_bills = len(bills)
    total_pages = max(1, (total_bills + page_size - 1) // page_size)
    page_idx = max(0, min(page - 1, total_pages - 1))
    current_page_num = page_idx + 1

    start_idx = page_idx * page_size
    page_bills = bills[start_idx : start_idx + page_size]

    tf_code = "next" if "next" in (timeframe or "").lower() else "this"
    inline_keyboard: List[List[Dict[str, str]]] = []

    for b in page_bills:
        concept = getattr(b, "concept", "Bill") or "Bill"
        if len(concept) > 20:
            concept = concept[:18] + "…"
        amt = getattr(b, "amount", 0.0)
        curr = getattr(b, "currency", "USD")
        label = f"💳 {concept} ({format_currency(amt, curr)})"
        cb_data = f"bill_v:{b.id}:{current_page_num}:{tf_code}"
        inline_keyboard.append([{"text": label, "callback_data": cb_data}])

    if total_pages > 1:
        prev_p = total_pages if current_page_num == 1 else current_page_num - 1
        next_p = 1 if current_page_num == total_pages else current_page_num + 1
        nav_row = [
            {"text": "◀️ Prev", "callback_data": f"bills_p:{prev_p}:{tf_code}"},
            {"text": f"Page {current_page_num}/{total_pages}", "callback_data": "noop"},
            {"text": "Next ▶️", "callback_data": f"bills_p:{next_p}:{tf_code}"}
        ]
        inline_keyboard.append(nav_row)

    return {"inline_keyboard": inline_keyboard}


def build_bill_settlement_card(
    bill_id: UUID,
    family_id: UUID,
    encryption_service: Optional[EncryptionService] = None,
    return_page: int = 1,
    timeframe: str = "this_month",
    is_spanish: bool = False,
    session_factory=Session
) -> Tuple[str, Dict[str, Any]]:
    """
    Builds the detailed 2-option settlement card for a specific bill:
    - [Pay <amount> (No Change)]
    - [Pay Different Amount]
    - [Back to Bills]
    """
    enc_service = encryption_service or EncryptionService()
    tf_code = "next" if "next" in (timeframe or "").lower() else "this"

    with session_factory(engine) as session:
        bill = session.get(ScheduledBill, bill_id)
        if not bill or bill.family_id != family_id:
            not_found = "Factura no encontrada." if is_spanish else "Bill not found."
            return not_found, {"inline_keyboard": [[{"text": "🔙 Volver" if is_spanish else "🔙 Back", "callback_data": f"bills_p:{return_page}:{tf_code}"}]]}

        if bill.status != "pending":
            already_paid = "Esta factura ya fue pagada." if is_spanish else "This bill is already marked as paid."
            return already_paid, {"inline_keyboard": [[{"text": "🔙 Volver" if is_spanish else "🔙 Back", "callback_data": f"bills_p:{return_page}:{tf_code}"}]]}

        dec_cpt = enc_service.decrypt(bill.concept) or "Bill"
        amt_str = enc_service.decrypt(bill.amount) or "0 USD"
        parts = amt_str.split()
        amt = float(parts[0]) if parts else 0.0
        curr = parts[1].upper() if len(parts) > 1 else "USD"
        fmt_amt = format_currency(amt, curr)

        due_fmt = bill.due_date.strftime("%d/%m") if is_spanish else bill.due_date.strftime("%b %d") if bill.due_date else "N/A"
        cat = bill.category or "Rent/Bills"

    if is_spanish:
        card_text = (
            f"⚡ <b>Pagar Factura: {html.escape(dec_cpt)}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"• <b>Monto Registrado:</b> {fmt_amt}\n"
            f"• <b>Vencimiento:</b> {due_fmt}\n"
            f"• <b>Categoría:</b> {html.escape(cat)}\n\n"
            f"<i>¿Cómo deseas registrar este pago?</i>"
        )
        keyboard = {
            "inline_keyboard": [
                [{"text": f"✅ Pagar {fmt_amt} (Sin cambio)", "callback_data": f"bill_pay:{bill_id}:{tf_code}"}],
                [{"text": "✏️ Pagar Otro Monto", "callback_data": f"bill_edit:{bill_id}"}],
                [{"text": "🔙 Volver a Facturas", "callback_data": f"bills_p:{return_page}:{tf_code}"}],
            ]
        }
    else:
        card_text = (
            f"⚡ <b>Settle Bill: {html.escape(dec_cpt)}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"• <b>Recorded Amount:</b> {fmt_amt}\n"
            f"• <b>Due Date:</b> {due_fmt}\n"
            f"• <b>Category:</b> {html.escape(cat)}\n\n"
            f"<i>How would you like to settle this bill?</i>"
        )
        keyboard = {
            "inline_keyboard": [
                [{"text": f"✅ Pay {fmt_amt} (No Change)", "callback_data": f"bill_pay:{bill_id}:{tf_code}"}],
                [{"text": "✏️ Pay Different Amount", "callback_data": f"bill_edit:{bill_id}"}],
                [{"text": "🔙 Back to Bills", "callback_data": f"bills_p:{return_page}:{tf_code}"}],
            ]
        }

    return card_text, keyboard


def settle_bill_by_id(
    bill_id: UUID,
    user_id: UUID,
    family_id: UUID,
    override_amount: Optional[float] = None,
    override_currency: Optional[str] = None,
    is_spanish: bool = False,
    encryption_service: Optional[EncryptionService] = None,
    session_factory=Session
) -> Tuple[bool, str]:
    """
    Settles a ScheduledBill by its UUID:
    - Atomically updates status to 'paid'
    - Creates a Transaction linked to user_id
    - Links paid_transaction_id
    - Triggers Notion mirror task
    - Calculates remaining pending total
    - Returns (success, message)
    """
    enc_service = encryption_service or EncryptionService()
    now_dt = datetime.datetime.now(datetime.timezone.utc)

    with session_factory(engine) as session:
        bill = session.get(ScheduledBill, bill_id)
        if not bill or bill.family_id != family_id:
            msg = "Factura no encontrada." if is_spanish else "Bill not found."
            return False, msg

        if bill.status != "pending":
            msg = "Esta factura ya fue pagada." if is_spanish else "This bill is already marked as paid."
            return False, msg

        dec_concept = enc_service.decrypt(bill.concept) or "Bill"
        saved_amt_str = enc_service.decrypt(bill.amount) or "0 USD"
        parts = saved_amt_str.strip().split()
        saved_amt = float(parts[0]) if parts else 0.0
        saved_curr = parts[1].upper() if len(parts) > 1 else "USD"

        if override_amount is not None and override_amount > 0:
            actual_amt = float(override_amount)
            actual_curr = (override_currency or saved_curr).upper()
            enc_amt = enc_service.encrypt(f"{actual_amt:.2f} {actual_curr}")
            bill.amount = enc_amt
            is_changed = (actual_amt != saved_amt)
        else:
            actual_amt = saved_amt
            actual_curr = saved_curr
            enc_amt = bill.amount
            is_changed = False

        category = bill.category or "Rent/Bills"
        new_tx = Transaction(
            user_id=user_id,
            family_id=family_id,
            amount=enc_amt,
            concept=bill.concept,
            category=category,
            type="expense",
            timestamp=now_dt
        )
        session.add(new_tx)
        session.flush()

        bill.status = "paid"
        bill.paid_transaction_id = new_tx.id
        session.add(bill)
        session.commit()
        session.refresh(new_tx)
        tx_id = new_tx.id

        user = session.get(User, user_id)
        user_display_name = (user.full_name or user.username or "User") if user else "User"

    # Dispatch Notion mirror
    try:
        coro = safe_mirror_to_notion(
            family_id=family_id,
            amount=actual_amt,
            currency=actual_curr,
            concept=dec_concept,
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
        logger.warning(f"Could not dispatch Notion mirror task for settled bill {bill_id}: {e}")

    # Calculate remaining pending total
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
                p = amt_str.strip().split()
                try:
                    a = float(p[0])
                    c = p[1].upper() if len(p) > 1 else "USD"
                    rem_totals[c] = rem_totals.get(c, 0.0) + a
                except (ValueError, IndexError):
                    pass

        if rem_totals:
            rem_str = " + ".join([format_currency(a_val, c_val) for c_val, a_val in rem_totals.items()])
        else:
            rem_str = "$0"

    fmt_paid = format_currency(actual_amt, actual_curr)
    if is_spanish:
        note = " <i>(monto actualizado)</i>" if is_changed else ""
        msg = (
            f"✅ <b>Factura registrada como pagada:</b>\n"
            f"• 💳 <b>{html.escape(dec_concept)}</b> ({fmt_paid}){note}\n\n"
            f"<i>Se guardó como gasto en tu historial.</i>\n"
            f"📌 <b>Pendiente por pagar este mes:</b> {rem_str}"
        )
    else:
        note = " <i>(updated amount)</i>" if is_changed else ""
        msg = (
            f"✅ <b>Bill marked as paid:</b>\n"
            f"• 💳 <b>{html.escape(dec_concept)}</b> ({fmt_paid}){note}\n\n"
            f"<i>Recorded as an expense in your history.</i>\n"
            f"📌 <b>Remaining pending bills:</b> {rem_str}"
        )

    return True, msg


async def handle_bills_interactive(
    user: User,
    family: Family,
    args: str = "",
    page: int = 1
) -> Tuple[str, Optional[Dict[str, Any]]]:
    """
    Interactive bills command: returns formatted summary text and paginated inline keyboard.
    """
    from src.services.query.service import QueryService
    from src.services.query.formatters import format_bills_summary
    from src.core.config import settings

    args_lower = (args or "").strip().lower()
    timeframe = "next_month" if any(w in args_lower for w in ["next", "proximo", "siguiente"]) else "this_month"
    active_tz = getattr(user, "timezone", None) or getattr(family, "timezone", None) or getattr(settings, "DEFAULT_TIMEZONE", "America/Argentina/Buenos_Aires")

    qs = QueryService()
    ref_time = datetime.datetime.now(datetime.timezone.utc)
    start_time, end_time = qs._resolve_date_range(timeframe, None, None, ref_time, tz_name=active_tz, future_inclusive=True)

    bills = await asyncio.to_thread(
        qs._fetch_and_decrypt_scheduled_bills,
        family.id, start_time, end_time, "pending"
    )

    tf_label = "Next Month" if timeframe == "next_month" else "This Month"
    text = format_bills_summary(bills, timeframe_label=tf_label, tz_name=active_tz)
    keyboard = build_bills_keyboard(bills, page=page, timeframe=timeframe, page_size=4)
    return text, keyboard
