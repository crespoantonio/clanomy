"""
Onboarding, consent, legal disclosures, timezone, and data sovereignty templates for Clanomy.
"""
import html
from typing import Optional, Any
from datetime import datetime, timezone
from src.core.config import settings
from src.db.models import Family, User
from src.templates.common import (
    is_spanish_text,
    format_date_localized,
    AI_DISCLAIMER_FOOTER,
    TELEGRAM_NON_AFFILIATION_DISCLAIMER
)

UNAUTHORIZED_ACCESS_MESSAGE = (
    "🔒 <b>Private Instance</b>\n\n"
    "This Clanomy bot instance is private and restricted to authorized users."
)

CONSENT_REQUEST_MESSAGE = (
    "👋 <b>Welcome to Clanomy!</b>\n\n"
    "Clanomy is a privacy-first household financial assistant.\n\n"
    "Before logging your finances, please review and accept our data terms:\n\n"
    "• 🔒 <b>Zero-Knowledge:</b> Financial records (amounts &amp; concepts) are encrypted via AES-256 before storage.\n"
    "• 🤖 <b>Third-Party AI:</b> Voice &amp; text notes are parsed using Google Gemini &amp; Whisper developer APIs under zero-retention, zero-training agreements.\n"
    "• 🔞 <b>Eligibility:</b> You must be <b>18 years of age or older</b>. Individuals under 18 are prohibited from using Clanomy.\n"
    "• 📜 <b>Non-Advisory Tool:</b> Clanomy is an automated software utility. We do <b>NOT</b> provide financial, investment, legal, or tax advice. AI outputs may contain inaccuracies; always verify critical entries.\n"
    "• 🗑️ <b>Data Sovereignty:</b> You can permanently purge your data anytime with /delete_my_data.\n\n"
    "<i>Please tap below to accept the Terms of Service &amp; Privacy Policy to begin:</i>"
)

CONSENT_KEYBOARD = {
    "inline_keyboard": [
        [{"text": "✅ Accept Terms & Privacy (18+)", "callback_data": "accept_tos"}],
        [
            {"text": "📄 Privacy Policy", "callback_data": "view_privacy"},
            {"text": "📜 Terms of Service", "callback_data": "view_tos"}
        ]
    ]
}

PRIVACY_POLICY_MESSAGE = (
    "🛡️ <b>Clanomy Privacy Policy & Transparency Notice</b>\n\n"
    "• <b>Zero-Knowledge Encryption:</b> All financial entries are encrypted in memory using application-level AES-256 Fernet before hitting the database. Database backups contain only unreadable ciphertext.\n\n"
    "• <b>Third-Party Sub-Processors:</b>\n"
    "  1. <i>Google LLC (Gemini API):</i> Used for natural language parsing under commercial enterprise API terms. User prompts are strictly transient, never stored, and never used to train machine learning models.\n"
    "  2. <i>Speech-to-Text (Whisper):</i> Voice notes are transcribed transiently in memory and immediately discarded.\n"
    "  3. <i>Notion Labs (Optional):</i> Synchronized only if you explicitly connect your personal Notion database.\n\n"
    "• <b>Data Retention & Rights (GDPR / CCPA):</b>\n"
    "  - /export — Instantly download your full transaction history (CSV/JSON).\n"
    "  - /delete_my_data — Permanently purge your account, Telegram ID, and all records.\n\n"
    "• <b>Contact:</b> support@clanomy.com"
)

TERMS_OF_SERVICE_MESSAGE = (
    "📜 <b>Clanomy Terms of Service</b>\n\n"
    "• <b>Non-Advisory Tool:</b> Clanomy is an automated productivity software utility for personal record-keeping. Clanomy is <b>NOT</b> a certified financial planner, broker, lender, tax specialist, or attorney. We do NOT provide financial, investment, legal, or tax advice.\n\n"
    "• <b>Age Requirement:</b> You must be at least 18 years old to use Clanomy.\n\n"
    "• <b>'As-Is' Warranty & AI Notice:</b> Clanomy utilizes Artificial Intelligence. Outputs may be inaccurate, hallucinated, or delayed. The Service is provided on an <b>'AS IS'</b> and <b>'AS AVAILABLE'</b> basis with no uptime or error-free warranties. Always verify entries via /undo.\n\n"
    "• <b>Subscriptions & Billing:</b> Paid plans auto-renew monthly or annually until cancelled. Cancel anytime with 1 tap via /billing. All plans include a 60-day free trial; paid subscriptions are non-refundable once billed.\n\n"
    "• <b>Unofficial Status:</b> Clanomy is an independent product not affiliated with, sponsored by, or endorsed by Telegram FZ-LLC.\n\n"
    "• <b>Contact:</b> support@clanomy.com"
)

def format_welcome_message(user: User, family: Optional[Family], from_user: dict, is_spanish: bool = False) -> str:
    plan_badge = ""
    command_bullet = (
        "• ⚡ <b>Comandos Instantáneos:</b> Escribe /month, /me, /today, /bills, o /balance para respuestas inmediatas!"
        if is_spanish else
        "• ⚡ <b>Instant Commands:</b> Type /month, /me, /today, /bills, or /balance for the fastest responses!"
    )

    if family:
        if family.plan_type == "trial":
            days_left = 60
            if family.trial_ends_at:
                now_utc = datetime.now(timezone.utc)
                trial_end = family.trial_ends_at if family.trial_ends_at.tzinfo else family.trial_ends_at.replace(tzinfo=timezone.utc)
                days_left = max(0, (trial_end - now_utc).days)
            if is_spanish:
                plan_badge = f"⭐️ <b>Prueba Duo Pro (60 días):</b> {days_left} días restantes de registros compartidos (pool de 60/día para 2 integrantes) y Notion!\n\n"
            else:
                plan_badge = f"⭐️ <b>60-Day Duo Pro Trial:</b> {days_left} days remaining of shared logs (60/day pool for 2 partners) &amp; Notion sync!\n\n"
        elif family.plan_type == "free":
            used = getattr(family, "monthly_tx_count", 0)
            if is_spanish:
                plan_badge = f"📦 <b>Plan:</b> Gratuito ({used}/20 registros con IA usados este mes).\n\n"
                command_bullet = "• ⚡ <b>Comandos Gratuitos Ilimitados:</b> Escribe /month, /me, /today, /bills, o /balance en cualquier momento — ¡son 100% gratuitos y no consumen tus 20 registros mensuales de IA!"
            else:
                plan_badge = f"📦 <b>Plan:</b> Free Plan ({used}/20 AI logs used this month).\n\n"
                command_bullet = "• ⚡ <b>Unlimited Free Commands:</b> Type /month, /me, /today, /bills, or /balance anytime — they are 100% free and don't count against your 20 monthly AI logs!"
        elif family.plan_type == "solo_pro":
            plan_badge = (
                "⭐️ <b>Plan:</b> Solo Pro (Activo — 60 registros diarios con IA, espacio personal).\n\n"
                if is_spanish else
                "⭐️ <b>Plan:</b> Solo Pro (Active — 60 daily AI logs, personal workspace).\n\n"
            )
        elif family.plan_type == "duo_pro":
            plan_badge = (
                "👫 <b>Plan:</b> Duo Pro (Activo — 120 registros diarios con IA, registro compartido para 2 integrantes).\n\n"
                if is_spanish else
                "👫 <b>Plan:</b> Duo Pro (Active — 120 daily AI logs, shared ledger for 2 partners).\n\n"
            )
        elif family.plan_type == "family_pro":
            plan_badge = (
                "👨‍👩‍👧‍👦 <b>Plan:</b> Family Pro (Activo — 300 registros diarios con IA, registro familiar compartido y sincronización con Notion).\n\n"
                if is_spanish else
                "👨‍👩‍👧‍👦 <b>Plan:</b> Family Pro (Active — 300 daily AI logs, shared family ledger &amp; Notion sync).\n\n"
            )
        elif family.plan_type == "lifetime_pro":
            plan_badge = (
                "👑 <b>Plan:</b> Lifetime Pro (Estado activo permanente — 40 registros diarios con IA).\n\n"
                if is_spanish else
                "👑 <b>Plan:</b> Lifetime Pro (Permanent active status — 40 daily AI logs).\n\n"
            )

    raw_user_name = user.full_name or from_user.get("first_name") or "User"
    user_display_name = html.escape(raw_user_name, quote=False)
    project_name = html.escape(getattr(settings, "PROJECT_NAME", "Clanomy"), quote=False)
    tz_name = html.escape(str(getattr(settings, "DEFAULT_TIMEZONE", "America/Argentina/Buenos_Aires")), quote=False)

    teamwork_bullet = (
        "👥 <i>Trabajo en equipo: Usa /invite para agregar a tu pareja o integrantes de tu hogar.</i>"
        if is_spanish else
        "👥 <i>Teamwork: Use /invite to add your partner or household members.</i>"
    )
    if family:
        if family.plan_type in ("trial", "duo_pro"):
            teamwork_bullet = (
                "👥 <i>Trabajo en equipo: Usa /invite para agregar a tu pareja (o mejora a Family Pro para hasta 5 miembros).</i>"
                if is_spanish else
                "👥 <i>Teamwork: Use /invite to add your partner (or upgrade to Family Pro for up to 5 members).</i>"
            )
        elif family.plan_type == "solo_pro":
            teamwork_bullet = (
                "👥 <i>Trabajo en equipo: Solo Pro es para 1 usuario. Mejora a Duo Pro o Family Pro con /upgrade para invitar miembros.</i>"
                if is_spanish else
                "👥 <i>Teamwork: Solo Pro is for 1 user. Upgrade to Duo Pro or Family Pro with /upgrade to invite members.</i>"
            )

    greeting = (
        f"👋 <b>¡Bienvenido a {project_name}, {user_display_name}!</b>\n\n"
        if is_spanish else
        f"👋 <b>Welcome to {project_name}, {user_display_name}!</b>\n\n"
    )

    body = (
        "<b>Cómo funciona Clanomy:</b>\n"
        "• 🎙️ <b>Voz y Texto Natural:</b> Registra gastos o ingresos en español o inglés cuando quieras (<i>\"Café 4\"</i>, <i>\"Gasté 35 en cena\"</i>, <i>\"Cobré 3500 de sueldo\"</i>).\n"
        f"{command_bullet}\n"
        "• ↩️ <b>¿Te equivocaste?</b> Escribe /undo en cualquier momento para deshacer tu último registro.\n\n"
        "💡 <b>Configuración Rápida:</b>\n"
        "• 💵 <b>Moneda:</b> Elige la moneda de tu hogar con /currency\n"
        f"• 🌐 <b>Zona Horaria:</b> Configurada en <b>{tz_name}</b>. Calíbrala con /timezone o compartiendo tu ubicación (📎 ➔ Ubicación).\n\n"
        "<b>Prueba enviándome algo ahora mismo:</b>\n"
        "• 🎙️ <i>Envía un audio:</i> \"Café 4\"\n"
        "• 💬 <i>Escribe un gasto:</i> \"Gasté 45 en compras\" o \"45 cena\"\n"
        "• 💰 <i>Escribe un ingreso:</i> \"Cobré 3000 sueldo\"\n"
        "• 📊 <i>Haz una pregunta:</i> \"¿Cuánto gastamos este mes?\"\n\n"
        f"{teamwork_bullet}\n"
        "Escribe /help para ver comandos, /privacy para privacidad, o /export para descargar tus datos."
    ) if is_spanish else (
        "<b>How Clanomy Works:</b>\n"
        "• 🎙️ <b>Natural Voice &amp; Text:</b> Log expenses or income in English or Spanish anytime (<i>\"Coffee 4\"</i>, <i>\"Gasté 35 en cena\"</i>, <i>\"Earned 3,500 salary\"</i>).\n"
        f"{command_bullet}\n"
        "• ↩️ <b>Mistake?</b> Type /undo anytime to instantly revert your last entry.\n\n"
        "💡 <b>Quick Setup:</b>\n"
        "• 💵 <b>Currency:</b> Set your household default currency with /currency\n"
        f"• 🌐 <b>Timezone:</b> Defaults to <b>{tz_name}</b>. Calibrate anytime with /timezone or by sharing your location pin (📎 ➔ Location).\n\n"
        "<b>Try sending me something right now:</b>\n"
        "• 🎙️ <i>Send a voice note:</i> \"Coffee 4\"\n"
        "• 💬 <i>Type an expense:</i> \"Spent 45 on groceries\" or \"45 cena\"\n"
        "• 💰 <i>Type an income:</i> \"Got paid 3,000 salary\"\n"
        "• 📊 <i>Ask a question:</i> \"How much did we spend this month?\"\n\n"
        f"{teamwork_bullet}\n"
        "Type /help anytime for commands, /privacy for data rights, or /export to download your data."
    )

    return (
        f"{greeting}"
        f"{plan_badge}"
        f"{body}"
        f"{AI_DISCLAIMER_FOOTER}"
        f"{TELEGRAM_NON_AFFILIATION_DISCLAIMER}"
    )

def format_help_message(is_spanish: bool) -> str:
    """Full help menu detailing zero-quota commands and conversational AI capabilities."""
    if is_spanish:
        return (
            "✨ <b>Clanomy — Asistente de Finanzas del Hogar</b>\n\n"
            "⚡ <b>Comandos Gratuitos Ilimitados:</b>\n"
            "• /month — 📊 Resumen mensual del hogar y desglose por integrante\n"
            "• /month last — 📊 Ver el resumen del hogar del mes anterior\n"
            "• /me — 👤 Tus ingresos, gastos personales y categorías principales\n"
            "• /today — 📅 Resumen de transacciones registradas hoy\n"
            "• /balance — 💰 Flujo de caja neto y tasa de ahorro del hogar\n"
            "• /savings — 🏦 Ahorros acumulados y balance total de la historia\n"
            "• /history — 📜 Historial financiero de los últimos 3 meses\n"
            "• /bills — ⏰ Facturas y vencimientos programados pendientes\n"
            "• /timezone — 🌐 Ver o calibrar tu zona horaria activa\n"
            "• /family — 👥 Integrantes, roles, moneda y cuota del plan\n"
            "• /invite — 🔗 Invitar a tu pareja o compañero de casa\n"
            "• /export — 📁 Descargar todas tus transacciones en CSV o JSON\n"
            "• /undo — ↩️ Revertir de inmediato el último gasto registrado\n"
            "• /privacy — 🛡️ Privacidad Zero-Knowledge y acuerdos de IA de terceros\n"
            "• /tos — 📜 Términos de Servicio y aviso de herramienta no asesora\n"
            "• /delete_my_data — 🗑️ Borrar permanentemente tus datos de Clanomy\n\n"
            "🧠 <b>Asistente de IA Conversacional:</b>\n"
            "<i>Escríbeme o envíame audios con total naturalidad para registrar o consultar:</i>\n"
            "• <i>\"35 sushi Tony\"</i> o <i>\"Pagué 120 de luz María\"</i>\n"
            "• <i>\"¿Cuánto gastamos en el súper la semana pasada?\"</i>\n"
            "• <i>\"Cambia el último a ingreso\"</i>\n\n"
            "💡 <i>Nota: Los comandos (/month, /me, etc.) son siempre 100% gratuitos y nunca consumen tu cuota mensual de IA.</i>"
            f"{AI_DISCLAIMER_FOOTER}"
            f"{TELEGRAM_NON_AFFILIATION_DISCLAIMER}"
        )
    return (
        "✨ <b>Clanomy — Household Finance Assistant</b>\n\n"
        "⚡ <b>Unlimited Free Commands:</b>\n"
        "• /month — 📊 Household monthly summary &amp; member breakdown\n"
        "• /month last — 📊 View last month's family summary\n"
        "• /me — 👤 Your personal income, expenses &amp; top categories\n"
        "• /today — 📅 Summary of transactions logged today\n"
        "• /balance — 💰 Household net cash flow &amp; savings rate\n"
        "• /savings — 🏦 Cumulative savings &amp; all-time total balance\n"
        "• /history — 📜 3-month financial history (incomes, expenses, conversions)\n"
        "• /bills — ⏰ Upcoming fixed bills and dues\n"
        "• /timezone — 🌐 View or calibrate your active timezone\n"
        "• /family — 👥 Members, roles, currency &amp; plan quota\n"
        "• /invite — 🔗 Invite partner/roommate to your household\n"
        "• /export — 📁 Download all transactions in CSV or JSON\n"
        "• /undo — ↩️ Instantly revert your last logged expense\n"
        "• /privacy — 🛡️ Zero-Knowledge privacy &amp; third-party AI disclosures\n"
        "• /tos — 📜 Terms of Service &amp; Non-Advisory status\n"
        "• /delete_my_data — 🗑️ Permanently wipe your data from Clanomy\n\n"
        "🧠 <b>Conversational AI Assistant:</b>\n"
        "<i>Simply message me naturally to log expenses, ask questions, or edit:</i>\n"
        "• <i>\"35 sushi Tony\"</i> or <i>\"Paid 120 electric bill Maria\"</i>\n"
        "• <i>\"How much did we spend on groceries last week?\"</i>\n"
        "• <i>\"Change the last one to income\"</i>\n\n"
        "💡 <i>Note: Slash commands (/month, /me, etc.) are always 100% free and never consume your monthly AI quota!</i>"
        f"{AI_DISCLAIMER_FOOTER}"
        f"{TELEGRAM_NON_AFFILIATION_DISCLAIMER}"
    )

def format_timezone_overview(active_tz: str, fam_tz: str, user_tz: Optional[str], is_spanish: bool) -> str:
    """Overview message for the /timezone command."""
    if is_spanish:
        user_note = f" (personal: <code>{user_tz}</code>)" if user_tz else " (usando predeterminado del hogar)"
        return (
            f"🌐 <b>Configuración de Zona Horaria</b>\n\n"
            f"• Zona Horaria Activa: <b>{active_tz}</b>{user_note}\n"
            f"• Predeterminada del Hogar: <b>{fam_tz}</b>\n\n"
            f"📍 <b>Cómo actualizar:</b>\n"
            f"• Envía tu ubicación (📎 ➔ Ubicación) para detección automática.\n"
            f"• O escribe: <code>/timezone &lt;ciudad, país o UTC offset&gt;</code>\n\n"
            f"<i>Ejemplos:</i>\n"
            f"• <code>/timezone Buenos Aires</code>\n"
            f"• <code>/timezone Madrid</code>\n"
            f"• <code>/timezone -3</code>\n"
            f"• <code>/timezone America/Argentina/Buenos_Aires</code>\n\n"
            f"💡 <i>Tip: Los administradores pueden cambiar la del hogar con <code>/timezone --household &lt;zona&gt;</code>.</i>"
        )
    user_note = f" (personal: <code>{user_tz}</code>)" if user_tz else " (using household default)"
    return (
        f"🌐 <b>Timezone Settings</b>\n\n"
        f"• Active Timezone: <b>{active_tz}</b>{user_note}\n"
        f"• Household Default: <b>{fam_tz}</b>\n\n"
        f"📍 <b>How to update:</b>\n"
        f"• Send your location pin (📎 ➔ Location) to auto-detect.\n"
        f"• Or type: <code>/timezone &lt;city, country, or offset&gt;</code>\n\n"
        f"<i>Examples:</i>\n"
        f"• <code>/timezone Buenos Aires</code>\n"
        f"• <code>/timezone Madrid</code>\n"
        f"• <code>/timezone -3</code>\n"
        f"• <code>/timezone America/Argentina/Buenos_Aires</code>\n\n"
        f"💡 <i>Tip: Household admins can update the family default with <code>/timezone --household &lt;zone&gt;</code>.</i>"
    )

def format_timezone_unrecognized(input_tz: str, is_spanish: bool) -> str:
    """Error message when a timezone string is invalid."""
    escaped_input = html.escape(input_tz, quote=False)
    if is_spanish:
        return (
            f"❌ <b>Zona horaria no reconocida:</b> '{escaped_input}'\n\n"
            f"Por favor indica una ciudad conocida, nombre IANA o UTC offset:\n"
            f"• <code>/timezone Buenos Aires</code>\n"
            f"• <code>/timezone Madrid</code>\n"
            f"• <code>/timezone -3</code>\n"
            f"• <code>/timezone America/Argentina/Buenos_Aires</code>"
        )
    return (
        f"❌ <b>Unrecognized timezone:</b> '{escaped_input}'\n\n"
        f"Please provide a known city, IANA name, or UTC offset:\n"
        f"• <code>/timezone Buenos Aires</code>\n"
        f"• <code>/timezone Madrid</code>\n"
        f"• <code>/timezone -3</code>\n"
        f"• <code>/timezone America/Argentina/Buenos_Aires</code>"
    )

def format_timezone_admin_required(is_spanish: bool) -> str:
    """Error message when non-admin attempts to set household timezone."""
    if is_spanish:
        return "⛔ Solo los administradores del hogar pueden actualizar la zona horaria predeterminada de la familia."
    return "⛔ Only household administrators can update the family-wide default timezone."

def format_timezone_updated(normalized_tz: str, is_household: bool, is_spanish: bool) -> str:
    """Confirmation message after setting timezone."""
    if is_spanish:
        if is_household:
            return (
                f"✅ <b>¡Zona Horaria del Hogar Actualizada!</b>\n\n"
                f"El espacio familiar ahora está configurado en <b>{normalized_tz}</b>. "
                f"Todos los resúmenes diarios y mensuales se alinearán a esta hora local."
            )
        return (
            f"✅ <b>¡Zona Horaria Personal Actualizada!</b>\n\n"
            f"Tu zona horaria activa ahora está configurada en <b>{normalized_tz}</b>. "
            f"Tus reportes diarios (/today, /me) ahora están calibrados a tu hora local."
        )
    if is_household:
        return (
            f"✅ <b>Household Default Timezone Updated!</b>\n\n"
            f"The family workspace is now set to <b>{normalized_tz}</b>. "
            f"All daily and monthly summaries will be aligned to this local time."
        )
    return (
        f"✅ <b>Personal Timezone Updated!</b>\n\n"
        f"Your active timezone is now set to <b>{normalized_tz}</b>. "
        f"Your daily reports (/today, /me) are now calibrated to your local time."
    )

def format_delete_my_data_confirm_prompt(is_spanish: bool) -> str:
    """Warning and confirmation prompt for account/data deletion."""
    if is_spanish:
        return (
            "⚠️ <b>Confirmar Borrado Permanente de Datos (Derecho al Olvido - GDPR)</b>\n\n"
            "Esta acción es permanente e irreversible:\n"
            "• Todas tus transacciones personales y facturas programadas serán eliminadas para siempre.\n"
            "• Tu ID de Telegram y enlaces de perfil serán borrados de nuestra base de datos.\n\n"
            "Para confirmar, por favor responde con:\n"
            "<b>/delete_my_data confirmar</b> <i>(o escribe CONFIRMAR BORRAR)</i>"
        )
    return (
        "⚠️ <b>Confirm Permanent Data Erasure (GDPR Right to be Forgotten)</b>\n\n"
        "This action is permanent and irreversible:\n"
        "• All your personal transactions and scheduled bills will be permanently deleted.\n"
        "• Your Telegram ID and profile links will be wiped from our database.\n\n"
        "To confirm, please reply with:\n"
        "<b>/delete_my_data confirm</b> <i>(or type CONFIRM DELETE)</i>"
    )

def format_delete_my_data_success(is_spanish: bool) -> str:
    """Confirmation message when data is permanently erased."""
    if is_spanish:
        return (
            "✅ <b>Datos Eliminados Exitosamente</b>\n\n"
            "Tu cuenta personal, enlace de Telegram y registros financieros han sido borrados permanentemente de nuestra base de datos.\n\n"
            "¡Gracias por haber usado Clanomy! Si deseas volver en el futuro, simplemente envía /start."
        )
    return (
        "✅ <b>Data Purged Successfully</b>\n\n"
        "Your personal account, Telegram identity link, and associated financial records have been permanently erased from our database.\n\n"
        "Thank you for using Clanomy! If you ever wish to return, simply send /start."
    )

def format_delete_my_data_failure(is_spanish: bool) -> str:
    """Error message when data deletion fails."""
    if is_spanish:
        return "❌ No se pudieron borrar tus datos. Por favor contacta a support@clanomy.com."
    return "❌ Failed to delete your data. Please contact support@clanomy.com."

def format_location_calibrated(tz_name: str, is_spanish: bool = False) -> str:
    """Confirmation message after auto-calibrating timezone from a location pin."""
    if is_spanish:
        return (
            f"📍 <b>¡Ubicación Detectada y Calibrada!</b>\n\n"
            f"Tu zona horaria activa ha sido configurada automáticamente en <b>{tz_name}</b>.\n"
            f"Tus reportes diarios (/today, /me) y filtros de fecha ahora están alineados a tu hora local."
        )
    return (
        f"📍 <b>Location Detected & Calibrated!</b>\n\n"
        f"Your active timezone has been automatically set to <b>{tz_name}</b>.\n"
        f"Your daily summaries (/today, /me) and date filters are now aligned to your local time."
    )

def format_location_calibration_failed(is_spanish: bool = False) -> str:
    """Error message when timezone could not be determined from location pin."""
    if is_spanish:
        return "⚠️ No se pudo determinar la zona horaria a partir de esta ubicación. Por favor configúrala manualmente usando <code>/timezone &lt;ciudad&gt;</code>."
    return "⚠️ Could not determine the timezone from this location pin. Please configure it manually using <code>/timezone &lt;city&gt;</code>."
