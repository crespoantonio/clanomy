"""
Telegram HTML Message Templates for Clanomy.
Consolidates user-facing notification strings and onboarding messages.
"""

from typing import Optional
from datetime import datetime, timezone
from src.core.config import settings
from src.db.models import Family, User
from src.core.subscription_config import FREE_TIER_MONTHLY_LIMIT

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
    f"Your workspace has transitioned to the Free tier ({FREE_TIER_MONTHLY_LIMIT} logs/month). "
    "All your historical data, past entries, and Notion sync remain 100% safe."
)

PLAN_EXPIRED_MESSAGE = (
    "🔒 <b>Clanomy Pro Required</b>\n\n"
    "Your workspace access period has ended. To continue logging transactions and querying your financial history, "
    "please upgrade to <b>Clanomy Pro</b> using /upgrade."
)

UPGRADE_MENU_INTRO = (
    "⭐️ <b>Upgrade to Clanomy Pro</b>\n\n"
    "Choose the plan that fits your needs with secure billing (Apple Pay, Google Pay, or Credit/Debit Card):\n\n"
    "1️⃣ <b>Solo Pro ($4.99 / month)</b>\n"
    "• Unlimited text & voice expense & income logging\n"
    "• Real-time Notion database mirroring\n"
    "• AI Natural language queries & cash flow insights\n"
    "• CSV & JSON financial exports\n"
    "• 1 User\n\n"
    "2️⃣ <b>Family Pro ($9.99 / month)</b>\n"
    "• Everything in Solo Pro\n"
    "• Up to 5 Family Members with shared ledger\n"
    "• Per-member spending attribution & budget visibility\n\n"
    "🎁 <i>Annual Savings: Type <code>/upgrade annual</code> to get 2 Months Free on annual plans ($49.99 & $99.99/yr)!</i>\n\n"
    "<i>Tap a button below to open secure checkout and activate immediately!</i>"
)

UPGRADE_MENU_ANNUAL_INTRO = (
    "🎁 <b>Clanomy Pro Annual Plans (2 Months Free!)</b>\n\n"
    "Get a full year of unlimited AI financial tracking and save 17%:\n\n"
    "1️⃣ <b>Solo Pro Annual ($49.99 / year)</b> — ~$4.16/mo (Save $10)\n"
    "• 1 User, Unlimited AI logging & Notion sync\n\n"
    "2️⃣ <b>Family Pro Annual ($99.99 / year)</b> — ~$8.33/mo (Save $20)\n"
    "• Up to 5 Members, Shared Ledger & Notion sync\n\n"
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
        "• 💵 <b>Currency:</b> Set your default currency with <code>/currency USD</code> <i>(or ARS, EUR, MXN, etc.)</i>\n"
        f"• 🌐 <b>Timezone:</b> For privacy, Telegram doesn't share your location with bots automatically. Your timezone defaults to <b>{getattr(settings, 'DEFAULT_TIMEZONE', 'America/Argentina/Buenos_Aires')}</b>. Calibrate anytime with /timezone or by sharing your location pin (📎 ➔ Location).\n\n"
        "<b>Try sending me something right now:</b>\n"
        "• 🎙️ <i>Send a voice note:</i> \"Coffee 4\"\n"
        "• 💬 <i>Type an expense:</i> \"Spent 45 on groceries\"\n"
        "• 💰 <i>Type an income:</i> \"Got paid 3,000 salary\"\n"
        "• 📊 <i>Ask a question:</i> \"How much did we spend this month?\"\n\n"
        "Type /help anytime for Notion sync, family invites, and data export."
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
    return (
        f"⚠️ <b>Confirm Leaving as Family Admin</b>\n\n"
        f"You are currently the Admin of <b>{family_name}</b>.\n\n"
        "If you leave:\n"
        f"• Leadership will automatically transfer to <b>{new_admin_name}</b> (the oldest member).\n"
        "• The remaining members will continue sharing this family workspace.\n"
        "• You will be moved to your own new personal workspace.\n"
        "• <b>All your personal logged expenses & transactions will be safely transferred with you.</b>\n\n"
        "To confirm leaving and transferring admin rights, please reply with:\n"
        "<b>CONFIRM LEAVE</b> <i>(or /leavefamily confirm)</i>"
    )


def format_leave_family_member_prompt(family_name: str, admin_name: str) -> str:
    return (
        f"⚠️ <b>Confirm Leaving Family</b>\n\n"
        f"You are currently a member of <b>{family_name}</b> (managed by {admin_name}).\n\n"
        "If you leave:\n"
        "• You will exit this shared family workspace.\n"
        "• You will be placed in your own private personal workspace on the Free tier.\n"
        "• <b>All your personal logged expenses & transactions will be safely transferred with you.</b>\n"
        "• Other family members will no longer see your newly logged expenses.\n\n"
        "To confirm leaving, please reply with:\n"
        "<b>CONFIRM LEAVE</b> <i>(or /leavefamily confirm)</i>"
    )


def format_non_admin_upgrade_intro(family_name: str, admin_name: str) -> str:
    return (
        f"⭐️ <b>Upgrade to Your Own Sovereign Workspace</b>\n\n"
        f"You are currently a member of <b>{family_name}</b> (managed by {admin_name}).\n\n"
        "Upgrading will create your own independent workspace and <b>migrate all your personal transaction history with you</b>, without disrupting the current family group:\n\n"
        "1️⃣ <b>Solo Pro ($4.99 / mo)</b> — Unlimited personal AI logging & private Notion sync.\n\n"
        "2️⃣ <b>Family Pro ($9.99 / mo)</b> — Start your own family! Unlimited AI logging, shared ledger, and invite up to 4 members.\n\n"
        "<i>Tap a button below to choose your plan and launch your new workspace:</i>"
    )


def format_family_split_notice(new_admin_name: str) -> str:
    return (
        "ℹ️ <b>Family Workspace Update</b>\n\n"
        "The workspace admin has switched to a personal Solo Pro plan. You and the remaining family members have been placed into a new shared family workspace on the Free tier.\n\n"
        f"👑 <b>{new_admin_name}</b> is your new workspace admin.\n\n"
        "Type /family to view your group, or /upgrade to unlock Family Pro anytime!"
    )


def format_member_graduated_notice(member_name: str, plan_name: str) -> str:
    return (
        "ℹ️ <b>Family Member Graduated</b>\n\n"
        f"<b>{member_name}</b> has upgraded to their own <b>{plan_name}</b> plan and transitioned to their own sovereign workspace. Their personal transactions have moved with them."
    )

