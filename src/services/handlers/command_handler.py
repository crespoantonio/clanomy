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

    async def handle_month(self, user: User, family: Family, args: str = "") -> str:
        """
        /month or /month last
        Generates full family monthly overview with member-by-member breakdown.
        """
        args_lower = (args or "").strip().lower()
        timeframe = "last_month" if any(w in args_lower for w in ["last", "pasado", "anterior"]) else "this_month"
        
        ref_time = datetime.now(timezone.utc)
        start_time, end_time = self.query_service._resolve_date_range(timeframe, None, None, ref_time)
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
        return format_month_summary(qr, family_name=family.name, timeframe_label=month_label)

    async def handle_me(self, user: User, family: Family, args: str = "") -> str:
        """
        /me or /me last
        Generates caller's personal monthly summary (income, expenses, net savings, top categories).
        """
        args_lower = (args or "").strip().lower()
        timeframe = "last_month" if any(w in args_lower for w in ["last", "pasado", "anterior"]) else "this_month"
        
        ref_time = datetime.now(timezone.utc)
        start_time, end_time = self.query_service._resolve_date_range(timeframe, None, None, ref_time)
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
        return format_me_summary(qr, user_name=user_display, timeframe_label=month_label)

    async def handle_today(self, user: User, family: Family, args: str = "") -> str:
        """
        /today or /today me
        Generates summary of transactions recorded today.
        """
        ref_time = datetime.now(timezone.utc)
        start_time, end_time = self.query_service._resolve_date_range("today", None, None, ref_time)
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

        return format_today_summary(qr, is_family=(not only_me))

    async def handle_bills(self, user: User, family: Family, args: str = "") -> str:
        """
        /bills or /bills next
        Shows upcoming pending scheduled bills.
        """
        args_lower = (args or "").strip().lower()
        timeframe = "next_month" if any(w in args_lower for w in ["next", "proximo", "siguiente"]) else "this_month"

        ref_time = datetime.now(timezone.utc)
        start_time, end_time = self.query_service._resolve_date_range(timeframe, None, None, ref_time)

        bills = await asyncio.to_thread(
            self.query_service._fetch_and_decrypt_scheduled_bills,
            family.id, start_time, end_time, "pending"
        )

        tf_label = "Next Month" if timeframe == "next_month" else "This Month"
        return format_bills_summary(bills, timeframe_label=tf_label)

    async def handle_balance(self, user: User, family: Family, args: str = "") -> str:
        """
        /balance
        Shows net cash flow, earnings vs spendings, and savings rate.
        """
        ref_time = datetime.now(timezone.utc)
        start_time, end_time = self.query_service._resolve_date_range("this_month", None, None, ref_time)
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

        return format_balance_summary(qr)

    async def handle_undo(self, user: User, family: Family) -> str:
        """
        /undo
        Instantly reverts the user's latest recorded transaction.
        """
        from src.services.ai_orchestrator import AIOrchestrator
        orchestrator = AIOrchestrator()
        return await asyncio.to_thread(orchestrator._handle_transaction_undo, user.id, None)

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
