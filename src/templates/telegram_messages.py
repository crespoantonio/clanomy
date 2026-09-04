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
    "<i>Tap a button below to open secure checkout and activate immediately:</i>"
)

UPGRADE_MENU_ANNUAL_INTRO = (
    "🎁 <b>Clanomy Pro Annual Plans (2 Months Free!)</b>\n\n"
    "Get a full year of unlimited AI financial tracking and save 17%:\n\n"
    "1️⃣ <b>Solo Pro Annual ($49.99 / year)</b> — ~$4.16/mo (1 User)\n\n"
    "2️⃣ <b>Duo Pro Annual ($79.99 / year)</b> — ~$6.66/mo (2 Partners ⭐)\n\n"
    "3️⃣ <b>Family Pro Annual ($119.99 / year)</b> — ~$9.99/mo (Up to 5 Members)\n\n"
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
        "Type /help anytime for Notion sync, family settings, and CSV/JSON export."
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
