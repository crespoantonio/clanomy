"""
Scheduled bills, reminders, settlement cards, and interactive bill edit templates for Clanomy.
"""
import html
from typing import Optional, Any, List
from datetime import datetime
from src.templates.common import is_spanish_text, format_date_localized

def format_batch_bills_tip(is_spanish: bool) -> str:
    """Returns pro-tip explaining /bills command alongside conversational query."""
    if is_spanish:
        return '\n\n💡 <i>Pregúntame "¿qué vence esta semana?" o envía /bills para ver todas tus facturas sin gastar créditos de IA.</i>'
    return '\n\n💡 <i>Ask me "what bills are due this week?" or send /bills to check upcoming bills without using your monthly AI quota.</i>'

def format_upcoming_bills_tip(is_spanish: bool, plan_type: str = "free") -> str:
    """Returns friendly shortcut tip for bills queries."""
    if plan_type == "free":
        if is_spanish:
            return "\n\n💡 <i>Tip: Escribe /bills en cualquier momento para consultar tus facturas al instante sin gastar tu cuota mensual de IA.</i>"
        return "\n\n💡 <i>Pro-tip: Type /bills anytime for an instant check that doesn't use your monthly AI quota!</i>"
    else:
        if is_spanish:
            return "\n\n💡 <i>Tip: Escribe /bills en cualquier momento para una consulta instantánea.</i>"
        return "\n\n💡 <i>Pro-tip: Type /bills anytime for an instant check!</i>"

def format_batch_bills_header(count: int, is_spanish: bool) -> str:
    """Header for scheduled bills section in batch responses."""
    if is_spanish:
        return f"📋 <b>{count} Factura(s) Programada(s):</b>\n\n"
    return f"📋 <b>{count} Scheduled Bill(s):</b>\n\n"

def format_batch_total_pending(tot_str: str, is_spanish: bool) -> str:
    """Summary of total pending amount for bills in batch responses."""
    if is_spanish:
        return f"\n📌 <b>Total pendiente por pagar:</b> {tot_str}"
    return f"\n📌 <b>Total pending to pay:</b> {tot_str}"

def format_unmatched_bill_claim(concept_hint_or_raw: str, is_spanish: bool) -> str:
    """Response when a payment claim does not match an upcoming bill."""
    safe_hint = html.escape(concept_hint_or_raw)
    if is_spanish:
        return f"ℹ️ No encontré ninguna factura pendiente para '{safe_hint}'. ¿Cuánto fue el monto que pagaste?"
    return f"ℹ️ I couldn't find an upcoming bill matching '{safe_hint}'. What was the amount paid?"

def format_bill_settled_notice(matched_concept: str, remaining_pending: str, is_spanish: bool) -> str:
    """Notice appended when an expense settles an existing scheduled bill."""
    safe_concept = html.escape(matched_concept)
    if is_spanish:
        return f"\n\n✅ <b>¡Marcado como pagado!</b>\n💳 <b>{safe_concept}</b> registrado en tus gastos.\n⏳ Restante pendiente este mes: <b>{remaining_pending}</b>"
    return f"\n\n✅ <b>Marked as paid!</b>\n💳 <b>{safe_concept}</b> recorded in your expenses.\n⏳ Remaining pending this month: <b>{remaining_pending}</b>"

def format_batch_bill_item(concept: str, fmt_amt: str, due_date: datetime, is_spanish: bool) -> str:
    """Formats a single bill row inside a batch confirmation message."""
    safe_concept = html.escape(concept)
    due_str = due_date.strftime("%d/%m")
    if is_spanish:
        day_names = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
        day_name = day_names[due_date.weekday()]
        return f"• 💳 <b>{safe_concept}:</b> {fmt_amt} <i>(Vence: {day_name} {due_str})</i>\n"
    day_name = due_date.strftime("%a")
    return f"• 💳 <b>{safe_concept}:</b> {fmt_amt} <i>(Due: {day_name} {due_str})</i>\n"

def format_bill_settled_response(
    concept: str,
    fmt_paid: str,
    rem_str: str,
    is_spanish: bool,
    is_changed: bool = False
) -> str:
    """Full response message when a scheduled bill is settled by ID or name."""
    safe_concept = html.escape(concept)
    if is_spanish:
        note = " <i>(monto actualizado)</i>" if is_changed else ""
        return (
            f"✅ <b>Factura registrada como pagada:</b>\n"
            f"• 💳 <b>{safe_concept}</b> ({fmt_paid}){note}\n\n"
            f"<i>Se guardó como gasto en tu historial.</i>\n"
            f"📌 <b>Pendiente por pagar este mes:</b> {rem_str}"
        )
    note = " <i>(updated amount)</i>" if is_changed else ""
    return (
        f"✅ <b>Bill marked as paid:</b>\n"
        f"• 💳 <b>{safe_concept}</b> ({fmt_paid}){note}\n\n"
        f"<i>Recorded as an expense in your history.</i>\n"
        f"📌 <b>Remaining pending bills:</b> {rem_str}"
    )

def format_overdue_bills_reminder(due_or_overdue_lines: list, is_spanish: bool) -> str:
    """Formatted banner alerting users of impending or overdue bills."""
    if not due_or_overdue_lines:
        return ""
    if is_spanish:
        header = "⚠️ <b>Recordatorio de Vencimientos:</b>\n<i>Tienes facturas programadas pendientes de pago:</i>"
        tip = '\n👉 <i>Si ya pagaste alguna, solo dime "Pagué [nombre]" (ej: "Pagué la visa") o pulsa en /bills para registrarla.</i>'
    else:
        header = "⚠️ <b>Upcoming / Due Bills Reminder:</b>\n<i>You have pending scheduled bills:</i>"
        tip = '\n👉 <i>If you already paid any, simply tell me "Paid [name]" (e.g. "Paid the visa") or tap in /bills to record it.</i>'
    return f"{header}\n" + "\n".join(due_or_overdue_lines) + f"\n{tip}"

def format_bill_settlement_card(
    concept: str,
    fmt_amt: str,
    due_fmt: str,
    category: str,
    bill_id: Any,
    return_page: int = 1,
    tf_code: str = "this",
    is_spanish: bool = False
) -> Tuple[str, dict]:
    """Builds interactive 2-option settlement card text and inline keyboard for a specific bill."""
    safe_concept = html.escape(concept)
    safe_cat = html.escape(category)
    if is_spanish:
        card_text = (
            f"⚡ <b>Pagar Factura: {safe_concept}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"• <b>Monto Registrado:</b> {fmt_amt}\n"
            f"• <b>Vencimiento:</b> {due_fmt}\n"
            f"• <b>Categoría:</b> {safe_cat}\n\n"
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
            f"⚡ <b>Settle Bill: {safe_concept}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"• <b>Recorded Amount:</b> {fmt_amt}\n"
            f"• <b>Due Date:</b> {due_fmt}\n"
            f"• <b>Category:</b> {safe_cat}\n\n"
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

def format_bill_not_found_card(return_page: int = 1, tf_code: str = "this", is_spanish: bool = False) -> Tuple[str, dict]:
    """Fallback card when requested bill does not exist."""
    msg = "Factura no encontrada." if is_spanish else "Bill not found."
    btn_text = "🔙 Volver" if is_spanish else "🔙 Back"
    return msg, {"inline_keyboard": [[{"text": btn_text, "callback_data": f"bills_p:{return_page}:{tf_code}"}]]}

def format_bill_already_paid_card(return_page: int = 1, tf_code: str = "this", is_spanish: bool = False) -> Tuple[str, dict]:
    """Fallback card when requested bill is already paid."""
    msg = "Esta factura ya fue pagada." if is_spanish else "This bill is already marked as paid."
    btn_text = "🔙 Volver" if is_spanish else "🔙 Back"
    return msg, {"inline_keyboard": [[{"text": btn_text, "callback_data": f"bills_p:{return_page}:{tf_code}"}]]}

def format_bill_edit_prompt(target_bill_id: Any, concept: str, is_spanish: bool = False) -> Tuple[str, str]:
    """Returns (prompt_text, toast_text) for interactive bill editing session."""
    safe_cpt = html.escape(concept)
    if is_spanish:
        prompt = (
            f'<a href="tg://bill/{target_bill_id}">&#8203;</a>'
            f"✏️ <b>Pagar '{safe_cpt}'</b>\n\n"
            f"Responde con el monto pagado (ej: <code>45.50</code>) — <i>100% gratis</i>,\n"
            f"o envía un audio <i>(consume 1 crédito de IA 🎙️)</i>.\n\n"
            f"<i>(Escribe 'cancel' para abortar)</i>"
        )
        toast = "Responde con el nuevo monto"
    else:
        prompt = (
            f'<a href="tg://bill/{target_bill_id}">&#8203;</a>'
            f"✏️ <b>Settle '{safe_cpt}'</b>\n\n"
            f"Reply with the exact amount paid (e.g. <code>45.50</code>) — <i>100% free</i>,\n"
            f"or send a voice note <i>(uses 1 AI log 🎙️)</i>.\n\n"
            f"<i>(Send 'cancel' to abort)</i>"
        )
        toast = "Reply with the new amount"
    return prompt, toast

def format_bill_edit_cancelled(is_spanish: bool = False) -> str:
    """Notice when an interactive bill edit is cancelled."""
    if is_spanish:
        return "❌ Pago de factura cancelado. La factura sigue pendiente."
    return "❌ Bill payment cancelled. The bill remains pending."

def format_bill_edit_invalid_amount(is_spanish: bool = False) -> str:
    """Error message when invalid numeric amount is provided during bill edit."""
    if is_spanish:
        return "⚠️ No pude reconocer un monto válido. Por favor responde con un número (ej: 45.50) o escribe 'cancel'."
    return "⚠️ Could not recognize a valid amount. Please reply with a number (e.g. 45.50) or type 'cancel'."
