"""
Telegram HTML Message Templates for Clanomy.
Consolidates user-facing notification strings and onboarding messages.
"""

import html
from typing import Optional
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


def format_welcome_message(user: User, family: Optional[Family], from_user: dict) -> str:
    plan_badge = ""
    command_bullet = "• ⚡ <b>Instant Commands:</b> Type /month, /me, /today, /bills, or /balance for the fastest responses!"

    if family:
        if family.plan_type == "trial":
            days_left = 60
            if family.trial_ends_at:
                now_utc = datetime.now(timezone.utc)
                trial_end = family.trial_ends_at if family.trial_ends_at.tzinfo else family.trial_ends_at.replace(tzinfo=timezone.utc)
                days_left = max(0, (trial_end - now_utc).days)
            plan_badge = f"⭐️ <b>60-Day Duo Pro Trial:</b> {days_left} days remaining of shared logs (60/day pool for 2 partners) &amp; Notion sync!\n\n"
            command_bullet = "• ⚡ <b>Instant Commands:</b> Type /month, /me, /today, /bills, or /balance for the fastest responses!"
        elif family.plan_type == "free":
            used = getattr(family, "monthly_tx_count", 0)
            plan_badge = f"📦 <b>Plan:</b> Free Plan ({used}/20 AI logs used this month).\n\n"
            command_bullet = "• ⚡ <b>Unlimited Free Commands:</b> Type /month, /me, /today, /bills, or /balance anytime — they are 100% free and don't count against your 20 monthly AI logs!"
        elif family.plan_type == "solo_pro":
            plan_badge = "⭐️ <b>Plan:</b> Solo Pro (Active — Unlimited text &amp; voice logs, personal workspace).\n\n"
        elif family.plan_type == "duo_pro":
            plan_badge = "👫 <b>Plan:</b> Duo Pro (Active — Unlimited text &amp; voice logs, shared ledger for 2 partners).\n\n"
        elif family.plan_type == "family_pro":
            plan_badge = "👨‍👩‍👧‍👦 <b>Plan:</b> Family Pro (Active — Unlimited text &amp; voice logs, shared family ledger &amp; Notion sync).\n\n"
        elif family.plan_type == "lifetime_pro":
            plan_badge = "👑 <b>Plan:</b> Lifetime Pro (Permanent active status).\n\n"

    raw_user_name = user.full_name or from_user.get("first_name") or "User"
    user_display_name = html.escape(raw_user_name, quote=False)
    project_name = html.escape(getattr(settings, "PROJECT_NAME", "Clanomy"), quote=False)
    tz_name = html.escape(str(getattr(settings, "DEFAULT_TIMEZONE", "America/Argentina/Buenos_Aires")), quote=False)

    teamwork_bullet = "👥 <i>Teamwork: Use /invite to add your partner or household members.</i>"
    if family:
        if family.plan_type in ("trial", "duo_pro"):
            teamwork_bullet = "👥 <i>Teamwork: Use /invite to add your partner (or upgrade to Family Pro for up to 5 members).</i>"
        elif family.plan_type == "solo_pro":
            teamwork_bullet = "👥 <i>Teamwork: Solo Pro is for 1 user. Upgrade to Duo Pro or Family Pro with /upgrade to invite members.</i>"

    return (
        f"👋 <b>Welcome to {project_name}, {user_display_name}!</b>\n\n"
        f"{plan_badge}"
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


def format_non_admin_upgrade_intro(family_name: str, admin_name: str) -> str:
    escaped_family = html.escape(family_name, quote=False)
    escaped_admin = html.escape(admin_name, quote=False)
    return (
        f"⭐️ <b>Upgrade to Your Own Sovereign Workspace</b>\n\n"
        f"You are currently a member of <b>{escaped_family}</b> (managed by {escaped_admin}).\n\n"
        "Upgrading will create your own independent workspace and <b>migrate all your personal transaction history with you</b>, without disrupting the current family group:\n\n"
        "1️⃣ <b>Solo Pro ($4.99 / mo)</b> — Unlimited personal AI logging &amp; private Notion sync (1 User).\n\n"
        "2️⃣ <b>Duo Pro ($7.99 / mo)</b> — Shared workspace for you and your partner (2 Members).\n\n"
        "3️⃣ <b>Family Pro ($11.99 / mo)</b> — Start your own family workspace for up to 5 members.\n\n"
        "<i>Tap a button below to choose your plan and launch your new workspace:</i>"
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


