"""
Telegram Billing and Subscriptions Service.
Handles Stars pre-checkout validation, successful payment provisioning, refunds, and /upgrade invoicing.
"""

import uuid
import logging
from typing import Optional
from fastapi import BackgroundTasks
from sqlmodel import Session, select

from src.core.config import settings
from src.db.models import Family, User
from src.services.telegram_service import TelegramService
from src.services.family_service import FamilyService
from src.services.subscription_service import (
    validate_invoice_payload,
    extract_plan_and_family_id,
    handle_successful_payment,
    handle_subscription_expiry
)
from src.templates.telegram_messages import (
    SELF_HOSTED_UPGRADE_MESSAGE,
    LIFETIME_PRO_CONFIRMATION,
    SOLO_PRO_CONFIRMATION,
    FAMILY_PRO_CONFIRMATION,
    SOLO_PRO_MEMBER_NOTICE,
    REFUND_PROCESSED_MESSAGE,
    UPGRADE_MENU_INTRO
)

logger = logging.getLogger(__name__)


class TelegramBillingService:
    def __init__(self, telegram_service: Optional[TelegramService] = None):
        self.telegram_service = telegram_service or TelegramService()

    async def handle_pre_checkout_query(self, pre_checkout: dict) -> dict:
        """Validates and acknowledges Telegram Stars pre-checkout queries."""
        query_id = pre_checkout.get("id")
        if not query_id:
            logger.error("Missing pre_checkout_query id")
            return {"status": "error", "message": "Missing query_id"}
        invoice_payload = pre_checkout.get("invoice_payload", "")

        try:
            validate_invoice_payload(invoice_payload)
            await self.telegram_service.answer_pre_checkout_query(
                pre_checkout_query_id=query_id,
                ok=True
            )
        except ValueError as e:
            logger.warning(f"Rejecting pre_checkout_query {query_id} for payload '{invoice_payload}': {e}")
            await self.telegram_service.answer_pre_checkout_query(
                pre_checkout_query_id=query_id,
                ok=False,
                error_message="Invalid or unsupported subscription plan."
            )
        return {"status": "ok"}

    def handle_successful_payment_event(
        self,
        session: Session,
        background_tasks: BackgroundTasks,
        message: dict,
        fallback_family: Optional[Family],
        chat_id: int
    ) -> dict:
        """Processes successful Telegram Star subscription payments and notifies users."""
        successful_payment = message.get("successful_payment", {})
        invoice_payload = successful_payment.get("invoice_payload", "")
        charge_id = successful_payment.get("telegram_payment_charge_id")
        expiration_timestamp = successful_payment.get("subscription_expiration_date")

        try:
            _, payload_family_id = extract_plan_and_family_id(invoice_payload)
        except ValueError:
            payload_family_id = None

        target_family = fallback_family
        if payload_family_id:
            try:
                fam_uuid = uuid.UUID(payload_family_id)
                db_fam = session.get(Family, fam_uuid)
                if db_fam:
                    target_family = db_fam
            except ValueError:
                pass

        if not target_family:
            logger.error(f"Cannot process payment: target family could not be resolved for payload '{invoice_payload}'")
            return {"status": "error", "message": "Family not found"}

        existing_members = []
        was_multi_member = False
        if target_family:
            existing_members = session.exec(
                select(User).where(User.family_id == target_family.id)
            ).all()
            was_multi_member = len(existing_members) > 1

        result = handle_successful_payment(
            session=session,
            family=target_family,
            invoice_payload=invoice_payload,
            charge_id=charge_id,
            expiration_timestamp=expiration_timestamp
        )

        if target_family.plan_type == "lifetime_pro" or result.get("status") == "ignored_lifetime":
            background_tasks.add_task(self.telegram_service.send_message, chat_id=chat_id, text=LIFETIME_PRO_CONFIRMATION)
        elif target_family.plan_type == "solo_pro":
            background_tasks.add_task(self.telegram_service.send_message, chat_id=chat_id, text=SOLO_PRO_CONFIRMATION)

            if was_multi_member:
                fam_service = FamilyService()
                for member in existing_members:
                    if member.telegram_id and not fam_service.is_family_admin(target_family.id, member.id):
                        background_tasks.add_task(
                            self.telegram_service.send_message,
                            chat_id=member.telegram_id,
                            text=SOLO_PRO_MEMBER_NOTICE
                        )
        elif target_family.plan_type == "family_pro":
            background_tasks.add_task(self.telegram_service.send_message, chat_id=chat_id, text=FAMILY_PRO_CONFIRMATION)

        return {"status": "ok"}

    def handle_refunded_payment_event(
        self,
        session: Session,
        background_tasks: BackgroundTasks,
        message: dict,
        fallback_family: Optional[Family],
        chat_id: int
    ) -> dict:
        """Processes refunded Telegram Star payments and downgrades workspace to Free tier."""
        refunded_payment = message.get("refunded_payment", {})
        invoice_payload = refunded_payment.get("invoice_payload", "")

        try:
            _, payload_family_id = extract_plan_and_family_id(invoice_payload)
        except ValueError:
            payload_family_id = None

        target_family = fallback_family
        if payload_family_id:
            try:
                fam_uuid = uuid.UUID(payload_family_id)
                db_fam = session.get(Family, fam_uuid)
                if db_fam:
                    target_family = db_fam
            except ValueError:
                pass

        if target_family and target_family.plan_type != "lifetime_pro":
            handle_subscription_expiry(session, target_family)
            background_tasks.add_task(self.telegram_service.send_message, chat_id=chat_id, text=REFUND_PROCESSED_MESSAGE)
        return {"status": "ok"}

    def handle_upgrade_command(
        self,
        background_tasks: BackgroundTasks,
        text: str,
        user: User,
        family: Optional[Family],
        chat_id: int
    ) -> dict:
        """Processes /upgrade commands and issues Telegram Stars invoices."""
        if not settings.ENABLE_SUBSCRIPTIONS:
            background_tasks.add_task(self.telegram_service.send_message, chat_id=chat_id, text=SELF_HOSTED_UPGRADE_MESSAGE)
            return {"status": "ok"}

        parts = text.split()
        arg = "_".join(parts[1:]).lower() if len(parts) > 1 else None
        family_id_str = str(family.id) if family else (str(user.family_id) if user and user.family_id else "")

        if arg in ["solo", "solo_pro", "single"]:
            background_tasks.add_task(
                self.telegram_service.send_subscription_invoice,
                chat_id=chat_id,
                plan_type="solo_pro",
                family_id=family_id_str
            )
            return {"status": "ok"}
        elif arg in ["family", "family_pro", "fam"]:
            background_tasks.add_task(
                self.telegram_service.send_subscription_invoice,
                chat_id=chat_id,
                plan_type="family_pro",
                family_id=family_id_str
            )
            return {"status": "ok"}
        elif arg in ["solo_annual", "solo_yearly", "annual_solo", "yearly_solo"]:
            background_tasks.add_task(
                self.telegram_service.send_subscription_invoice,
                chat_id=chat_id,
                plan_type="solo_pro_annual",
                family_id=family_id_str
            )
            return {"status": "ok"}
        elif arg in ["family_annual", "family_yearly", "annual_family", "yearly_family"]:
            background_tasks.add_task(
                self.telegram_service.send_subscription_invoice,
                chat_id=chat_id,
                plan_type="family_pro_annual",
                family_id=family_id_str
            )
            return {"status": "ok"}
        elif arg in ["lifetime", "lifetime_pro", "life"]:
            background_tasks.add_task(
                self.telegram_service.send_subscription_invoice,
                chat_id=chat_id,
                plan_type="lifetime_pro",
                family_id=family_id_str
            )
            return {"status": "ok"}
        else:
            background_tasks.add_task(self.telegram_service.send_message, chat_id=chat_id, text=UPGRADE_MENU_INTRO)
            background_tasks.add_task(
                self.telegram_service.send_subscription_invoice,
                chat_id=chat_id,
                plan_type="solo_pro",
                family_id=family_id_str
            )
            background_tasks.add_task(
                self.telegram_service.send_subscription_invoice,
                chat_id=chat_id,
                plan_type="family_pro",
                family_id=family_id_str
            )
            return {"status": "ok"}
