import logging
import datetime
import html
import asyncio
from typing import Optional
from uuid import UUID
from sqlmodel import Session, select

from src.core.config import settings
from src.core.encryption import EncryptionService
from src.db.session import engine
from src.db.models import User, Transaction, Family
from src.services.query.models import ParsedQueryIntent
from src.services.handlers.notion_handler import (
    safe_update_notion_page,
    safe_archive_notion_page
)

logger = logging.getLogger(__name__)


def create_logged_task(coro, *, name: Optional[str] = None) -> asyncio.Task:
    """Creates an asyncio task with an attached done callback to log unhandled exceptions."""
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


def format_currency(amount: float, currency: str = "USD", show_sign: bool = False) -> str:
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


def get_monthly_cash_flow_snapshot(
    family_id: UUID,
    target_date: datetime.datetime,
    primary_currency: str = "USD",
    encryption_service: Optional[EncryptionService] = None,
    session_factory=Session
) -> dict:
    """
    Queries and decrypts all transactions for the given family in the calendar month of target_date.
    Calculates Total In, Total Out, Net Savings, and Savings Rate percentage for the specified currency.
    """
    enc_service = encryption_service or EncryptionService()
    start_of_month = target_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if target_date.month == 12:
        next_month = target_date.replace(year=target_date.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        next_month = target_date.replace(month=target_date.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)

    with session_factory(engine) as session:
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
                decrypted_amount_str = enc_service.decrypt(tx.amount)
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


def find_target_transaction(
    session: Session,
    user_uuid: UUID,
    target_amount: Optional[float] = None,
    target_currency: Optional[str] = None,
    target_concept: Optional[str] = None,
    encryption_service: Optional[EncryptionService] = None
) -> Optional[Transaction]:
    """
    Searches recent transactions for the user matching optional criteria.
    If no criteria specified, returns the most recent transaction.
    """
    enc_service = encryption_service or EncryptionService()
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
        dec_amt_str = enc_service.decrypt(tx.amount)
        dec_concept = enc_service.decrypt(tx.concept) or ""
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
            dec_amt_str = enc_service.decrypt(tx.amount)
            if not dec_amt_str:
                continue
            parts = dec_amt_str.strip().split()
            a = float(parts[0]) if parts else 0.0
            if abs(a - target_amount) <= 0.01:
                return tx

    # Fallback to the latest transaction
    return recent_txs[0]


def handle_transaction_undo(
    user_uuid: UUID,
    parsed_query: Optional[ParsedQueryIntent] = None,
    encryption_service: Optional[EncryptionService] = None,
    session_factory=Session
) -> str:
    """Removes a recent transaction or entire batch logged by the user, recalculating monthly balance."""
    enc_service = encryption_service or EncryptionService()
    has_target = bool(parsed_query and (parsed_query.target_amount or parsed_query.target_currency or parsed_query.target_concept))

    from src.services.handlers.batch_tracker import BatchTracker
    last_batch_ids = BatchTracker.get_last_batch(user_uuid) if not has_target else None

    with session_factory(engine) as session:
        if last_batch_ids and len(last_batch_ids) > 1:
            txs_to_delete = session.exec(
                select(Transaction).where(
                    Transaction.id.in_(last_batch_ids),
                    Transaction.user_id == user_uuid
                )
            ).all()
            if txs_to_delete:
                deleted_items = []
                notion_page_ids = []
                family_id = txs_to_delete[0].family_id
                tx_time = txs_to_delete[0].timestamp
                primary_curr = "USD"
                for t in txs_to_delete:
                    dec_amount = enc_service.decrypt(t.amount) or "0.00 USD"
                    dec_concept = enc_service.decrypt(t.concept) or "Transaction"
                    parts = dec_amount.strip().split()
                    amt = float(parts[0]) if parts else 0.0
                    curr = parts[1].upper() if len(parts) > 1 else "USD"
                    primary_curr = curr
                    ttype = getattr(t, "tx_type", getattr(t, "type", "expense")) or "expense"
                    deleted_items.append({
                        "concept": dec_concept,
                        "amount": amt,
                        "currency": curr,
                        "category": t.category,
                        "type": ttype
                    })
                    if t.notion_page_id:
                        notion_page_ids.append(t.notion_page_id)
                    session.delete(t)
                session.commit()
                BatchTracker.clear_last_batch(user_uuid)

                for n_id in notion_page_ids:
                    try:
                        create_logged_task(safe_archive_notion_page(family_id, n_id), name="archive_notion_page")
                    except Exception as e:
                        logger.warning(f"Could not dispatch Notion archive task: {e}")

                snapshot = get_monthly_cash_flow_snapshot(family_id, tx_time, primary_curr, encryption_service=enc_service, session_factory=session_factory)
                formatted_in = format_currency(snapshot["total_in"], primary_curr, show_sign=False)
                formatted_out = format_currency(snapshot["total_out"], primary_curr, show_sign=False)
                formatted_net = format_currency(snapshot["net_savings"], primary_curr, show_sign=True)
                pct_str = f" ({snapshot['savings_pct']}%)" if snapshot["total_in"] > 0 else ""

                item_lines = []
                for it in deleted_items:
                    icon = "💰" if it["type"] == "income" else "💸"
                    sign = "+" if it["type"] == "income" else "-"
                    fmt_amt = format_currency(it["amount"], it["currency"], show_sign=False)
                    item_lines.append(f"• {icon} {sign}{fmt_amt} ({html.escape(it['category'])} - {html.escape(it['concept'])})")

                items_block = "\n".join(item_lines)
                is_exchange_pair = (len(deleted_items) == 2 and all(it.get("category") == "Exchange" for it in deleted_items))
                title = "🗑️ <b>Removed currency exchange:</b>\n" if is_exchange_pair else f"🗑️ <b>Removed {len(deleted_items)} transactions from your last message:</b>\n"
                return (
                    f"{title}"

                    f"{items_block}\n\n"
                    f"📊 <b>Updated {snapshot['month_name']} Balance ({primary_curr}):</b>\n"
                    f"• Total In: {formatted_in}\n"
                    f"• Total Out: {formatted_out}\n"
                    f"• Net Savings: {formatted_net}{pct_str}"
                )

        t_amt = parsed_query.target_amount if parsed_query else None
        t_curr = parsed_query.target_currency if parsed_query else None
        t_cpt = parsed_query.target_concept if parsed_query else None

        tx = find_target_transaction(
            session=session,
            user_uuid=user_uuid,
            target_amount=t_amt,
            target_currency=t_curr,
            target_concept=t_cpt,
            encryption_service=enc_service
        )
        if not tx:
            return "ℹ️ You don't have any recent transactions to undo."

        dec_amount = enc_service.decrypt(tx.amount) or "0.00 USD"
        dec_concept = enc_service.decrypt(tx.concept) or "Transaction"
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
            c_dec_amount = enc_service.decrypt(counterpart.amount) or "0.00 USD"
            c_dec_concept = enc_service.decrypt(counterpart.concept) or "Transaction"
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
        BatchTracker.clear_last_batch(user_uuid)

    if notion_page_id:
        try:
            create_logged_task(safe_archive_notion_page(family_id, notion_page_id), name="archive_notion_page")
        except Exception as e:
            logger.warning(f"Could not dispatch Notion archive task: {e}")

    if counterpart_info and counterpart_info.get("notion_page_id"):
        try:
            create_logged_task(safe_archive_notion_page(family_id, counterpart_info["notion_page_id"]), name="archive_counterpart_notion_page")
        except Exception as e:
            logger.warning(f"Could not dispatch counterpart Notion archive task: {e}")

    snapshot = get_monthly_cash_flow_snapshot(family_id, tx_time, curr, encryption_service=enc_service, session_factory=session_factory)

    icon = "💰" if old_type == "income" else "💸"
    sign = "+" if old_type == "income" else "-"
    formatted_amt = format_currency(amt, curr, show_sign=False)
    formatted_in = format_currency(snapshot["total_in"], curr, show_sign=False)
    formatted_out = format_currency(snapshot["total_out"], curr, show_sign=False)
    formatted_net = format_currency(snapshot["net_savings"], curr, show_sign=True)
    pct_str = f" ({snapshot['savings_pct']}%)" if snapshot["total_in"] > 0 else ""

    safe_concept = html.escape(dec_concept)
    safe_category = html.escape(category)
    has_target = bool(parsed_query and (parsed_query.target_amount or parsed_query.target_currency or parsed_query.target_concept))

    if counterpart_info:
        c_icon = "💰" if counterpart_info["type"] == "income" else "💸"
        c_sign = "+" if counterpart_info["type"] == "income" else "-"
        c_formatted = format_currency(counterpart_info["amount"], counterpart_info["currency"], show_sign=False)
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


def handle_transaction_correction(
    user_uuid: UUID,
    parsed_query: ParsedQueryIntent,
    encryption_service: Optional[EncryptionService] = None,
    session_factory=Session
) -> str:
    """Modifies fields on the user's targeted or latest transaction and updates Notion / cash flow snapshot."""
    enc_service = encryption_service or EncryptionService()
    with session_factory(engine) as session:
        tx = find_target_transaction(
            session=session,
            user_uuid=user_uuid,
            target_amount=parsed_query.target_amount,
            target_currency=parsed_query.target_currency,
            target_concept=parsed_query.target_concept,
            encryption_service=enc_service
        )
        if not tx:
            return "ℹ️ You don't have any recent transactions to update."

        dec_amount = enc_service.decrypt(tx.amount) or "0.00 USD"
        dec_concept = enc_service.decrypt(tx.concept) or "Transaction"
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
        tx.amount = enc_service.encrypt(f"{new_amt:.2f} {new_curr}")
        tx.concept = enc_service.encrypt(new_concept)

        session.add(tx)
        session.commit()
        session.refresh(tx)

        notion_page_id = tx.notion_page_id
        family_id = tx.family_id
        tx_time = tx.timestamp

        user = session.get(User, user_uuid)
        user_display_name = (user.full_name or user.username or "User") if user else "User"

    if notion_page_id:
        try:
            create_logged_task(safe_update_notion_page(
                family_id=family_id,
                page_id=notion_page_id,
                amount=new_amt,
                currency=new_curr,
                concept=new_concept,
                category=new_cat,
                timestamp=tx_time,
                user_name=user_display_name,
                tx_type=new_type
            ), name="update_notion_page")
        except Exception as e:
            logger.warning(f"Could not dispatch Notion update task: {e}")

    snapshot = get_monthly_cash_flow_snapshot(family_id, tx_time, new_curr, encryption_service=enc_service, session_factory=session_factory)

    type_note = ""
    if current_type != new_type:
        old_label = "Expense 💸" if current_type == "expense" else "Income 💰"
        new_label = "Income 💰" if new_type == "income" else "Expense 💸"
        type_note = f"\n<i>[Switched from {old_label} to {new_label}]</i>"

    icon = "💰" if new_type == "income" else "💸"
    sign = "+" if new_type == "income" else "-"
    formatted_amt = format_currency(new_amt, new_curr, show_sign=False)
    formatted_in = format_currency(snapshot["total_in"], new_curr, show_sign=False)
    formatted_out = format_currency(snapshot["total_out"], new_curr, show_sign=False)
    formatted_net = format_currency(snapshot["net_savings"], new_curr, show_sign=True)
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

