"""
Billing and Subscriptions Service.
Handles plan tier presentation, /upgrade command menus,
and self-serve customer billing portal links.
"""

import logging
from typing import Optional
from fastapi import BackgroundTasks
from sqlmodel import Session, select

from src.core.config import settings
from src.core.subscription_config import (
    SUBSCRIPTION_TIERS,
    get_tier_config,
)
from src.db.models import Family, User
from src.services.telegram_service import TelegramService
from src.services.family_service import FamilyService
from src.templates.telegram_messages import (
    SELF_HOSTED_UPGRADE_MESSAGE,
    UPGRADE_MENU_INTRO,
    UPGRADE_MENU_ANNUAL_INTRO,
    BILLING_PORTAL_MESSAGE,
    format_non_admin_upgrade_intro,
)

logger = logging.getLogger(__name__)


class BillingService:
    def __init__(self, telegram_service: Optional[TelegramService] = None):
        self.telegram_service = telegram_service or TelegramService()

    async def _get_checkout_or_info_url(self, plan_code: str) -> str:
        """
        Returns an interactive deep-link for the tier.
        When a new payment processor is integrated, this will generate hosted checkout URLs.
        """
        bot_username = await self.telegram_service.get_bot_username()
        if bot_username and bot_username != "UnknownBot":
            return f"https://t.me/{bot_username}?start=upgrade_{plan_code}"
        return f"https://t.me/clanomy_bot?start=upgrade_{plan_code}"

    async def handle_upgrade_command(
        self,
        background_tasks: BackgroundTasks,
        text: str,
        user: User,
        family: Optional[Family],
        chat_id: int
    ) -> dict:
        """
        Handles /upgrade commands:
        - When ENABLE_SUBSCRIPTIONS is False: returns friendly self-hosted / closed beta message.
        - When ENABLE_SUBSCRIPTIONS is True: displays subscription tier options.
        """
        if not settings.ENABLE_SUBSCRIPTIONS:
            background_tasks.add_task(
                self.telegram_service.send_message,
                chat_id=chat_id,
                text=SELF_HOSTED_UPGRADE_MESSAGE
            )
            return {"status": "ok"}

        parts = text.split()
        arg = "_".join(parts[1:]).lower() if len(parts) > 1 else ""

        fam_service = FamilyService()
        is_admin = getattr(user, "is_admin", False)
        if not is_admin and family and user and getattr(user, "id", None):
            try:
                is_admin = fam_service.is_family_admin(family.id, user.id)
            except Exception:
                is_admin = True
        elif not user or not family:
            is_admin = True

        is_graduation = bool(family and not is_admin)

        if arg in ("annual", "yearly", "annually"):
            solo_annual_url = await self._get_checkout_or_info_url("solo_pro_annual")
            duo_annual_url = await self._get_checkout_or_info_url("duo_pro_annual")
            fam_annual_url = await self._get_checkout_or_info_url("family_pro_annual")
            reply_markup = {
                "inline_keyboard": [
                    [{"text": "💳 Solo Pro Annual ($49.99/yr)", "url": solo_annual_url}],
                    [{"text": "💳 Duo Pro Annual ($79.99/yr) ⭐", "url": duo_annual_url}],
                    [{"text": "💳 Family Pro Annual ($119.99/yr)", "url": fam_annual_url}]
                ]
            }
            background_tasks.add_task(
                self.telegram_service.send_message,
                chat_id=chat_id,
                text=UPGRADE_MENU_ANNUAL_INTRO,
                reply_markup=reply_markup
            )
            return {"status": "ok"}

        elif arg in ("solo", "solo_pro", "single"):
            solo_url = await self._get_checkout_or_info_url("solo_pro")
            reply_markup = {
                "inline_keyboard": [
                    [{"text": "💳 Upgrade to Solo Pro ($4.99/mo)", "url": solo_url}]
                ]
            }
            if is_graduation:
                intro = (
                    "⭐️ <b>Upgrade to Your Own Solo Pro Workspace</b>\n\n"
                    "Upgrading will create your own personal workspace and migrate all your personal transactions with you.\n\n"
                    "Tap below to select your upgrade:"
                )
            else:
                intro = "⭐️ <b>Upgrade to Clanomy Solo Pro</b>\n\nTap below to select your upgrade:"

            background_tasks.add_task(
                self.telegram_service.send_message,
                chat_id=chat_id,
                text=intro,
                reply_markup=reply_markup
            )
            return {"status": "ok"}

        elif arg in ("duo", "duo_pro", "couple", "couples", "pair"):
            duo_url = await self._get_checkout_or_info_url("duo_pro")
            reply_markup = {
                "inline_keyboard": [
                    [{"text": "💳 Duo Pro ($7.99/mo)", "url": duo_url}]
                ]
            }
            if is_graduation:
                intro = (
                    "👫 <b>Upgrade to Your Own Duo Pro Workspace</b>\n\n"
                    "Upgrading will create your own couples workspace as Admin for you and your partner, migrating all your personal transactions.\n\n"
                    "Tap below to select your upgrade:"
                )
            else:
                intro = "👫 <b>Upgrade to Clanomy Duo Pro</b>\n\nTap below to select your upgrade for 2 partners:"

            background_tasks.add_task(
                self.telegram_service.send_message,
                chat_id=chat_id,
                text=intro,
                reply_markup=reply_markup
            )
            return {"status": "ok"}

        elif arg in ("family", "family_pro", "fam"):
            fam_url = await self._get_checkout_or_info_url("family_pro")
            reply_markup = {
                "inline_keyboard": [
                    [{"text": "💳 Upgrade to Family Pro ($11.99/mo)", "url": fam_url}]
                ]
            }
            if is_graduation:
                intro = (
                    "👨‍👩‍👧‍👦 <b>Start Your Own Family Pro Workspace</b>\n\n"
                    "Upgrading will create your own family workspace as Admin and migrate all your personal transactions.\n\n"
                    "Tap below to select your upgrade for up to 5 family members:"
                )
            else:
                intro = "👨‍👩‍👧‍👦 <b>Upgrade to Clanomy Family Pro</b>\n\nTap below to select your upgrade for up to 5 family members:"

            background_tasks.add_task(
                self.telegram_service.send_message,
                chat_id=chat_id,
                text=intro,
                reply_markup=reply_markup
            )
            return {"status": "ok"}

        else:
            solo_url = await self._get_checkout_or_info_url("solo_pro")
            duo_url = await self._get_checkout_or_info_url("duo_pro")
            fam_url = await self._get_checkout_or_info_url("family_pro")
            reply_markup = {
                "inline_keyboard": [
                    [{"text": "💳 Solo Pro ($4.99 / mo)", "url": solo_url}],
                    [{"text": "💳 Duo Pro ($7.99 / mo) ⭐", "url": duo_url}],
                    [{"text": "💳 Family Pro ($11.99 / mo)", "url": fam_url}]
                ]
            }
            if is_graduation and family:
                admin_name = "your Admin"
                try:
                    with Session(fam_service.engine) as s:
                        members = s.exec(select(User).where(User.family_id == family.id)).all()
                        admin_user = next((u for u in members if fam_service.is_family_admin(family.id, u.id)), None)
                        if admin_user:
                            admin_name = f"@{admin_user.username}" if admin_user.username else (admin_user.full_name or "Admin")
                except Exception:
                    pass
                intro_text = format_non_admin_upgrade_intro(family.name, admin_name)
            else:
                intro_text = UPGRADE_MENU_INTRO

            background_tasks.add_task(
                self.telegram_service.send_message,
                chat_id=chat_id,
                text=intro_text,
                reply_markup=reply_markup
            )
            return {"status": "ok"}

    async def handle_billing_command(
        self,
        background_tasks: BackgroundTasks,
        user: User,
        family: Optional[Family],
        chat_id: int
    ) -> dict:
        """
        Handles /billing command by serving the user their secure customer portal URL.
        """
        if not settings.ENABLE_SUBSCRIPTIONS:
            background_tasks.add_task(
                self.telegram_service.send_message,
                chat_id=chat_id,
                text=SELF_HOSTED_UPGRADE_MESSAGE
            )
            return {"status": "ok"}

        portal_url = family.customer_portal_url if family else None
        if portal_url:
            reply_markup = {
                "inline_keyboard": [
                    [{"text": "⚙️ Open Billing Portal", "url": portal_url}]
                ]
            }
            background_tasks.add_task(
                self.telegram_service.send_message,
                chat_id=chat_id,
                text=BILLING_PORTAL_MESSAGE,
                reply_markup=reply_markup
            )
        else:
            background_tasks.add_task(
                self.telegram_service.send_message,
                chat_id=chat_id,
                text=(
                    "ℹ️ <b>No Active Billing Portal Found</b>\n\n"
                    "Your workspace does not have an active subscription link.\n"
                    "Type /upgrade to view available subscription plans."
                )
            )
        return {"status": "ok"}
