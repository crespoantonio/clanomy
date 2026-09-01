import asyncio
from uuid import UUID
from typing import Optional
from src.services.family_service import FamilyService, PlanLimitExceededError
from src.services.telegram_service import TelegramService

async def handle_create_family(user_uuid: UUID, family_name: Optional[str] = None) -> str:
    family_service = FamilyService()
    name = family_name or "My Family"
    await asyncio.to_thread(family_service.create_family, user_uuid, name)
    return f"✅ Family group '{name}' has been created! To invite others, just ask me to 'generate an invite link'."

async def handle_generate_invite(user_uuid: UUID, family_id: UUID) -> str:
    family_service = FamilyService()
    telegram_service = TelegramService()
    bot_username = await telegram_service.get_bot_username()
    try:
        invite, link = await asyncio.to_thread(family_service.create_invite, family_id, user_uuid, bot_username)
        return f"🔗 Here is your family invite link:\n\n{link}\n\n⏳ This invite link will expire in 48 hours."
    except PlanLimitExceededError:
        return (
            "⚠️ <b>Family Invites Require Family Pro</b>\n\n"
            "Your workspace is currently on the <b>Solo Pro</b> tier (1 user limit). "
            "To add family members and share a household ledger, please upgrade to <b>Family Pro</b> using /upgrade."
        )
    except ValueError as ve:
        return f"⚠️ {ve}"

async def handle_family_info(user_uuid: UUID) -> str:
    family_service = FamilyService()
    info = await asyncio.to_thread(family_service.get_family_info, user_uuid)
    members_str = []
    for m in info["members"]:
        name = m.get("full_name") or m.get("username") or "User"
        handle = f" (@{m['username']})" if m.get("username") else ""
        role = " 👑 (Admin)" if m.get("is_admin") else ""
        members_str.append(f"• {name}{handle}{role}")
    plan_type = info.get("plan_type", "free")
    plan_desc = plan_type.replace("_", " ").title()
    if plan_type == "free":
        tx_info = f"{info.get('monthly_tx_count', 0)} / 20 (⚡ Commands are 100% free & unlimited)"
    else:
        tx_info = f"{info.get('monthly_tx_count', 0)} (Unlimited)"
        
    return (
        f"👪 <b>Family Workspace: {info['name']}</b>\n"
        f"📋 <b>Plan:</b> {plan_desc}\n"
        f"📊 <b>Monthly AI Logs:</b> {tx_info}\n\n"
        f"<b>Members:</b>\n{members_formatted}\n\n"
        f"<b>Total Transactions:</b> {info['transactions_count']}\n"
        f"<b>Active Invites:</b> {info['active_invites_count']}"
    )

async def handle_leave_family(user_uuid: UUID) -> str:
    family_service = FamilyService()
    success, msg, _ = await asyncio.to_thread(family_service.leave_family, user_uuid)
    return msg

async def handle_remove_member(user_uuid: UUID, target_member: Optional[str]) -> str:
    family_service = FamilyService()
    target = target_member or ""
    success, msg, removed_user, _ = await asyncio.to_thread(family_service.remove_member, user_uuid, target)
    if success and removed_user and removed_user.telegram_id:
        telegram_service = TelegramService()
        try:
            from src.services.ai_orchestrator import create_logged_task
            create_logged_task(
                telegram_service.send_message(
                    chat_id=removed_user.telegram_id,
                    text="ℹ️ You have been removed from the family workspace by the admin. A new personal workspace has been created for you with all your personal transaction history intact."
                ),
                name="notify_removed_member"
            )
        except Exception:
            asyncio.create_task(
                telegram_service.send_message(
                    chat_id=removed_user.telegram_id,
                    text="ℹ️ You have been removed from the family workspace by the admin. A new personal workspace has been created for you with all your personal transaction history intact."
                )
            )
    return msg
