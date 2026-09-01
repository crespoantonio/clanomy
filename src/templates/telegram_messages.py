"""
Telegram HTML Message Templates for Clanomy.
Consolidates user-facing notification strings and onboarding messages.
"""

from typing import Optional
from datetime import datetime, timezone
from src.core.config import settings
from src.db.models import Family, User

UNAUTHORIZED_ACCESS_MESSAGE = (
    "🔒 <b>Private Instance</b>\n\n"
    "This Clanomy bot instance is private and restricted to authorized users."
)

UNSUPPORTED_FORMAT_MESSAGE = (
    "⚠️ <b>Unsupported Format</b>\n\n"
    "Clanomy only accepts native voice notes (hold the mic 🎙️ icon) or text messages (e.g. <i>'Spent $24 on lunch'</i>)."
)

SELF_HOSTED_UPGRADE_MESSAGE = (
    "🏠 <b>Self-Hosted Clanomy</b>\n\n"
    "You are running a self-hosted instance of Clanomy. All features (unlimited voice and text logging, "
    "multi-member family sharing, Notion syncing, natural language insights, and data exports) are "
    "<b>fully unlocked</b> with no quotas or subscriptions required!"
)

LIFETIME_PRO_CONFIRMATION = (
    "⭐️ <b>Clanomy Lifetime Pro Active</b>\n\n"
    "Your workspace is enjoying permanent Lifetime Pro status. Thank you for your payment!"
)

SOLO_PRO_CONFIRMATION = (
    "🎉 <b>Welcome to Clanomy Solo Pro!</b>\n\n"
    "Your subscription is now active! You have unlocked unlimited voice and text transaction logging "
    "and AI queries for your personal workspace. Thank you for supporting Clanomy!"
)

FAMILY_PRO_CONFIRMATION = (
    "🎉 <b>Welcome to Clanomy Family Pro!</b>\n\n"
    "Your subscription is now active! You have unlocked unlimited voice and text transaction logging, "
    "shared family ledger for up to 5 members, and real-time Notion mirroring. "
    "Thank you for supporting Clanomy!"
)

SOLO_PRO_MEMBER_NOTICE = (
    "ℹ️ <b>Workspace Plan Update</b>\n\n"
    "Your workspace admin has updated the workspace to the <b>Solo Pro</b> plan. "
    "Solo Pro is designed for an individual user.\n\n"
    "To start your own personal workspace and keep logging transactions, "
    "simply type /leavefamily."
)

REFUND_PROCESSED_MESSAGE = (
    "ℹ️ <b>Subscription Update:</b> Your payment was refunded. "
    "Your workspace has transitioned to the Free tier (30 logs/month). "
    "All your historical data, past entries, and Notion sync remain 100% safe."
)

PLAN_EXPIRED_MESSAGE = (
    "🔒 <b>Clanomy Pro Required</b>\n\n"
    "Your workspace access period has ended. To continue logging transactions and querying your financial history, "
    "please upgrade to <b>Clanomy Pro</b> using /upgrade."
)

UPGRADE_MENU_INTRO = (
    "⭐️ <b>Upgrade to Clanomy Pro</b>\n\n"
    "Choose the plan that fits your needs with seamless, auto-renewing Telegram Stars billing (Apple Pay / Google Pay / Card):\n\n"
    "1️⃣ <b>Solo Pro (200 Stars / month)</b>\n"
    "• Unlimited text & voice expense & income logging\n"
    "• Real-time Notion database mirroring\n"
    "• AI Natural language queries & cash flow insights\n"
    "• CSV & JSON financial exports\n"
    "• 1 User\n\n"
    "2️⃣ <b>Family Pro (450 Stars / month)</b>\n"
    "• Everything in Solo Pro\n"
    "• Up to 5 Family Members with shared ledger\n"
    "• Per-member spending attribution & budget visibility\n\n"
    "🎁 <i>Annual Savings: Type <code>/upgrade annual</code> to get 2 Months Free on annual subscriptions (2,000 & 4,500 Stars)!</i>\n\n"
    "<i>Invoices are attached below. Tap <b>Pay</b> on your chosen tier to activate immediately!</i>"
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


def format_free_tier_exceeded(monthly_tx_count: int) -> str:
    return (
        f"⚠️ <b>Monthly AI Quota Exceeded ({monthly_tx_count}/20)</b>\n\n"
        "You've reached your free monthly AI quota for voice & text logs.\n\n"
        "⚡ <b>Commands are ALWAYS 100% Free & Unlimited:</b>\n"
        "• Type /month or /me for your spending breakdown\n"
        "• Type /today for today's logs\n"
        "• Type /bills for upcoming bill reminders\n"
        "• Type /balance for net cash flow & savings\n\n"
        "⭐️ <b>Upgrade to Clanomy Pro:</b>\n"
        "Unlock unlimited AI voice/text logging and family sharing with /upgrade."
    )


def format_welcome_message(user: User, family: Optional[Family], from_user: dict) -> str:
    plan_badge = ""
    command_bullet = "• ⚡ <b>Instant Commands:</b> Type /month, /me, /today, /bills, or /balance for instant (<40ms) summaries!"

    if family:
        if family.plan_type == "trial":
            days_left = 60
            if family.trial_ends_at:
                now_utc = datetime.now(timezone.utc)
                trial_end = family.trial_ends_at if family.trial_ends_at.tzinfo else family.trial_ends_at.replace(tzinfo=timezone.utc)
                days_left = max(0, (trial_end - now_utc).days)
            plan_badge = f"⭐️ <b>60-Day Family Pro Trial:</b> {days_left} days remaining of unlimited logs & family features!\n\n"
            command_bullet = "• ⚡ <b>Instant Commands:</b> Type /month, /me, /today, /bills, or /balance for instant (<40ms) responses!"
        elif family.plan_type == "free":
            used = getattr(family, "monthly_tx_count", 0)
            plan_badge = f"📦 <b>Plan:</b> Free Plan ({used}/20 AI logs used this month).\n\n"
            command_bullet = "• ⚡ <b>Unlimited Free Commands:</b> Type /month, /me, /today, /bills, or /balance anytime — they are 100% free and don't count against your 20 monthly AI logs!"
        elif family.plan_type == "solo_pro":
            plan_badge = "⭐️ <b>Plan:</b> Solo Pro (Active — Unlimited text & voice logs, personal workspace).\n\n"
        elif family.plan_type == "family_pro":
            plan_badge = "👨‍👩‍👧‍👦 <b>Plan:</b> Family Pro (Active — Unlimited text & voice logs, shared family ledger & Notion sync).\n\n"
        elif family.plan_type == "lifetime_pro":
            plan_badge = "👑 <b>Plan:</b> Lifetime Pro (Permanent active status).\n\n"

    user_display_name = user.full_name or from_user.get("first_name") or "User"
    return (
        f"👋 <b>Welcome to {settings.PROJECT_NAME}, {user_display_name}!</b>\n\n"
        f"{plan_badge}"
        "<b>How Clanomy Works:</b>\n"
        "• 🎙️ <b>AI Logging:</b> Send voice notes or text anytime (<i>\"Coffee 4\"</i>, <i>\"Earned 3,500 salary\"</i>, <i>\"Internet 50 due the 15th\"</i>).\n"
        f"{command_bullet}\n\n"
        "💡 <b>Quick Setup:</b>\n"
        "Set your household default currency:\n"
        "👉 <code>/currency USD</code> <i>(or ARS, EUR, MXN, GBP, etc.)</i>\n\n"
        "<b>Try sending me something right now:</b>\n"
        "• 🎙️ <i>Send a voice note:</i> \"Coffee 4\"\n"
        "• 💬 <i>Type an expense:</i> \"Spent 45 on groceries\"\n"
        "• 💰 <i>Type an income:</i> \"Got paid 3,000 salary\"\n"
        "• 📊 <i>Ask a question:</i> \"How much did we spend this month?\"\n\n"
        "Type /help anytime for Notion sync, family invites, and data export."
    )
