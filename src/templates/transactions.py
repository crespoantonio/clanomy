"""
Transaction confirmations, exchange rates, undo, and correction templates for Clanomy.
"""
import html
from typing import Optional, Any, List
from datetime import datetime
from src.templates.common import is_spanish_text, format_date_localized

def format_spending_summary_tip(is_spanish: bool, plan_type: str = "free") -> str:
    """Returns friendly shortcut tip for spending/month queries."""
    if plan_type == "free":
        if is_spanish:
            return "\n\n💡 <i>Tip: Escribe /month o /me en cualquier momento para una respuesta instantánea sin gastar tu cuota mensual de IA.</i>"
        return "\n\n💡 <i>Pro-tip: Type /month or /me anytime for an instant response that doesn't use your monthly AI quota!</i>"
    else:
        if is_spanish:
            return "\n\n💡 <i>Tip: Escribe /month o /me en cualquier momento para una respuesta instantánea.</i>"
        return "\n\n💡 <i>Pro-tip: Type /month or /me anytime for an instant response!</i>"

def format_savings_summary_tip(is_spanish: bool, plan_type: str = "free") -> str:
    """Returns friendly shortcut tip for savings/total balance queries."""
    if plan_type == "free":
        if is_spanish:
            return "\n\n💡 <i>Tip: Escribe /savings o /history en cualquier momento para una respuesta instantánea sin gastar tu cuota mensual de IA.</i>"
        return "\n\n💡 <i>Pro-tip: Type /savings or /history anytime for an instant response that doesn't use your monthly AI quota!</i>"
    else:
        if is_spanish:
            return "\n\n💡 <i>Tip: Escribe /savings o /history en cualquier momento para una respuesta instantánea.</i>"
        return "\n\n💡 <i>Pro-tip: Type /savings or /history anytime for an instant response!</i>"

def format_batch_transactions_header(incomes_count: int, expenses_count: int, total_count: int, is_spanish: bool) -> str:
    """Header for transaction section in batch responses."""
    if incomes_count > 0 and expenses_count == 0:
        return f"📋 <b>{total_count} Ingreso(s) Registrado(s):</b>\n\n" if is_spanish else f"📋 <b>{total_count} Income(s) Logged:</b>\n\n"
    elif expenses_count > 0 and incomes_count == 0:
        return f"📋 <b>{total_count} Gasto(s) Registrado(s):</b>\n\n" if is_spanish else f"📋 <b>{total_count} Expense(s) Logged:</b>\n\n"
    else:
        return f"📋 <b>{total_count} Transacciones Registradas:</b>\n\n" if is_spanish else f"📋 <b>{total_count} Transactions Logged:</b>\n\n"

def format_single_expense_confirmation(
    amount: float,
    currency: str,
    concept: str,
    category: str,
    date_str: str,
    is_spanish: bool
) -> str:
    """Confirmation message for a single logged expense."""
    safe_concept = html.escape(concept)
    safe_cat = html.escape(category)
    if is_spanish:
        return f"Guardado {amount} {currency} para '{safe_concept}' en la categoría '{safe_cat}'{date_str}."
    return f"Saved {amount} {currency} for '{safe_concept}' under category '{safe_cat}'{date_str}."

def format_single_income_confirmation(
    formatted_amt: str,
    concept_detail: str,
    date_str: str,
    formatted_in: str,
    formatted_out: str,
    formatted_net: str,
    pct_str: str,
    month_name: str,
    is_spanish: bool,
    month_num: Optional[int] = None
) -> str:
    """Confirmation message and monthly snapshot for a single logged income."""
    if is_spanish:
        spanish_months = {
            1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
            5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
            9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
        }
        month_label = spanish_months.get(month_num, month_name) if month_num else month_name
        return (
            f"💰 Ingreso Registrado: {formatted_amt} {concept_detail}{date_str}\n"
            f"📊 Resumen de {month_label}:\n"
            f"• Total Ingresos: {formatted_in}\n"
            f"• Total Gastos: {formatted_out}\n"
            f"• Ahorro Neto: {formatted_net}{pct_str}"
        )
    return (
        f"💰 Income Logged: {formatted_amt} {concept_detail}{date_str}\n"
        f"📊 {month_name} Snapshot:\n"
        f"• Total In: {formatted_in}\n"
        f"• Total Out: {formatted_out}\n"
        f"• Net Savings: {formatted_net}{pct_str}"
    )

def format_exchange_confirmation(
    fmt_sold: str,
    fmt_recv: str,
    rate_line: str,
    is_spanish: bool
) -> str:
    """Formatted confirmation for dual-leg currency exchange transactions."""
    if is_spanish:
        return (
            f"💱 <b>Cambio de Moneda Registrado:</b>\n"
            f"• 💸 Entregaste: -{fmt_sold}\n"
            f"• 💰 Recibiste: +{fmt_recv}"
            f"{rate_line}\n\n"
            f"🏷️ <i>Categorizado bajo <b>Exchange</b> para no distorsionar ingresos o gastos operativos del mes.</i>"
        )
    return (
        f"💱 <b>Currency Exchange Logged:</b>\n"
        f"• 💸 Sold: -{fmt_sold}\n"
        f"• 💰 Received: +{fmt_recv}"
        f"{rate_line}\n\n"
        f"🏷️ <i>Categorized under <b>Exchange</b> to keep operational income & expenses clean.</i>"
    )

def format_exchange_rate_line(sold_currency: str, rate_val: Optional[float], recv_currency: str, fmt_rate: str, is_spanish: bool) -> str:
    """Formats the calculated exchange rate line item."""
    if not rate_val:
        return ""
    if is_spanish:
        return f"\n• 📊 Cotización: 1 {sold_currency} = {fmt_rate}"
    return f"\n• 📊 Rate: 1 {sold_currency} = {fmt_rate}"

def format_batch_tx_item(icon: str, concept: str, fmt_amt: str, category: str) -> str:
    """Formats a single transaction row inside a batch confirmation message."""
    safe_concept = html.escape(concept)
    safe_category = html.escape(category)
    return f"• {icon} <b>{safe_concept}:</b> {fmt_amt} ({safe_category})\n"

def format_undo_no_transactions(is_spanish: bool) -> str:
    """Message when user calls /undo with no recent transactions."""
    if is_spanish:
        return "ℹ️ No tienes transacciones recientes para deshacer."
    return "ℹ️ You don't have any recent transactions to undo."

def format_undo_success(
    items_block: str,
    month_name: str,
    primary_curr: str,
    formatted_in: str,
    formatted_out: str,
    formatted_net: str,
    pct_str: str,
    is_exchange: bool = False,
    is_batch: bool = False,
    batch_count: int = 1,
    has_target: bool = False,
    is_spanish: bool = False
) -> str:
    """Confirmation message and updated balance snapshot after /undo."""
    if is_spanish:
        if is_exchange:
            title = "🗑️ <b>Cambio de moneda revertido:</b>\n"
        elif is_batch:
            title = f"🗑️ <b>Se eliminaron {batch_count} transacciones de tu último mensaje:</b>\n"
        elif has_target:
            title = "🗑️ <b>Transacción revertida:</b>\n"
        else:
            title = "🗑️ <b>Última transacción revertida:</b>\n"

        balance_header = f"📊 <b>Balance Actualizado de {month_name} ({primary_curr}):</b>"
        in_label = "• Total Ingresos:"
        out_label = "• Total Gastos:"
        net_label = "• Ahorro Neto:"
    else:
        if is_exchange:
            title = "🗑️ <b>Removed currency exchange:</b>\n"
        elif is_batch:
            title = f"🗑️ <b>Removed {batch_count} transactions from your last message:</b>\n"
        elif has_target:
            title = "🗑️ <b>Removed transaction:</b>\n"
        else:
            title = "🗑️ <b>Removed latest transaction:</b>\n"

        balance_header = f"📊 <b>Updated {month_name} Balance ({primary_curr}):</b>"
        in_label = "• Total In:"
        out_label = "• Total Out:"
        net_label = "• Net Savings:"

    return (
        f"{title}"
        f"{items_block}\n\n"
        f"{balance_header}\n"
        f"{in_label} {formatted_in}\n"
        f"{out_label} {formatted_out}\n"
        f"{net_label} {formatted_net}{pct_str}"
    )

def format_correction_no_transactions(is_spanish: bool) -> str:
    """Message when user attempts to correct a non-existent transaction."""
    if is_spanish:
        return "ℹ️ No tienes transacciones recientes para modificar."
    return "ℹ️ You don't have any recent transactions to update."

def format_correction_success(
    icon: str,
    sign: str,
    formatted_amt: str,
    category: str,
    concept: str,
    type_note: str,
    month_name: str,
    formatted_in: str,
    formatted_out: str,
    formatted_net: str,
    pct_str: str,
    has_target: bool = False,
    is_spanish: bool = False
) -> str:
    """Confirmation message and updated balance snapshot after editing a transaction."""
    safe_concept = html.escape(concept)
    safe_category = html.escape(category)
    if is_spanish:
        title = "✏️ <b>Transacción modificada:</b>\n" if has_target else "✏️ <b>Última transacción modificada:</b>\n"
        balance_header = f"📊 <b>Balance Actualizado de {month_name}:</b>"
        in_label = "• Total Ingresos:"
        out_label = "• Total Gastos:"
        net_label = "• Ahorro Neto:"
    else:
        title = "✏️ <b>Updated transaction:</b>\n" if has_target else "✏️ <b>Updated latest transaction:</b>\n"
        balance_header = f"📊 <b>Updated {month_name} Balance:</b>"
        in_label = "• Total In:"
        out_label = "• Total Out:"
        net_label = "• Net Savings:"

    return (
        f"{title}"
        f"• {icon} {sign}{formatted_amt} ({safe_category} - {safe_concept}){type_note}\n\n"
        f"{balance_header}\n"
        f"{in_label} {formatted_in}\n"
        f"{out_label} {formatted_out}\n"
        f"{net_label} {formatted_net}{pct_str}"
    )

def format_currency_menu_text(active_currency: str, is_spanish: bool = False) -> str:
    """Introduction text for the interactive currency selector menu."""
    if is_spanish:
        return (
            "💵 <b>Seleccionar Moneda Predeterminada del Hogar</b>\n\n"
            f"Actualmente activa: <b>{active_currency}</b>\n\n"
            "Toca una moneda abajo para establecerla como predeterminada de tu familia. "
            "Cualquier futuro gasto o ingreso que registres sin especificar moneda usará automáticamente esta opción."
        )
    return (
        "💵 <b>Select Household Default Currency</b>\n\n"
        f"Currently active: <b>{active_currency}</b>\n\n"
        "Tap a currency below to set it as your household default. "
        "Any future expenses or income logged without a currency symbol will automatically default to your choice."
    )

def format_currency_success_text(new_currency: str, is_spanish: bool = False) -> str:
    """Confirmation text when a new household currency is saved."""
    if is_spanish:
        return (
            f"✅ <b>¡Moneda Predeterminada Actualizada a {new_currency}!</b>\n\n"
            f"Todos los gastos e ingresos futuros registrados sin símbolo se guardarán automáticamente como <b>{new_currency}</b>.\n\n"
            "Puedes cambiar esto en cualquier momento con /currency."
        )
    return (
        f"✅ <b>Default Currency Updated to {new_currency}!</b>\n\n"
        f"All future expenses & income logged without a currency symbol will automatically record as <b>{new_currency}</b>.\n\n"
        "You can change this anytime with /currency."
    )
