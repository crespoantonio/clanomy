"""
Telegram HTML Message Templates for Clanomy.
Consolidates user-facing notification strings and onboarding messages.
"""

import html
from typing import Any, Optional, Tuple
from datetime import datetime, timezone
from src.core.config import settings
from src.db.models import Family, User
from src.core.subscription_config import FREE_TIER_MONTHLY_LIMIT

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

SELF_HOSTED_UPGRADE_MESSAGE = (
    "⏳ <b>Subscriptions Coming Soon</b>\n\n"
    "We are currently in private beta testing. Dedicated subscription tiers "
    "will be required in the future, but right now all features are <b>100% unlocked for free</b>."
)

DAILY_LIMIT_REACHED_MESSAGE = (
    "⚠️ <b>Daily Limit Reached</b>\n\n"
    "Your workspace has reached its fair-use limit of <b>{limit} messages</b> for today.\n\n"
    "All limits reset to zero daily at <b>10:00 UTC</b>."
)


def format_daily_limit_reached(limit: int, is_spanish: bool = False) -> str:
    """Localized fair-use daily message quota exhaustion notice."""
    if is_spanish:
        return (
            "⚠️ <b>Límite Diario Alcanzado</b>\n\n"
            f"Tu espacio ha alcanzado el límite de uso justo de <b>{limit} mensajes</b> para hoy.\n\n"
            "Todos los límites se reinician a cero diariamente a las <b>10:00 UTC</b>."
        )
    return DAILY_LIMIT_REACHED_MESSAGE.format(limit=limit)

LIFETIME_PRO_CONFIRMATION = (
    "⭐️ <b>Clanomy Lifetime Pro Active</b>\n\n"
    "You have unlocked permanent Lifetime Pro access to Clanomy. Enjoy unlimited voice and text logging forever!"
)

SOLO_PRO_CONFIRMATION = (
    "🎉 <b>Welcome to Clanomy Solo Pro!</b>\n\n"
    "Your subscription is now active. Enjoy unlimited AI voice and text logging, "
    "instant deterministic summaries, and private Notion mirroring."
)

DUO_PRO_CONFIRMATION = (
    "🎉 <b>Welcome to Clanomy Duo Pro!</b>\n\n"
    "Your subscription is now active. Enjoy unlimited AI voice and text logging for 2 partners, "
    "a shared couple ledger, per-member breakdowns, and real-time Notion database mirroring."
)

FAMILY_PRO_CONFIRMATION = (
    "🎉 <b>Welcome to Clanomy Family Pro!</b>\n\n"
    "Your subscription is now active. Enjoy unlimited AI voice and text logging for your entire household, "
    "shared family ledger, per-member breakdowns, and real-time Notion database mirroring."
)

SOLO_PRO_MEMBER_NOTICE = (
    "ℹ️ <b>Workspace Plan Update</b>\n\n"
    "Your workspace admin has updated the workspace to the <b>Solo Pro</b> plan. "
    "As a non-admin member, you can continue viewing past records, or upgrade to your own "
    "plan anytime using /upgrade."
)

REFUND_PROCESSED_MESSAGE = (
    "ℹ️ <b>Subscription Update:</b> Your payment was refunded. "
    "Your workspace has been moved to the Free plan. Type /upgrade to resubscribe anytime."
)

PLAN_EXPIRED_MESSAGE = (
    "🔒 <b>Clanomy Pro Required</b>\n\n"
    "This feature requires an active <b>Clanomy Pro</b> subscription. "
    "To unlock unlimited AI logging, family sharing, and Notion sync, "
    "please upgrade to <b>Clanomy Pro</b> using /upgrade."
)

UPGRADE_MENU_INTRO = (
    "⭐️ <b>Upgrade to Clanomy Pro</b>\n\n"
    "Choose the plan that fits your needs with secure billing (Apple Pay, Google Pay, or Credit/Debit Card):\n\n"
    "1️⃣ <b>Solo Pro ($4.99 / month)</b>\n"
    "• Unlimited text &amp; voice logging &amp; Notion sync for 1 User\n\n"
    "2️⃣ <b>Duo Pro ($7.99 / month) — Best for Couples ⭐</b>\n"
    "• Everything in Solo Pro for 2 Partners with shared ledger &amp; Notion sync\n\n"
    "3️⃣ <b>Family Pro ($11.99 / month)</b>\n"
    "• Everything in Duo Pro for up to 5 Family Members with shared ledger\n\n"
    "🎁 <i>Annual Savings: 2 Months Free on annual plans ($49.99, $79.99, $119.99/yr)!</i>\n\n"
    "📋 <b>Billing Terms &amp; Transparency:</b>\n"
    "• <b>Auto-Renewal:</b> Subscriptions auto-renew monthly or annually until cancelled.\n"
    "• <b>Cancel Anytime:</b> 1-tap cancellation via /billing to prevent future charges.\n"
    "• <b>Refund Policy:</b> All workspaces include a 60-day free trial. Paid subscriptions are non-refundable once billed.\n"
    "• By subscribing, you agree to our /tos and /privacy.\n\n"
    "<i>Tap a button below to open secure checkout and activate immediately:</i>"
)

UPGRADE_MENU_ANNUAL_INTRO = (
    "🎁 <b>Clanomy Pro Annual Plans (2 Months Free!)</b>\n\n"
    "Get a full year of unlimited AI financial tracking and save 17%:\n\n"
    "1️⃣ <b>Solo Pro Annual ($49.99 / year)</b> — ~$4.16/mo (1 User)\n\n"
    "2️⃣ <b>Duo Pro Annual ($79.99 / year)</b> — ~$6.66/mo (2 Partners ⭐)\n\n"
    "3️⃣ <b>Family Pro Annual ($119.99 / year)</b> — ~$9.99/mo (Up to 5 Members)\n\n"
    "📋 <b>Billing Terms:</b>\n"
    "• Subscriptions auto-renew annually until cancelled. Cancel anytime via /billing.\n"
    "• All plans include a 60-day free evaluation; paid subscriptions are non-refundable. Terms: /tos.\n\n"
    "<i>Tap a button below to activate your annual subscription!</i>"
)

BILLING_PORTAL_MESSAGE = (
    "⚙️ <b>Manage Your Subscription</b>\n\n"
    "You can update your payment method, view past receipts, or cancel your subscription anytime "
    "through your secure customer billing portal.\n\n"
    "<i>Tap the button below to open your billing portal:</i>"
)

SUBSCRIPTION_CANCELLED_MESSAGE = (
    "ℹ️ <b>Subscription Cancelled</b>\n\n"
    "Your subscription auto-renewal has been cancelled. "
    "You will retain full Pro access until the end of your current billing period."
)

SUBSCRIPTION_PAYMENT_FAILED_MESSAGE = (
    "⚠️ <b>Subscription Payment Failed</b>\n\n"
    "We were unable to process your subscription renewal. "
    "Please update your payment method in the billing portal to avoid service interruption."
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



def format_free_tier_exceeded(monthly_tx_count: int) -> str:
    return (
        f"⚠️ <b>Monthly AI Quota Exceeded ({monthly_tx_count}/20)</b>\n\n"
        "You've reached your free monthly AI quota for voice &amp; text logs.\n\n"
        "⚡ <b>Commands are ALWAYS 100% Free &amp; Unlimited:</b>\n"
        "• Type /month or /me for your spending breakdown\n"
        "• Type /today for today's logs\n"
        "• Type /bills for upcoming bill reminders\n"
        "• Type /balance for net cash flow &amp; savings\n\n"
        "⭐️ <b>Upgrade to Clanomy Pro:</b>\n"
        "Unlock unlimited AI voice/text logging and family sharing with /upgrade."
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


LEAVE_FAMILY_ADMIN_ACTIVE_PRO_BLOCKED = (
    "⚠️ <b>Active Subscription Notice</b>\n\n"
    "You are the billing administrator of this <b>Clanomy Pro</b> workspace, and your payment method is actively tied to this family.\n\n"
    "To prevent accidental recurring charges for a workspace you no longer use, <b>you cannot leave while your subscription is active</b>.\n\n"
    "<b>What to do:</b>\n"
    "1. Use /billing to open the customer portal and cancel your subscription (or downgrade to Solo Pro).\n"
    "2. Once your subscription is cancelled or converted, you can leave or manage your family."
)


def format_leave_family_admin_prompt(family_name: str, new_admin_name: str) -> str:
    escaped_family = html.escape(family_name, quote=False)
    escaped_admin = html.escape(new_admin_name, quote=False)
    return (
        f"⚠️ <b>Confirm Leaving as Family Admin</b>\n\n"
        f"You are currently the Admin of <b>{escaped_family}</b>.\n\n"
        "If you leave:\n"
        f"• Leadership will automatically transfer to <b>{escaped_admin}</b> (the oldest member).\n"
        "• The remaining members will continue sharing this family workspace.\n"
        "• You will be moved to your own new personal workspace.\n"
        "• <b>All your personal logged expenses &amp; transactions will be safely transferred with you.</b>\n\n"
        "To confirm leaving and transferring admin rights, please reply with:\n"
        "<b>CONFIRM LEAVE</b> <i>(or /leavefamily confirm)</i>"
    )


def format_leave_family_member_prompt(family_name: str, admin_name: str) -> str:
    escaped_family = html.escape(family_name, quote=False)
    escaped_admin = html.escape(admin_name, quote=False)
    return (
        f"⚠️ <b>Confirm Leaving Family</b>\n\n"
        f"You are currently a member of <b>{escaped_family}</b> (managed by {escaped_admin}).\n\n"
        "If you leave:\n"
        "• You will exit this shared family workspace.\n"
        "• You will be placed in your own private personal workspace on the Free tier.\n"
        "• <b>All your personal logged expenses &amp; transactions will be safely transferred with you.</b>\n"
        "• Other family members will no longer see your newly logged expenses.\n\n"
        "To confirm leaving, please reply with:\n"
        "<b>CONFIRM LEAVE</b> <i>(or /leavefamily confirm)</i>"
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


def format_non_admin_upgrade_intro(family_name: str, admin_name: str, is_spanish: bool = False) -> str:
    escaped_family = html.escape(family_name, quote=False)
    escaped_admin = html.escape(admin_name, quote=False)
    if is_spanish:
        return (
            f"⭐️ <b>Crea tu propia familia independiente</b>\n\n"
            f"Actualmente eres miembro de <b>{escaped_family}</b> (administrada por {escaped_admin}).\n\n"
            "⚠️ <b>Aviso importante:</b> Solo puedes tener acceso a <b>una sola familia a la vez</b>. Al mejorar tu plan, "
            f"saldrás de <b>{escaped_family}</b> y comenzarás tu propia familia como Administrador/a. "
            "<b>Todo tu historial personal de transacciones se migrará contigo</b> automáticamente:\n\n"
            "1️⃣ <b>Solo Pro ($4.99 / mes)</b> — Registro personal ilimitado y Notion privado (1 Usuario).\n\n"
            "2️⃣ <b>Duo Pro ($7.99 / mes) ⭐</b> — Espacio compartido para ti y tu pareja (2 Miembros).\n\n"
            "3️⃣ <b>Family Pro ($11.99 / mes)</b> — Tu propia familia de hasta 5 miembros con registro compartido.\n\n"
            "<i>Toca un botón abajo para elegir tu plan y comenzar tu propia familia:</i>"
        )
    return (
        f"⭐️ <b>Start Your Own Independent Family Workspace</b>\n\n"
        f"You are currently a member of <b>{escaped_family}</b> (managed by {escaped_admin}).\n\n"
        "⚠️ <b>Important Notice:</b> You can only have access to <b>one family workspace at a time</b>. Upgrading will "
        f"transition you out of <b>{escaped_family}</b> and start your own separate family workspace as Admin. "
        "<b>All your personal transaction history will migrate with you</b> seamlessly:\n\n"
        "1️⃣ <b>Solo Pro ($4.99 / mo)</b> — Unlimited personal AI logging &amp; private Notion sync (1 User).\n\n"
        "2️⃣ <b>Duo Pro ($7.99 / mo) ⭐</b> — Shared workspace for you and your partner (2 Members).\n\n"
        "3️⃣ <b>Family Pro ($11.99 / mo)</b> — Start your own family workspace for up to 5 members.\n\n"
        "<i>Tap a button below to choose your plan and launch your new workspace:</i>"
    )


def format_subscription_activated_message(
    tier_name: str,
    interval: str = "month",
    period_end: Optional[datetime] = None,
    is_spanish: bool = False
) -> str:
    """Sent ONLY to the paying user/admin upon successful checkout or tier upgrade."""
    escaped_tier = html.escape(tier_name, quote=False)
    cadence_str = "anual" if "year" in interval.lower() or "annual" in interval.lower() else "mensual"
    cadence_en = "yearly" if "year" in interval.lower() or "annual" in interval.lower() else "monthly"

    end_str = ""
    if period_end:
        date_formatted = format_date_localized(period_end, is_spanish=is_spanish)
        if is_spanish:
            end_str = f"• <b>Próxima fecha de renovación:</b> {date_formatted}\n"
        else:
            end_str = f"• <b>Next renewal date:</b> {date_formatted}\n"

    if is_spanish:
        return (
            f"🎉 <b>¡Suscripción Confirmada! Bienvenido a {escaped_tier}</b>\n\n"
            f"Tu pago se ha procesado con éxito y tu espacio familiar ya cuenta con <b>{escaped_tier}</b> activo.\n\n"
            f"📋 <b>Detalles de tu suscripción:</b>\n"
            f"• <b>Plan:</b> {escaped_tier}\n"
            f"• <b>Facturación:</b> Cobro automático {cadence_str}\n"
            f"{end_str}"
            f"• <b>Cancelación:</b> Puedes cancelar en cualquier momento desde /billing.\n\n"
            f"¡Ya tienes acceso a todas las funcionalidades premium! 🚀"
        )
    return (
        f"🎉 <b>Subscription Confirmed! Welcome to {escaped_tier}</b>\n\n"
        f"Your payment was successful and your family workspace is now active on <b>{escaped_tier}</b>.\n\n"
        f"📋 <b>Subscription Details:</b>\n"
        f"• <b>Plan:</b> {escaped_tier}\n"
        f"• <b>Billing:</b> Auto-renews {cadence_en}\n"
        f"{end_str}"
        f"• <b>Cancel Anytime:</b> You can cancel anytime directly via /billing.\n\n"
        f"You are all set with full premium access! 🚀"
    )


def format_subscription_canceled_message(
    tier_name: str,
    effective_end: Optional[datetime] = None,
    is_spanish: bool = False
) -> str:
    """Broadcast to ALL family members when a subscription cancellation is confirmed."""
    escaped_tier = html.escape(tier_name, quote=False)

    if effective_end:
        end_date_str = format_date_localized(effective_end, is_spanish=is_spanish)
        last_day_en = f"You will continue to have full access to <b>{escaped_tier}</b> until <b>{end_date_str}</b> (the end of your current billing period)."
        last_day_es = f"Seguirán teniendo acceso completo a <b>{escaped_tier}</b> hasta el <b>{end_date_str}</b> (fin del período de facturación actual)."
    else:
        last_day_en = f"Your access to <b>{escaped_tier}</b> has ended."
        last_day_es = f"El acceso a <b>{escaped_tier}</b> ha finalizado."

    if is_spanish:
        return (
            f"ℹ️ <b>Cancelación de Suscripción Confirmada</b>\n\n"
            f"Se ha procesado la cancelación de la suscripción a <b>{escaped_tier}</b> para su espacio familiar.\n\n"
            f"📅 <b>Período de acceso:</b>\n"
            f"{last_day_es}\n\n"
            f"📉 <b>Próximo plan (Gratuito):</b>\n"
            f"Luego de esa fecha, su espacio pasará al plan <b>Free</b> con un límite de <b>50 transacciones por mes</b> (hasta 5 miembros). "
            f"Todo su historial de gastos e información permanece 100% seguro y guardado.\n\n"
            f"💡 <i>Pueden volver a suscribirse a Premium en cualquier momento enviando /upgrade.</i>"
        )
    return (
        f"ℹ️ <b>Subscription Cancellation Confirmed</b>\n\n"
        f"The subscription for <b>{escaped_tier}</b> has been cancelled for your family workspace.\n\n"
        f"📅 <b>Access Period:</b>\n"
        f"{last_day_en}\n\n"
        f"📉 <b>Upcoming Plan (Free):</b>\n"
        f"After that date, your workspace will move to the <b>Free</b> plan with a limit of <b>50 transactions per month</b> (up to 5 members). "
        f"All your transaction history and data remain completely safe and intact.\n\n"
        f"💡 <i>You can resubscribe to Premium anytime by typing /upgrade.</i>"
    )


def format_family_split_notice(new_admin_name: str) -> str:
    escaped_admin = html.escape(new_admin_name, quote=False)
    return (
        "ℹ️ <b>Family Workspace Update</b>\n\n"
        "The workspace admin has switched to a personal Solo Pro plan. You and the remaining family members have been placed into a new shared family workspace on the Free tier.\n\n"
        f"👑 <b>{escaped_admin}</b> is your new workspace admin.\n\n"
        "Type /family to view your group, or /upgrade to unlock Family Pro anytime!"
    )


def format_member_graduated_notice(member_name: str, plan_name: str) -> str:
    escaped_member = html.escape(member_name, quote=False)
    escaped_plan = html.escape(plan_name, quote=False)
    return (
        "ℹ️ <b>Family Member Graduated</b>\n\n"
        f"<b>{escaped_member}</b> has upgraded to their own <b>{escaped_plan}</b> plan and transitioned to their own sovereign workspace. Their personal transactions have moved with them."
    )


# ─────────────────────────────────────────────────────────────────
# Orchestrator & Fast-Path Transaction / Query Message Templates
# ─────────────────────────────────────────────────────────────────

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


def format_batch_bills_tip(is_spanish: bool) -> str:
    """Returns pro-tip explaining /bills command alongside conversational query."""
    if is_spanish:
        return '\n\n💡 <i>Pregúntame "¿qué vence esta semana?" o envía /bills para ver todas tus facturas sin gastar créditos de IA.</i>'
    return '\n\n💡 <i>Ask me "what bills are due this week?" or send /bills to check upcoming bills without using your monthly AI quota.</i>'


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


def format_batch_transactions_header(incomes_count: int, expenses_count: int, total_count: int, is_spanish: bool) -> str:
    """Header for transaction section in batch responses."""
    if incomes_count > 0 and expenses_count == 0:
        return f"📋 <b>{total_count} Ingreso(s) Registrado(s):</b>\n\n" if is_spanish else f"📋 <b>{total_count} Income(s) Logged:</b>\n\n"
    elif expenses_count > 0 and incomes_count == 0:
        return f"📋 <b>{total_count} Gasto(s) Registrado(s):</b>\n\n" if is_spanish else f"📋 <b>{total_count} Expense(s) Logged:</b>\n\n"
    else:
        return f"📋 <b>{total_count} Transacciones Registradas:</b>\n\n" if is_spanish else f"📋 <b>{total_count} Transactions Logged:</b>\n\n"


def format_batch_total_pending(tot_str: str, is_spanish: bool) -> str:
    """Summary of total pending amount for bills in batch responses."""
    if is_spanish:
        return f"\n📌 <b>Total pendiente por pagar:</b> {tot_str}"
    return f"\n📌 <b>Total pending to pay:</b> {tot_str}"


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


def format_unmatched_bill_claim(concept_hint_or_raw: str, is_spanish: bool) -> str:
    """Response when a payment claim does not match an upcoming bill."""
    safe_hint = html.escape(concept_hint_or_raw)
    if is_spanish:
        return f"ℹ️ No encontré ninguna factura pendiente para '{safe_hint}'. ¿Cuánto fue el monto que pagaste?"
    return f"ℹ️ I couldn't find an upcoming bill matching '{safe_hint}'. What was the amount paid?"


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


def format_bill_settled_notice(matched_concept: str, remaining_pending: str, is_spanish: bool) -> str:
    """Notice appended when an expense settles an existing scheduled bill."""
    safe_concept = html.escape(matched_concept)
    if is_spanish:
        return f"\n\n✅ <b>¡Marcado como pagado!</b>\n💳 <b>{safe_concept}</b> registrado en tus gastos.\n⏳ Restante pendiente este mes: <b>{remaining_pending}</b>"
    return f"\n\n✅ <b>Marked as paid!</b>\n💳 <b>{safe_concept}</b> recorded in your expenses.\n⏳ Remaining pending this month: <b>{remaining_pending}</b>"


# ─────────────────────────────────────────────────────────────────
# Batch Line Items & Exchange Rate Formatters
# ─────────────────────────────────────────────────────────────────

def format_exchange_rate_line(sold_currency: str, rate_val: Optional[float], recv_currency: str, fmt_rate: str, is_spanish: bool) -> str:
    """Formats the calculated exchange rate line item."""
    if not rate_val:
        return ""
    if is_spanish:
        return f"\n• 📊 Cotización: 1 {sold_currency} = {fmt_rate}"
    return f"\n• 📊 Rate: 1 {sold_currency} = {fmt_rate}"


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


def format_batch_tx_item(icon: str, concept: str, fmt_amt: str, category: str) -> str:
    """Formats a single transaction row inside a batch confirmation message."""
    safe_concept = html.escape(concept)
    safe_category = html.escape(category)
    return f"• {icon} <b>{safe_concept}:</b> {fmt_amt} ({safe_category})\n"


# ─────────────────────────────────────────────────────────────────
# Bill Handler Presentation Templates & Cards
# ─────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────
# Command Handler & General Interaction Templates
# ─────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────
# Undo & Transaction Correction Templates
# ─────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────
# Currency, Family & Notion Handler Templates
# ─────────────────────────────────────────────────────────────────

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


def format_family_created_text(name: str, is_spanish: bool = False) -> str:
    """Confirmation text upon creating a new family workspace."""
    safe_name = html.escape(name, quote=False)
    if is_spanish:
        return f"✅ ¡El grupo familiar '{safe_name}' ha sido creado! Para invitar a otros, simplemente pídeme 'generar un link de invitación'."
    return f"✅ Family group '{safe_name}' has been created! To invite others, just ask me to 'generate an invite link'."


def format_family_invite_text(link: str, is_spanish: bool = False) -> str:
    """Invite link message for inviting partners/roommates to workspace."""
    if is_spanish:
        return f"🔗 Aquí tienes el link de invitación para tu familia:\n\n{link}\n\n⏳ Este enlace expirará en 1 hora."
    return f"🔗 Here is your family invite link:\n\n{link}\n\n⏳ This invite link will expire in 1 hour."


def format_family_info_text(
    name: str,
    plan_desc: str,
    tx_info: str,
    members_formatted: str,
    tx_count: int,
    invite_count: int,
    is_spanish: bool = False
) -> str:
    """Information summary card for the /family command."""
    safe_name = html.escape(name, quote=False)
    if is_spanish:
        return (
            f"👪 <b>Espacio Familiar: {safe_name}</b>\n"
            f"📋 <b>Plan:</b> {plan_desc}\n"
            f"📊 <b>Registros de IA:</b> {tx_info}\n\n"
            f"<b>Integrantes:</b>\n{members_formatted}\n\n"
            f"<b>Total de Transacciones:</b> {tx_count}\n"
            f"<b>Invitaciones Activas:</b> {invite_count}"
        )
    return (
        f"👪 <b>Family Workspace: {safe_name}</b>\n"
        f"📋 <b>Plan:</b> {plan_desc}\n"
        f"📊 <b>AI Logs:</b> {tx_info}\n\n"
        f"<b>Members:</b>\n{members_formatted}\n\n"
        f"<b>Total Transactions:</b> {tx_count}\n"
        f"<b>Active Invites:</b> {invite_count}"
    )


def format_member_removed_notice(is_spanish: bool = False) -> str:
    """Notification sent to a user removed from a household workspace."""
    if is_spanish:
        return (
            "ℹ️ Has sido removido del espacio familiar por el administrador. "
            "Se ha creado un nuevo espacio personal para ti con todo tu historial de transacciones intacto."
        )
    return (
        "ℹ️ You have been removed from the family workspace by the admin. "
        "A new personal workspace has been created for you with all your personal transaction history intact."
    )


def format_notion_pro_required(is_spanish: bool = False) -> str:
    """Paywall notice for Notion mirroring."""
    if is_spanish:
        return (
            "⭐️ <b>La Sincronización con Notion es una Función Pro</b>\n\n"
            "La sincronización de base de datos en tiempo real con Notion está disponible en los planes <b>Solo Pro</b> y <b>Family Pro</b>.\n\n"
            "Escribe /upgrade para conectar tu base de datos de Notion."
        )
    return (
        "⭐️ <b>Notion Mirroring is a Pro Feature</b>\n\n"
        "Real-time Notion database synchronization is available on <b>Solo Pro</b> and <b>Family Pro</b> plans.\n\n"
        "Type /upgrade to connect your Notion database."
    )


def format_notion_connect_instructions(is_spanish: bool = False) -> str:
    """Instructions on obtaining and providing an internal integration token."""
    if is_spanish:
        return (
            "🔗 <b>Conecta tu Espacio de Notion</b>\n\n"
            "Sigue estos rápidos pasos:\n"
            "1. Ve a https://www.notion.so/my-integrations y crea una <b>Integración Interna</b>.\n"
            "2. Copia el <b>Token Secreto de Integración</b>.\n"
            "3. Abre tu base de datos de gastos en Notion, haz clic en <b>•••</b> (arriba a la derecha) -> <b>Conexiones</b>, y selecciona tu integración.\n"
            "4. Responde aquí con:\n"
            "   <code>/notion connect &lt;tu_token_secreto&gt;</code>"
        )
    return (
        "🔗 <b>Connect your Notion Workspace</b>\n\n"
        "Follow these quick steps:\n"
        "1. Go to https://www.notion.so/my-integrations and create an <b>Internal Integration</b>.\n"
        "2. Copy the <b>Internal Integration Secret</b> (token).\n"
        "3. Open your Notion expenses database, click <b>•••</b> (top right) -> <b>Add connections</b>, and select your integration.\n"
        "4. Reply here with:\n"
        "   <code>/notion connect &lt;your_secret_token&gt;</code>"
    )


def format_notion_invalid_token(is_spanish: bool = False) -> str:
    """Error message when a provided Notion token is invalid."""
    if is_spanish:
        return "⚠️ <b>¡Token Inválido!</b> Por favor verifica tu Token Secreto de Integración e intenta de nuevo.\n\n🔒 <i>Tu mensaje con el token fue eliminado automáticamente por seguridad.</i>"
    return "⚠️ <b>Invalid Token!</b> Please check your Integration Secret and try again.\n\n🔒 <i>Your secret token message was automatically deleted for security.</i>"


def format_notion_connected_success(database_name: Any, database_id: str, is_spanish: bool = False) -> str:
    """Success message when Notion integration connects."""
    if isinstance(database_name, list) and database_name and isinstance(database_name[0], dict) and "plain_text" in database_name[0]:
        db_title = database_name[0]["plain_text"]
    else:
        db_title = str(database_name)
    safe_db = html.escape(db_title)
    if is_spanish:
        return (
            f"✅ <b>¡Espacio de Notion Conectado!</b>\n\n"
            f"📁 <b>Base de Datos:</b> {safe_db}\n"
            f"🆔 <b>ID:</b> <code>{database_id}</code>\n\n"
            "¡Tus transacciones ahora están vinculadas y listas para sincronización automática!\n\n"
            "🔒 <i>Tu mensaje con el token fue eliminado automáticamente por seguridad.</i>"
        )
    return (
        f"✅ <b>Notion Workspace Connected!</b>\n\n"
        f"📁 <b>Database:</b> {safe_db}\n"
        f"🆔 <b>ID:</b> <code>{database_id}</code>\n\n"
        "Your transactions are now linked and ready for automatic mirroring!\n\n"
        "🔒 <i>Your secret token message was automatically deleted for security.</i>"
    )


def format_notion_no_databases(is_spanish: bool = False) -> str:
    """Message when token is valid but no databases are shared."""
    if is_spanish:
        return (
            "⚠️ <b>¡No se encontraron bases de datos!</b>\n"
            "Tu token de Notion es válido, pero aún no has compartido ninguna base de datos con esta integración.\n\n"
            "Por favor abre tu base de datos en Notion, haz clic en <b>•••</b> -> <b>Conexiones</b>, selecciona tu integración y envía <code>/notion connect &lt;token&gt;</code> de nuevo.\n\n"
            "🔒 <i>Tu mensaje con el token fue eliminado automáticamente por seguridad.</i>"
        )
    return (
        "⚠️ <b>No databases found!</b>\n"
        "Your Notion token is valid, but no databases have been shared with this integration yet.\n\n"
        "Please open your Notion database, click <b>•••</b> -> <b>Add connections</b>, select your integration, and run <code>/notion connect &lt;token&gt;</code> again.\n\n"
        "🔒 <i>Your secret token message was automatically deleted for security.</i>"
    )


def format_notion_status_message(
    is_connected: bool,
    db_name: Optional[str] = None,
    db_id: Optional[str] = None,
    connected_at_str: Optional[str] = None,
    is_spanish: bool = False
) -> str:
    """Status report for Notion workspace connection."""
    if is_spanish:
        if is_connected:
            return (
                f"📊 <b>Estado de Conexión con Notion:</b> Conectado ✅\n"
                f"📁 <b>Base de Datos:</b> {html.escape(db_name or 'N/A')}\n"
                f"🆔 <b>ID de Base de Datos:</b> <code>{db_id or 'N/A'}</code>\n"
                f"📅 <b>Conectado:</b> {connected_at_str or 'N/A'}"
            )
        return "📊 <b>Estado de Conexión con Notion:</b> No Conectado ❌"
    if is_connected:
        return (
            f"📊 <b>Notion Connection Status:</b> Connected ✅\n"
            f"📁 <b>Target Database:</b> {html.escape(db_name or 'N/A')}\n"
            f"🆔 <b>Database ID:</b> <code>{db_id or 'N/A'}</code>\n"
            f"📅 <b>Connected:</b> {connected_at_str or 'N/A'}"
        )
    return "📊 <b>Notion Connection Status:</b> Not Connected ❌"


def format_notion_disconnected(is_spanish: bool = False) -> str:
    """Notice upon disconnecting Notion."""
    if is_spanish:
        return "🔌 <b>Notion Desconectado</b>\nLa conexión con tu espacio de Notion ha sido eliminada. La sincronización de transacciones está desactivada."
    return "🔌 <b>Notion Disconnected</b>\nYour Notion workspace connection has been removed. Transaction mirroring is now disabled."


# ─────────────────────────────────────────────────────────────────
# Telegram Webhook Flow Templates
# ─────────────────────────────────────────────────────────────────

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


def format_monthly_free_limit_reached(is_admin: bool, limit: int = FREE_TIER_MONTHLY_LIMIT, is_spanish: bool = False) -> str:
    """Monthly free quota exhaustion message, customized by admin role."""
    if is_spanish:
        if is_admin:
            return (
                f"⛔ <b>Límite Mensual Gratuito Alcanzado ({limit}/{limit} registros)</b>\n\n"
                f"Tu familia ha alcanzado el límite de {limit} registros gratuitos con IA para este mes (Cuota Alcanzada). "
                "Escribe /upgrade para desbloquear registros ilimitados con IA, o continúa usando nuestros comandos gratuitos ilimitados (/month, /me, /balance, /bills)."
            )
        return (
            f"⛔ <b>Límite Mensual Gratuito Alcanzado ({limit}/{limit} registros)</b>\n\n"
            f"Tu familia ha alcanzado el límite de {limit} registros gratuitos con IA para este mes (Cuota Alcanzada). "
            "Por favor pídele al administrador de tu hogar que actualice el espacio mediante /upgrade, o continúa usando nuestros comandos gratuitos ilimitados (/month, /me, /balance, /bills)."
        )
    if is_admin:
        return (
            f"⛔ <b>Monthly Free Limit Reached ({limit}/{limit} logs)</b>\n\n"
            f"Your family has reached the limit of {limit} free transaction logs for this month (Quota Reached). "
            "Type /upgrade to unlock unlimited AI logs, or continue using our unlimited free commands (/month, /me, /balance, /bills)."
        )
    return (
        f"⛔ <b>Monthly Free Limit Reached ({limit}/{limit} logs)</b>\n\n"
        f"Your family has reached the limit of {limit} free transaction logs for this month (Quota Reached). "
        "Please ask your family admin to upgrade the workspace via /upgrade, or continue using our unlimited free commands (/month, /me, /balance, /bills)."
    )


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


def format_subscription_expired_notice(limit: int = FREE_TIER_MONTHLY_LIMIT, is_spanish: bool = False) -> str:
    """Alert message sent to admin when subscription payment fails or expires."""
    if is_spanish:
        return (
            "⚠️ <b>Suscripción Expirada o Fallida:</b> El pago de tu espacio familiar falló o expiró. "
            f"Tu espacio ha pasado al plan Gratuito ({limit} registros/mes). "
            "Todo tu historial, registros anteriores y sincronización con Notion permanecen 100% seguros."
        )
    return (
        "⚠️ <b>Subscription Expired/Failed:</b> Your workspace payment failed or expired. "
        f"Your workspace has transitioned to the Free tier ({limit} logs/month). "
        "All your historical data, past entries, and Notion sync remain 100% safe."
    )


