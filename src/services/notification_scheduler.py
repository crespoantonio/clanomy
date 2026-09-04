import asyncio
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone, timedelta
from sqlmodel import Session, select, func
from sqlalchemy import Engine

from src.db.models import Family, User, Transaction
from src.db.session import engine as default_engine
from src.services.telegram_service import TelegramService
from src.core.config import settings
from src.core.subscription_config import FREE_TIER_MONTHLY_LIMIT
from src.services.subscription_service import reset_daily_quotas

logger = logging.getLogger(__name__)

def _to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def get_day_50_trial_families(session: Session, now: Optional[datetime] = None) -> List[Family]:
    """
    Queries active trial families where trial_ends_at is 10 days or fewer away (Day 50+),
    has not yet expired, and notified_day_50 is False.
    """
    current_time = _to_utc(now or datetime.now(timezone.utc))
    threshold = current_time + timedelta(days=10)

    statement = select(Family).where(
        Family.plan_type == "trial",
        Family.notified_day_50 == False,
        Family.trial_ends_at.is_not(None),
        Family.trial_ends_at <= threshold
    )
    candidates = session.exec(statement).all()

    results = []
    for fam in candidates:
        if fam.trial_ends_at:
            t_end = _to_utc(fam.trial_ends_at)
            # Must still be active (not yet reached Day 60 expiration)
            if t_end > current_time:
                results.append(fam)

    return results

def get_day_60_trial_families(session: Session, now: Optional[datetime] = None) -> List[Family]:
    """
    Queries expired trial families where trial_ends_at <= now,
    notified_day_60 is False, and without an active paid plan.
    """
    current_time = _to_utc(now or datetime.now(timezone.utc))

    statement = select(Family).where(
        Family.notified_day_60 == False,
        Family.trial_ends_at.is_not(None),
        Family.trial_ends_at <= current_time,
        Family.plan_type.notin_(["solo_pro", "family_pro", "lifetime_pro"])
    )
    candidates = session.exec(statement).all()

    results = []
    for fam in candidates:
        if fam.trial_ends_at:
            t_end = _to_utc(fam.trial_ends_at)
            if t_end <= current_time:
                results.append(fam)

    return results

def format_day_50_message(family: Family, tx_count: int, days_remaining: int) -> str:
    """
    Formats the Day 50 Nudge Message:
    - Summarizes value delivered (transactions tracked by family during the trial).
    - Warns that the 60-day trial will finish in dynamically calculated days.
    - Presents available tiers (Family Pro $9.99/mo, Solo Pro $4.99/mo) and /upgrade CTA.
    """
    tx_label = "1 transaction" if tx_count == 1 else f"{tx_count} transactions"
    return (
        f"⏳ <b>Your 60-Day Clanomy Duo Trial is Ending in {days_remaining} Days!</b>\n\n"
        f"During your trial, your workspace has tracked <b>{tx_label}</b> and kept your finances organized!\n\n"
        "To keep enjoying high-volume AI voice & text logging, real-time Notion sync, and multi-member collaboration without interruption, choose a plan:\n\n"
        "1️⃣ <b>Solo Pro ($4.99 / month)</b>\n"
        "• Unlimited text & voice expense & income logging (60 msgs/day)\n"
        "• Real-time Notion database mirroring\n"
        "• 1 User\n\n"
        "2️⃣ <b>Duo Pro ($7.99 / month)</b>\n"
        "• Everything in Solo Pro\n"
        "• 2 Partners with shared ledger (120 msgs/day pool)\n\n"
        "3️⃣ <b>Family Pro ($11.99 / month)</b>\n"
        "• Everything in Duo Pro\n"
        "• Up to 5 Family Members with shared ledger & Notion sync (300 msgs/day pool)\n\n"
        "Type /upgrade to choose your plan (or /upgrade annual to get 2 Months Free)!"
    )

def format_day_60_message(family: Optional[Family] = None) -> str:
    """
    Day 60 expired message sent once when trial ends.
    - Reassures user that all historical data, past Ask queries, and Notion sync remain 100% safe and intact.
    - Clearly explains the Free tier limits: shared transaction logs/month across up to 5 workspace members.
    - Provides a friendly /upgrade CTA.
    """
    return (
        "📦 <b>Your 60-Day Trial Has Ended — Welcome to Clanomy Free</b>\n\n"
        "Your workspace has transitioned to the <b>Free tier</b>.\n\n"
        "🛡️ <b>Your data is 100% safe:</b>\n"
        "• All your historical transactions, past Ask queries, and Notion sync remain completely safe and intact.\n"
        "• Nothing has been deleted, and no family members have been removed.\n\n"
        "📋 <b>Free Tier Limits:</b>\n"
        f"• {FREE_TIER_MONTHLY_LIMIT} free transaction logs per month shared across up to 5 workspace members.\n"
        "• Unlimited use of all pre-built slash commands (/month, /today, /balance, /bills, /me, /undo, /export) forever at $0.\n"
        "• Full access to query and view all your historical records.\n\n"
        "Want to unlock higher daily logs and features?\n"
        "Type /upgrade anytime to activate <b>Solo Pro</b> ($4.99/mo), <b>Duo Pro</b> ($7.99/mo), or <b>Family Pro</b> ($11.99/mo)!"
    )

async def process_day_50_notifications(
    session: Session,
    telegram_service: Optional[Any] = None,
    now: Optional[datetime] = None
) -> int:
    """
    Finds Day 50 trial candidate families, sends nudge messages to family members with telegram_id,
    and marks notified_day_50 = True.
    """
    service = telegram_service or TelegramService()
    candidates = get_day_50_trial_families(session, now=now)
    processed_count = 0
    current_time = _to_utc(now or datetime.now(timezone.utc))

    family_ids = [fam.id for fam in candidates]
    if not family_ids:
        return 0

    # Batch query transactions
    tx_counts = session.exec(
        select(Transaction.family_id, func.count(Transaction.id))
        .where(Transaction.family_id.in_(family_ids))
        .group_by(Transaction.family_id)
    ).all()
    tx_count_map = {fid: count for fid, count in tx_counts}

    # Batch query users
    users_by_family = {}
    all_users = session.exec(select(User).where(User.family_id.in_(family_ids))).all()
    for user in all_users:
        users_by_family.setdefault(user.family_id, []).append(user)

    for fam in candidates:
        tx_count = tx_count_map.get(fam.id, 0)
        
        days_remaining = 10
        if fam.trial_ends_at:
            t_end = _to_utc(fam.trial_ends_at)
            days_remaining = (t_end - current_time).days
            if days_remaining < 0:
                days_remaining = 0

        msg = format_day_50_message(fam, tx_count, days_remaining)
        users = users_by_family.get(fam.id, [])

        for user in users:
            if user.telegram_id:
                try:
                    await service.send_message(chat_id=user.telegram_id, text=msg)
                except Exception as e:
                    logger.error(f"Failed to send Day 50 notification to user {user.id} ({user.telegram_id}): {e}")

        fam.notified_day_50 = True
        session.add(fam)
        session.commit()
        processed_count += 1

    return processed_count

async def process_day_60_notifications(
    session: Session,
    telegram_service: Optional[Any] = None,
    now: Optional[datetime] = None
) -> int:
    """
    Finds Day 60 expired trial candidate families, transitions plan_type to 'free',
    sends reassurance and tier limits messages, and marks notified_day_60 = True.
    """
    service = telegram_service or TelegramService()
    candidates = get_day_60_trial_families(session, now=now)
    processed_count = 0

    family_ids = [fam.id for fam in candidates]
    if not family_ids:
        return 0

    users_by_family = {}
    all_users = session.exec(select(User).where(User.family_id.in_(family_ids))).all()
    for user in all_users:
        users_by_family.setdefault(user.family_id, []).append(user)

    for fam in candidates:
        msg = format_day_60_message(fam)
        users = users_by_family.get(fam.id, [])

        for user in users:
            if user.telegram_id:
                try:
                    await service.send_message(chat_id=user.telegram_id, text=msg)
                except Exception as e:
                    logger.error(f"Failed to send Day 60 notification to user {user.id} ({user.telegram_id}): {e}")

        fam.plan_type = "free"
        fam.max_members = 5
        fam.subscription_status = "expired"
        fam.notified_day_60 = True
        session.add(fam)
        session.commit()
        processed_count += 1

    return processed_count

async def run_daily_trial_notifications(
    session: Optional[Session] = None,
    engine: Optional[Engine] = None,
    telegram_service: Optional[Any] = None,
    now: Optional[datetime] = None,
    ignore_lock: bool = False
) -> Dict[str, int]:
    """
    Runs the full daily trial notification job (both Day 50 and Day 60 checks)
    and executes the silent 10:00 UTC fair-use daily quota reset.
    """
    # 1. Reset fair-use daily message quotas for all active workspaces (runs silently every day at 10:00 UTC)
    daily_resets = 0
    if session is not None:
        daily_resets = reset_daily_quotas(session)
    else:
        eng = engine or default_engine
        with Session(eng) as sess:
            daily_resets = reset_daily_quotas(sess)
    logger.info(f"Daily fair-use quota reset completed: {daily_resets} workspaces reset to 0.")

    if not settings.ENABLE_SUBSCRIPTIONS:
        logger.debug("ENABLE_SUBSCRIPTIONS is disabled (Self-Hosted mode). Skipping trial notifications.")
        return {"day_50_processed": 0, "day_60_processed": 0, "daily_quotas_reset": daily_resets}

    logger.info("Running daily trial notification lifecycle check...")

    if session is not None:
        day_50_count = await process_day_50_notifications(session, telegram_service=telegram_service, now=now)
        day_60_count = await process_day_60_notifications(session, telegram_service=telegram_service, now=now)
    else:
        eng = engine or default_engine
        with Session(eng) as sess:
            day_50_count = await process_day_50_notifications(sess, telegram_service=telegram_service, now=now)
            day_60_count = await process_day_60_notifications(sess, telegram_service=telegram_service, now=now)

    logger.info(f"Daily trial notifications complete: {day_50_count} Day-50, {day_60_count} Day-60.")
    return {
        "day_50_processed": day_50_count,
        "day_60_processed": day_60_count,
        "daily_quotas_reset": daily_resets
    }

class NotificationScheduler:
    """
    Background scheduler for daily trial lifecycle notifications.
    """
    def __init__(self, interval_seconds: int = 86400, engine: Optional[Engine] = None):
        self.interval_seconds = interval_seconds
        self.engine = engine or default_engine
        self._task: Optional[asyncio.Task] = None
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> asyncio.Task:
        if self._running and self._task and not self._task.done():
            return self._task
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"NotificationScheduler started with interval {self.interval_seconds}s")
        return self._task

    async def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        logger.info("NotificationScheduler stopped")

    async def _run_loop(self) -> None:
        while self._running:
            try:
                await run_daily_trial_notifications(engine=self.engine)
            except Exception as e:
                logger.error(f"Error in NotificationScheduler run loop: {e}", exc_info=True)

            try:
                await asyncio.sleep(self.interval_seconds)
            except asyncio.CancelledError:
                break

_global_scheduler: Optional[NotificationScheduler] = None

def start_notification_scheduler(engine: Optional[Engine] = None, interval_seconds: int = 86400) -> NotificationScheduler:
    global _global_scheduler
    if _global_scheduler is None or not _global_scheduler.is_running:
        _global_scheduler = NotificationScheduler(interval_seconds=interval_seconds, engine=engine)
        _global_scheduler.start()
    return _global_scheduler

async def stop_notification_scheduler() -> None:
    global _global_scheduler
    if _global_scheduler is not None:
        await _global_scheduler.stop()
        _global_scheduler = None
