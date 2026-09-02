"""
Lemon Squeezy Billing and Subscriptions Service.
Handles checkout session generation, webhook processing, subscription provisioning,
and self-serve customer billing portal links.
"""

import hmac
import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple
from fastapi import BackgroundTasks
from sqlmodel import Session, select

from src.core.config import settings
from src.core.http_client import get_http_client
from src.core.subscription_config import (
    SUBSCRIPTION_TIERS,
    get_tier_config,
    FREE_TIER_MONTHLY_LIMIT,
)
from src.db.models import Family, User
from src.services.telegram_service import TelegramService
from src.services.family_service import FamilyService
from src.templates.telegram_messages import (
    SELF_HOSTED_UPGRADE_MESSAGE,
    LIFETIME_PRO_CONFIRMATION,
    SOLO_PRO_CONFIRMATION,
    FAMILY_PRO_CONFIRMATION,
    SOLO_PRO_MEMBER_NOTICE,
    UPGRADE_MENU_INTRO,
    UPGRADE_MENU_ANNUAL_INTRO,
    BILLING_PORTAL_MESSAGE,
    SUBSCRIPTION_CANCELLED_MESSAGE,
    SUBSCRIPTION_PAYMENT_FAILED_MESSAGE,
)

logger = logging.getLogger(__name__)

LEMON_SQUEEZY_API_URL = "https://api.lemonsqueezy.com/v1"


class LemonSqueezyBillingService:
    def __init__(self, telegram_service: Optional[TelegramService] = None):
        self.telegram_service = telegram_service or TelegramService()

    def verify_webhook_signature(self, raw_body: bytes, signature_header: str) -> bool:
        """
        Validates incoming Lemon Squeezy webhook payloads using HMAC-SHA256 signature.
        """
        secret = settings.LEMON_SQUEEZY_WEBHOOK_SECRET
        if not secret or not signature_header:
            logger.error("Missing LEMON_SQUEEZY_WEBHOOK_SECRET or X-Signature header")
            return False

        try:
            expected_signature = hmac.new(
                secret.encode("utf-8"),
                raw_body,
                hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(expected_signature, signature_header)
        except Exception as e:
            logger.error(f"Error verifying Lemon Squeezy signature: {e}")
            return False

    def _resolve_tier(self, variant_id: Optional[Any], custom_data: Optional[dict]) -> Optional[Any]:
        """
        Authoritatively resolves the subscription tier.
        Prioritizes the actual variant_id returned by Lemon Squeezy over client custom_data.
        """
        if variant_id:
            from src.core.subscription_config import get_tier_by_variant_id
            tier = get_tier_by_variant_id(str(variant_id))
            if tier:
                return tier

        if custom_data:
            plan_code = custom_data.get("plan_type")
            if plan_code:
                tier = get_tier_config(str(plan_code).lower())
                if tier:
                    return tier

        return None

    async def create_checkout_url(
        self,
        family_id: str,
        chat_id: int,
        plan_code: str
    ) -> str:
        """
        Generates a hosted checkout session URL via Lemon Squeezy API,
        injecting family_id and chat_id in custom metadata.
        """
        # Validate UUID format
        try:
            uuid.UUID(str(family_id).strip())
        except (ValueError, TypeError, AttributeError):
            raise ValueError(f"Invalid family_id format for checkout: '{family_id}'")

        tier = get_tier_config(plan_code)
        if not tier:
            raise ValueError(f"Unknown subscription plan code: {plan_code}")

        variant_id = getattr(settings, tier.variant_id_setting_name, None)
        if not variant_id:
            logger.warning(
                f"Setting {tier.variant_id_setting_name} not configured. "
                "Returning mock/sandbox checkout fallback."
            )
            return f"https://lemonsqueezy.com/checkout?mock_plan={plan_code}"

        if not settings.LEMON_SQUEEZY_API_KEY or not settings.LEMON_SQUEEZY_STORE_ID:
            raise ValueError("Lemon Squeezy API credentials (API_KEY, STORE_ID) are not configured.")

        bot_username = await self.telegram_service.get_bot_username()
        redirect_url = f"https://t.me/{bot_username}" if bot_username and bot_username != "UnknownBot" else None

        client = get_http_client()
        headers = {
            "Authorization": f"Bearer {settings.LEMON_SQUEEZY_API_KEY}",
            "Accept": "application/vnd.api+json",
            "Content-Type": "application/vnd.api+json",
        }

        attributes: Dict[str, Any] = {
            "checkout_data": {
                "custom": {
                    "family_id": str(family_id).strip(),
                    "chat_id": str(chat_id),
                    "plan_type": tier.code,
                }
            }
        }
        if redirect_url:
            attributes["product_options"] = {"redirect_url": redirect_url}

        payload = {
            "data": {
                "type": "checkouts",
                "attributes": attributes,
                "relationships": {
                    "store": {
                        "data": {
                            "type": "stores",
                            "id": str(settings.LEMON_SQUEEZY_STORE_ID)
                        }
                    },
                    "variant": {
                        "data": {
                            "type": "variants",
                            "id": str(variant_id)
                        }
                    }
                }
            }
        }

        response = await client.post(
            f"{LEMON_SQUEEZY_API_URL}/checkouts",
            json=payload,
            headers=headers
        )
        response.raise_for_status()
        data = response.json()
        return data["data"]["attributes"]["url"]

    def handle_webhook_event(
        self,
        session: Session,
        event_name: str,
        payload: dict,
        background_tasks: BackgroundTasks
    ) -> dict:
        """
        Dispatches and processes verified Lemon Squeezy webhook events.
        """
        data_block = payload.get("data", {})
        attributes = data_block.get("attributes", {})

        # Security: Bind incoming webhooks to configured Lemon Squeezy store ID
        store_id = attributes.get("store_id")
        if settings.LEMON_SQUEEZY_STORE_ID and store_id:
            if str(store_id).strip() != str(settings.LEMON_SQUEEZY_STORE_ID).strip():
                logger.warning(
                    f"Security Alert: Webhook store_id '{store_id}' does not match configured store"
                )
                return {"status": "ignored", "reason": "Mismatched store_id"}

        meta = payload.get("meta", {})
        custom_data = meta.get("custom_data", {})
        family_id_str = custom_data.get("family_id")
        chat_id_val = custom_data.get("chat_id")
        chat_id = int(chat_id_val) if chat_id_val else None

        target_family: Optional[Family] = None
        if family_id_str:
            try:
                target_family = session.get(Family, uuid.UUID(family_id_str))
            except (ValueError, TypeError):
                target_family = None

        subscription_id = str(data_block.get("id")) if data_block.get("id") else None
        customer_id = str(attributes.get("customer_id")) if attributes.get("customer_id") else None
        customer_portal_url = attributes.get("urls", {}).get("customer_portal")

        # Fallback lookup by subscription_id or customer_id if family_id was not in custom_data
        if not target_family and subscription_id:
            target_family = session.exec(
                select(Family).where(Family.lemonsqueezy_subscription_id == subscription_id)
            ).first()

        if not target_family and customer_id:
            target_family = session.exec(
                select(Family).where(Family.lemonsqueezy_customer_id == customer_id)
            ).first()

        if not target_family:
            logger.warning(f"No matching Family found for Lemon Squeezy event '{event_name}' (payload id: {subscription_id})")
            return {"status": "ignored", "reason": "Family not found"}

        # Preserve permanent Lifetime Pro immunity
        if target_family.plan_type == "lifetime_pro":
            logger.info(f"Family {target_family.id} is lifetime_pro. Ignoring event '{event_name}'.")
            return {"status": "ignored_lifetime"}

        # Event Dispatching
        if event_name in ("subscription_created", "subscription_resumed"):
            return self._on_subscription_created(
                session=session,
                family=target_family,
                attributes=attributes,
                subscription_id=subscription_id,
                customer_id=customer_id,
                customer_portal_url=customer_portal_url,
                custom_data=custom_data,
                chat_id=chat_id,
                background_tasks=background_tasks
            )

        elif event_name in (
            "subscription_updated",
            "subscription_payment_success",
            "subscription_plan_changed",
            "subscription_payment_recovered",
            "subscription_unpaused",
        ):
            return self._on_subscription_updated(
                session=session,
                family=target_family,
                attributes=attributes,
                customer_portal_url=customer_portal_url
            )

        elif event_name == "subscription_cancelled":
            return self._on_subscription_cancelled(
                session=session,
                family=target_family,
                attributes=attributes,
                chat_id=chat_id,
                background_tasks=background_tasks
            )

        elif event_name == "subscription_expired":
            return self._on_subscription_expired(
                session=session,
                family=target_family,
                chat_id=chat_id,
                background_tasks=background_tasks
            )

        elif event_name == "subscription_payment_failed":
            return self._on_payment_failed(
                session=session,
                family=target_family,
                chat_id=chat_id,
                background_tasks=background_tasks
            )

        return {"status": "ok", "message": f"Event {event_name} acknowledged"}

    def _on_subscription_created(
        self,
        session: Session,
        family: Family,
        attributes: dict,
        subscription_id: Optional[str],
        customer_id: Optional[str],
        customer_portal_url: Optional[str],
        custom_data: dict,
        chat_id: Optional[int],
        background_tasks: BackgroundTasks
    ) -> dict:
        variant_id = attributes.get("variant_id")
        tier = self._resolve_tier(variant_id, custom_data)
        if not tier:
            logger.warning(
                f"Security Alert: Webhook subscription_created had unmapped tier "
                f"(variant_id={variant_id}, plan_type={custom_data.get('plan_type')}). Rejecting."
            )
            return {"status": "ignored", "reason": "Invalid or unmapped tier"}

        target_plan = tier.internal_plan
        max_members = tier.max_members

        sub_status = attributes.get("status", "active")
        is_active = sub_status in ("active", "on_trial")

        renews_at_raw = attributes.get("renews_at") or attributes.get("ends_at")
        renews_at = None
        if renews_at_raw:
            try:
                renews_at = datetime.fromisoformat(renews_at_raw.replace("Z", "+00:00"))
            except Exception:
                renews_at = None

        existing_members = session.exec(
            select(User).where(User.family_id == family.id)
        ).all()
        was_multi_member = len(existing_members) > 1

        # Idempotency check: avoid duplicate Telegram alerts on webhook retry
        is_already_active = (
            family.subscription_status == "active"
            and family.plan_type == target_plan
            and family.lemonsqueezy_subscription_id == subscription_id
        )

        family.subscription_status = "active" if is_active else sub_status
        family.plan_type = target_plan
        family.max_members = max_members
        if subscription_id:
            family.lemonsqueezy_subscription_id = subscription_id
        if customer_id:
            family.lemonsqueezy_customer_id = customer_id
        if customer_portal_url:
            family.customer_portal_url = customer_portal_url
        if renews_at:
            family.current_period_end = renews_at

        session.add(family)
        session.commit()
        session.refresh(family)

        # Notify via Telegram only if status is active and event is not a duplicate retry
        if chat_id and is_active and not is_already_active:
            if target_plan == "solo_pro":
                background_tasks.add_task(self.telegram_service.send_message, chat_id=chat_id, text=SOLO_PRO_CONFIRMATION)
                if was_multi_member:
                    fam_service = FamilyService()
                    for member in existing_members:
                        if member.telegram_id and not fam_service.is_family_admin(family.id, member.id):
                            background_tasks.add_task(
                                self.telegram_service.send_message,
                                chat_id=member.telegram_id,
                                text=SOLO_PRO_MEMBER_NOTICE
                            )
            elif target_plan == "family_pro":
                background_tasks.add_task(self.telegram_service.send_message, chat_id=chat_id, text=FAMILY_PRO_CONFIRMATION)

        return {"status": "upgraded", "plan": target_plan}

    def _on_subscription_updated(
        self,
        session: Session,
        family: Family,
        attributes: dict,
        customer_portal_url: Optional[str]
    ) -> dict:
        status = attributes.get("status")
        if status in ("active", "on_trial"):
            family.subscription_status = "active"
        elif status in ("past_due", "unpaid", "paused", "cancelled", "expired"):
            family.subscription_status = status

        # Update tier plan and capacity if customer upgraded/downgraded in portal
        variant_id = attributes.get("variant_id")
        tier = self._resolve_tier(variant_id, custom_data=None)
        if tier:
            family.plan_type = tier.internal_plan
            family.max_members = tier.max_members

        renews_at_raw = attributes.get("renews_at") or attributes.get("ends_at")
        if renews_at_raw:
            try:
                family.current_period_end = datetime.fromisoformat(renews_at_raw.replace("Z", "+00:00"))
            except Exception:
                pass

        if customer_portal_url:
            family.customer_portal_url = customer_portal_url

        session.add(family)
        session.commit()
        return {"status": "updated"}

    def _on_subscription_cancelled(
        self,
        session: Session,
        family: Family,
        attributes: dict,
        chat_id: Optional[int],
        background_tasks: BackgroundTasks
    ) -> dict:
        family.subscription_status = "cancelled"
        ends_at_raw = attributes.get("ends_at")
        if ends_at_raw:
            try:
                family.current_period_end = datetime.fromisoformat(ends_at_raw.replace("Z", "+00:00"))
            except Exception:
                pass

        session.add(family)
        session.commit()

        if chat_id:
            background_tasks.add_task(
                self.telegram_service.send_message,
                chat_id=chat_id,
                text=SUBSCRIPTION_CANCELLED_MESSAGE
            )
        return {"status": "cancelled"}

    def _on_subscription_expired(
        self,
        session: Session,
        family: Family,
        chat_id: Optional[int],
        background_tasks: BackgroundTasks
    ) -> dict:
        family.subscription_status = "expired"
        family.plan_type = "free"
        session.add(family)
        session.commit()

        if chat_id:
            from src.templates.telegram_messages import PLAN_EXPIRED_MESSAGE
            background_tasks.add_task(
                self.telegram_service.send_message,
                chat_id=chat_id,
                text=PLAN_EXPIRED_MESSAGE
            )
        return {"status": "expired"}

    def _on_payment_failed(
        self,
        session: Session,
        family: Family,
        chat_id: Optional[int],
        background_tasks: BackgroundTasks
    ) -> dict:
        if chat_id:
            reply_markup = None
            if family.customer_portal_url:
                reply_markup = {
                    "inline_keyboard": [
                        [{"text": "⚙️ Update Payment Method", "url": family.customer_portal_url}]
                    ]
                }
            background_tasks.add_task(
                self.telegram_service.send_message,
                chat_id=chat_id,
                text=SUBSCRIPTION_PAYMENT_FAILED_MESSAGE,
                reply_markup=reply_markup
            )
        return {"status": "payment_failed_alerted"}

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
        - In Self-Hosted mode: returns friendly 100% unlocked message.
        - In Commercial SaaS mode: generates Lemon Squeezy checkout link buttons.
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
        family_id_str = str(family.id) if family else (str(user.family_id) if user and user.family_id else "")

        if arg in ("annual", "yearly", "annually"):
            solo_annual_url = await self.create_checkout_url(family_id_str, chat_id, "solo_pro_annual")
            fam_annual_url = await self.create_checkout_url(family_id_str, chat_id, "family_pro_annual")
            reply_markup = {
                "inline_keyboard": [
                    [{"text": "💳 Solo Pro Annual ($49.99/yr)", "url": solo_annual_url}],
                    [{"text": "💳 Family Pro Annual ($99.99/yr)", "url": fam_annual_url}]
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
            solo_url = await self.create_checkout_url(family_id_str, chat_id, "solo_pro")
            reply_markup = {
                "inline_keyboard": [
                    [{"text": "💳 Upgrade to Solo Pro ($4.99/mo)", "url": solo_url}]
                ]
            }
            background_tasks.add_task(
                self.telegram_service.send_message,
                chat_id=chat_id,
                text="⭐️ <b>Upgrade to Clanomy Solo Pro</b>\n\nTap below to complete your upgrade with Card, Apple Pay, or Google Pay:",
                reply_markup=reply_markup
            )
            return {"status": "ok"}

        elif arg in ("family", "family_pro", "fam"):
            fam_url = await self.create_checkout_url(family_id_str, chat_id, "family_pro")
            reply_markup = {
                "inline_keyboard": [
                    [{"text": "💳 Upgrade to Family Pro ($9.99/mo)", "url": fam_url}]
                ]
            }
            background_tasks.add_task(
                self.telegram_service.send_message,
                chat_id=chat_id,
                text="👨‍👩‍👧‍👦 <b>Upgrade to Clanomy Family Pro</b>\n\nTap below to complete your upgrade for up to 5 family members:",
                reply_markup=reply_markup
            )
            return {"status": "ok"}

        else:
            solo_url = await self.create_checkout_url(family_id_str, chat_id, "solo_pro")
            fam_url = await self.create_checkout_url(family_id_str, chat_id, "family_pro")
            reply_markup = {
                "inline_keyboard": [
                    [{"text": "💳 Solo Pro ($4.99 / mo)", "url": solo_url}],
                    [{"text": "💳 Family Pro ($9.99 / mo)", "url": fam_url}]
                ]
            }
            background_tasks.add_task(
                self.telegram_service.send_message,
                chat_id=chat_id,
                text=UPGRADE_MENU_INTRO,
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
                    "Your workspace does not have an active Lemon Squeezy subscription link.\n"
                    "Type /upgrade to view available subscription plans."
                )
            )
        return {"status": "ok"}
