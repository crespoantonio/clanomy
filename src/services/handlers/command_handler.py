from typing import Optional, List
from datetime import datetime, timezone
from uuid import UUID
import logging
from sqlmodel import Session, select
import asyncio

from src.db.session import engine
from src.db.models import User, Family, Transaction
from src.core.config import settings
from src.services.query.service import QueryService
from src.services.query.models import ParsedQueryIntent, QueryResult
from src.services.query.aggregator import (
    aggregate_transactions,
    aggregate_by_category,
    aggregate_by_member
)
from src.services.query.formatters import (
    format_month_summary,
    format_me_summary,
    format_today_summary,
    format_bills_summary,
    format_balance_summary
)

logger = logging.getLogger(__name__)

class CommandHandler:
    """
    Handles pre-built deterministic Telegram commands without invoking the AI engine.
    Runs 100% in Python & SQL, incurs $0 AI cost, executes in <40ms, and never counts
    towards the monthly AI free-tier quota.
    """

    def __init__(self):
        self.query_service = QueryService()

    def _resolve_active_timezone(self, user: User, family: Family) -> str:
        return getattr(user, "timezone", None) or getattr(family, "timezone", None) or getattr(settings, "DEFAULT_TIMEZONE", "America/Argentina/Buenos_Aires")

    async def handle_month(self, user: User, family: Family, args: str = "") -> str:
        """
        /month or /month last
        Generates full family monthly overview with member-by-member breakdown.
        """
        args_lower = (args or "").strip().lower()
        timeframe = "last_month" if any(w in args_lower for w in ["last", "pasado", "anterior"]) else "this_month"
        active_tz = self._resolve_active_timezone(user, family)
        
        ref_time = datetime.now(timezone.utc)
        start_time, end_time = self.query_service._resolve_date_range(timeframe, None, None, ref_time, tz_name=active_tz)
        effective_currency = family.default_currency or settings.DEFAULT_CURRENCY or "USD"

        transactions = await asyncio.to_thread(
            self.query_service._fetch_and_decrypt_transactions,
            family.id, start_time, end_time, None, None, None
        )

        aggregation = aggregate_transactions(
            transactions=transactions,
            timeframe=timeframe,
            start_time=start_time,
            end_time=end_time,
            primary_currency=effective_currency,
            calculate_daily=True
        )

        member_breakdown = aggregate_by_member(
            transactions=transactions,
            timeframe=timeframe,
            start_time=start_time,
            end_time=end_time,
            primary_currency=effective_currency,
            overall_total=aggregation.total_expenses
        )

        qr = QueryResult(
            intent=ParsedQueryIntent(intent="spending_summary", timeframe=timeframe, scope="family"),
            resolved_start_time=start_time,
            resolved_end_time=end_time,
            transactions=transactions,
            total_count=len(transactions),
            aggregation=aggregation,
            member_breakdown=member_breakdown
        )

        month_label = start_time.strftime("%B %Y")
        return format_month_summary(qr, family_name=family.name, timeframe_label=month_label, tz_name=active_tz)

    async def handle_me(self, user: User, family: Family, args: str = "") -> str:
        """
        /me or /me last
        Generates caller's personal monthly summary (income, expenses, net savings, top categories).
        """
        args_lower = (args or "").strip().lower()
        timeframe = "last_month" if any(w in args_lower for w in ["last", "pasado", "anterior"]) else "this_month"
        active_tz = self._resolve_active_timezone(user, family)
        
        ref_time = datetime.now(timezone.utc)
        start_time, end_time = self.query_service._resolve_date_range(timeframe, None, None, ref_time, tz_name=active_tz)
        effective_currency = family.default_currency or settings.DEFAULT_CURRENCY or "USD"

        all_family_txs = await asyncio.to_thread(
            self.query_service._fetch_and_decrypt_transactions,
            family.id, start_time, end_time, None, None, None
        )
        my_transactions = [tx for tx in all_family_txs if tx.user_id == user.id]

        aggregation = aggregate_transactions(
            transactions=my_transactions,
            timeframe=timeframe,
            start_time=start_time,
            end_time=end_time,
            primary_currency=effective_currency,
            calculate_daily=True
        )

        category_breakdown = aggregate_by_category(
            transactions=my_transactions,
            timeframe=timeframe,
            start_time=start_time,
            end_time=end_time,
            primary_currency=effective_currency,
            overall_total=aggregation.total_expenses
        )

        qr = QueryResult(
            intent=ParsedQueryIntent(intent="spending_summary", timeframe=timeframe, scope="personal"),
            resolved_start_time=start_time,
            resolved_end_time=end_time,
            transactions=my_transactions,
            total_count=len(my_transactions),
            aggregation=aggregation,
            category_breakdown=category_breakdown
        )

        user_display = user.full_name or user.username or "You"
        month_label = start_time.strftime("%B %Y")
        return format_me_summary(qr, user_name=user_display, timeframe_label=month_label, tz_name=active_tz)

    async def handle_today(self, user: User, family: Family, args: str = "") -> str:
        """
        /today or /today me
        Generates summary of transactions recorded today.
        """
        active_tz = self._resolve_active_timezone(user, family)
        ref_time = datetime.now(timezone.utc)
        start_time, end_time = self.query_service._resolve_date_range("today", None, None, ref_time, tz_name=active_tz)
        effective_currency = family.default_currency or settings.DEFAULT_CURRENCY or "USD"

        args_lower = (args or "").strip().lower()
        only_me = any(w in args_lower for w in ["me", "yo"])

        transactions = await asyncio.to_thread(
            self.query_service._fetch_and_decrypt_transactions,
            family.id, start_time, end_time, None, None, None
        )

        if only_me:
            transactions = [tx for tx in transactions if tx.user_id == user.id]

        aggregation = aggregate_transactions(
            transactions=transactions,
            timeframe="today",
            start_time=start_time,
            end_time=end_time,
            primary_currency=effective_currency,
            calculate_daily=False
        )

        qr = QueryResult(
            intent=ParsedQueryIntent(intent="spending_summary", timeframe="today", scope="personal" if only_me else "family"),
            resolved_start_time=start_time,
            resolved_end_time=end_time,
            transactions=transactions,
            total_count=len(transactions),
            aggregation=aggregation
        )

        return format_today_summary(qr, is_family=(not only_me), tz_name=active_tz)

    async def handle_bills(self, user: User, family: Family, args: str = "") -> str:
        """
        /bills or /bills next
        Shows upcoming pending scheduled bills.
        """
        args_lower = (args or "").strip().lower()
        timeframe = "next_month" if any(w in args_lower for w in ["next", "proximo", "siguiente"]) else "this_month"
        active_tz = self._resolve_active_timezone(user, family)

        ref_time = datetime.now(timezone.utc)
        start_time, end_time = self.query_service._resolve_date_range(timeframe, None, None, ref_time, tz_name=active_tz)

        bills = await asyncio.to_thread(
            self.query_service._fetch_and_decrypt_scheduled_bills,
            family.id, start_time, end_time, "pending"
        )

        tf_label = "Next Month" if timeframe == "next_month" else "This Month"
        return format_bills_summary(bills, timeframe_label=tf_label, tz_name=active_tz)

    async def handle_balance(self, user: User, family: Family, args: str = "") -> str:
        """
        /balance
        Shows net cash flow, earnings vs spendings, and savings rate.
        """
        active_tz = self._resolve_active_timezone(user, family)
        ref_time = datetime.now(timezone.utc)
        start_time, end_time = self.query_service._resolve_date_range("this_month", None, None, ref_time, tz_name=active_tz)
        effective_currency = family.default_currency or settings.DEFAULT_CURRENCY or "USD"

        transactions = await asyncio.to_thread(
            self.query_service._fetch_and_decrypt_transactions,
            family.id, start_time, end_time, None, None, None
        )

        aggregation = aggregate_transactions(
            transactions=transactions,
            timeframe="this_month",
            start_time=start_time,
            end_time=end_time,
            primary_currency=effective_currency,
            calculate_daily=False
        )

        qr = QueryResult(
            intent=ParsedQueryIntent(intent="net_cash_flow", timeframe="this_month", scope="family"),
            resolved_start_time=start_time,
            resolved_end_time=end_time,
            transactions=transactions,
            total_count=len(transactions),
            aggregation=aggregation
        )

        return format_balance_summary(qr, tz_name=active_tz)

    async def handle_timezone(self, user: User, family: Family, args: str = "") -> str:
        """
        /timezone or /timezone Madrid
        Displays or updates the active timezone for the user or household.
        """
        from src.services.family_service import FamilyService
        from src.services.query.date_resolver import validate_and_normalize_timezone
        
        args_clean = (args or "").strip()
        family_service = FamilyService()

        if not args_clean:
            active_tz = self._resolve_active_timezone(user, family)
            user_tz = getattr(user, "timezone", None)
            fam_tz = getattr(family, "timezone", None) or getattr(settings, "DEFAULT_TIMEZONE", "America/Argentina/Buenos_Aires")
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

        # Check if setting for household
        is_household = False
        tz_input = args_clean
        if "--household" in tz_input.lower() or "-h" in tz_input.lower():
            tz_input = tz_input.replace("--household", "").replace("-h", "").strip()
            is_household = True

        normalized = validate_and_normalize_timezone(tz_input)
        if not normalized:
            return (
                f"❌ <b>Unrecognized timezone:</b> '{tz_input}'\n\n"
                f"Please provide a known city, IANA name, or UTC offset:\n"
                f"• <code>/timezone Buenos Aires</code>\n"
                f"• <code>/timezone Madrid</code>\n"
                f"• <code>/timezone -3</code>\n"
                f"• <code>/timezone America/Argentina/Buenos_Aires</code>"
            )

        if is_household:
            is_admin = family_service.is_family_admin(family.id, user.id)
            if not is_admin:
                return "⛔ Only household administrators can update the family-wide default timezone."
            await asyncio.to_thread(family_service.set_family_timezone, family.id, normalized)
            family.timezone = normalized
            return (
                f"✅ <b>Household Default Timezone Updated!</b>\n\n"
                f"The family workspace is now set to <b>{normalized}</b>. "
                f"All daily and monthly summaries will be aligned to this local time."
            )
        else:
            await asyncio.to_thread(family_service.set_user_timezone, user.id, normalized)
            user.timezone = normalized
            return (
                f"✅ <b>Personal Timezone Updated!</b>\n\n"
                f"Your active timezone is now set to <b>{normalized}</b>. "
                f"Your daily reports (/today, /me) are now calibrated to your local time."
            )

    async def handle_undo(self, user: User, family: Family) -> str:
        """
        /undo
        Instantly reverts the user's latest recorded transaction.
        """
        from src.services.handlers.transaction_handler import handle_transaction_undo
        return await asyncio.to_thread(handle_transaction_undo, user.id, None)

    async def handle_help(self, user: User, family: Family) -> str:
        """
        /help
        Displays interactive command guide and AI tips.
        """
        return (
            "✨ <b>Clanomy — Household Finance Assistant</b>\n\n"
            "⚡ <b>Unlimited Free Commands:</b>\n"
            "• /month — 📊 Household monthly summary & member breakdown\n"
            "• /month last — 📊 View last month's family summary\n"
            "• /me — 👤 Your personal income, expenses & top categories\n"
            "• /today — 📅 Summary of transactions logged today\n"
            "• /balance — 💰 Household net cash flow & savings rate\n"
            "• /bills — ⏰ Upcoming fixed bills and dues\n"
            "• /timezone — 🌐 View or calibrate your active timezone\n"
            "• /family — 👥 Members, roles, currency & plan quota\n"
            "• /invite — 🔗 Invite partner/roommate to your household\n"
            "• /export — 📁 Download all transactions in CSV\n"
            "• /undo — ↩️ Instantly revert your last logged expense\n\n"
            "🧠 <b>Conversational AI Assistant:</b>\n"
            "<i>Simply message me naturally to log expenses, ask questions, or edit:</i>\n"
            "• <i>\"35 sushi Tony\"</i> or <i>\"Paid 120 electric bill Maria\"</i>\n"
            "• <i>\"How much did we spend on groceries last week?\"</i>\n"
            "• <i>\"Change the last one to income\"</i>\n\n"
            "💡 <i>Note: Slash commands (/month, /me, etc.) are always 100% free and never consume your monthly AI quota!</i>"
        )

