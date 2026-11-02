"""
Common formatting, localization, and error templates for Clanomy.
"""
import html
from typing import Optional, Any
from datetime import datetime, timezone
from src.core.config import settings

AI_DISCLAIMER_FOOTER = (
    "\n\n⚠️ <i>AI Notice: Outputs may be inaccurate or delayed. Do not rely on AI for critical financial, legal, or tax decisions. Verify entries via /undo.</i>"
)

TELEGRAM_NON_AFFILIATION_DISCLAIMER = (
    "\nℹ️ <i>Notice: Clanomy is an independent application not affiliated with or endorsed by Telegram FZ-LLC.</i>"
)

UNSUPPORTED_FORMAT_MESSAGE = (
    "⚠️ <b>Unsupported Format</b>\n\n"
    "Clanomy only accepts native voice notes (hold the mic 🎙️ icon) or text messages (e.g. <i>'Spent $24 on lunch'</i>)."
)

def format_message_too_long(max_len: int, received_len: int) -> str:
    return (
        f"📝 <b>Message Too Long</b>\n\n"
        f"Please keep transactions and queries under {max_len} characters "
        f"(received {received_len} characters)."
    )

def format_voice_too_long(max_sec: int, received_sec: int) -> str:
    return (
        f"⏱️ <b>Voice Note Too Long</b>\n\n"
        f"Please keep voice logs under {max_sec} seconds "
        f"(recording was {received_sec} seconds)."
    )

def format_voice_too_large(max_mb: float, received_mb: float) -> str:
    return (
        f"📦 <b>Voice File Too Large</b>\n\n"
        f"Please keep voice notes under {max_mb:.1f} MB "
        f"(file was {received_mb:.1f} MB)."
    )

def format_date_localized(dt: datetime, is_spanish: bool = False) -> str:
    """Formats a datetime into a friendly localized date string without relying on system C locale."""
    months_en = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    months_es = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    day = dt.day
    year = dt.year
    month_idx = max(0, min(11, dt.month - 1))
    if is_spanish:
        return f"{day} de {months_es[month_idx]} de {year}"
    return f"{months_en[month_idx]} {day}, {year}"

def is_family_spanish(family: Optional[Any], session: Optional[Any] = None) -> bool:
    """
    Infers whether a family primarily communicates in Spanish based on:
    1. Family timezone (e.g., America/Argentina, America/Santiago, America/Bogota, etc.)
    2. Family default currency (e.g., ARS, CLP, COP, MXN, PEN, UYU)
    Defaults to False (English).
    """
    if not family:
        return False
    tz = (getattr(family, "timezone", None) or "").lower()
    spanish_tz_prefixes = (
        "america/argentina", "america/santiago", "america/bogota", "america/caracas",
        "america/lima", "america/la_paz", "america/asuncion", "america/montevideo",
        "america/mexico_city", "america/guatemala", "america/costa_rica", "america/panama",
        "europe/madrid"
    )
    if any(tz.startswith(p) for p in spanish_tz_prefixes):
        return True
    curr = (getattr(family, "default_currency", None) or "").upper()
    if curr in ("ARS", "CLP", "COP", "MXN", "PEN", "UYU", "BOB", "PYG"):
        return True
    return False

def is_spanish_text(text: Optional[str]) -> bool:
    """
    Heuristic to determine if input text is Spanish.
    Defaults to False (English) as canonical baseline.
    """
    if not text:
        return False
    t = text.lower()
    spanish_markers = [
        "gastos", "gasto", "gaste", "gasté", "fijos", "vencimiento", "vence", "vencimientos",
        "prestamo", "préstamo", "tarjeta", "pesos", "pago", "cuentas", "facturas", "factura",
        "cambie", "cambié", "dolares", "dólares", "cobre", "cobré", "ingreso", "ingresos",
        "sueldo", "almacen", "almacén", "super", "súper", "verdu", "nafta", "pagué", "pague",
        "aboné", "abone", "liquidé", "liquide", "cancelé", "cancele", "luz", "gas", "agua",
        "como", "cómo", "venimos", "mes", "resumen", "balance", "cuanto", "cuánto",
        "saldo", "ahorro", "ahorros", "guardar", "deshacer", "borrar",
        " y ", " en ", " de ", "para ", " con ", " por ", " mi ", " mis "
    ]
    return any(w in t for w in spanish_markers)

def format_payload_too_long_message(is_spanish: bool) -> str:
    """Warning when transaction payload exceeds processing capacity."""
    if is_spanish:
        return (
            "⚠️ <b>Lista demasiado extensa:</b>\n\n"
            "Por tu seguridad financiera, no se guardó ningún gasto parcial de este mensaje.\n"
            "Por favor, divide la lista y envíala en 2 mensajes más cortos."
        )
    return (
        "⚠️ <b>List is too long:</b>\n\n"
        "For your financial safety, no partial transactions were saved.\n"
        "Please split your list and send it in 2 smaller messages."
    )

def format_unhandled_query_message(is_spanish: bool) -> str:
    """Fallback when parsed query cannot be fulfilled."""
    if is_spanish:
        return "No pude procesar tu solicitud."
    return "I couldn't process your request."

def format_audio_error_message(is_spanish: bool) -> str:
    """Error message when audio cannot be transcribed."""
    if is_spanish:
        return "No pude entender el audio. ¿Podrías escribirlo o intentar de nuevo?"
    return "I couldn't understand the audio. Could you please type it or try again?"

def format_persistence_error_message(is_spanish: bool, is_batch: bool = False) -> str:
    """Error message when transaction persistence fails."""
    if is_batch:
        if is_spanish:
            return "No se pudieron guardar las transacciones. Por favor, intenta de nuevo más tarde."
        return "Failed to save transactions. Please try again later."
    if is_spanish:
        return "No se pudo guardar la transacción. Por favor, intenta de nuevo más tarde."
    return "Failed to save transaction. Please try again later."

def format_extraction_error_message(is_spanish: bool) -> str:
    """Error message when extraction fails to locate valid transaction parameters."""
    if is_spanish:
        return "No pude extraer los detalles de tu mensaje. Por favor asegúrate de incluir el monto y el concepto."
    return "I couldn't extract the details from your message. Please make sure to include the amount and what it was for."

def format_empty_message_error(is_spanish: bool) -> str:
    """Error message when message payload is empty."""
    if is_spanish:
        return "No se proporcionó ningún mensaje o audio."
    return "No message or audio was provided."

def format_generic_error_message(is_spanish: bool) -> str:
    """Generic error message for uncaught orchestrator exceptions."""
    if is_spanish:
        return "Ocurrió un error inesperado al procesar tu solicitud."
    return "An unexpected error occurred while processing your request."
