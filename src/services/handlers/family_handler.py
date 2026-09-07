import asyncio
import html
from uuid import UUID
from typing import Optional
from src.services.family_service import FamilyService, PlanLimitExceededError
from src.services.telegram_service import TelegramService
from src.templates.telegram_messages import (
    format_family_created_text,
    format_family_invite_text,
    format_family_info_text,
    format_member_removed_notice,
)

async def handle_create_family(user_uuid: UUID, family_name: Optional[str] = None, is_spanish: bool = False) -> str:
    family_service = FamilyService()
    name = family_name or ("Mi Familia" if is_spanish else "My Family")
    await asyncio.to_thread(family_service.create_family, user_uuid, name)
    return format_family_created_text(name, is_spanish=is_spanish)

async def handle_generate_invite(user_uuid: UUID, family_id: UUID, is_spanish: bool = False) -> str:
    family_service = FamilyService()
    telegram_service = TelegramService()
    bot_username = await telegram_service.get_bot_username()
    try:
        invite, link = await asyncio.to_thread(family_service.create_invite, family_id, user_uuid, bot_username)
        return format_family_invite_text(link, is_spanish=is_spanish)
    except PlanLimitExceededError as e:
        hdr = "Límite de Miembros Alcanzado" if is_spanish else "Member Limit Reached"
        return f"⚠️ <b>{hdr}</b>\n\n{e}"
    except ValueError as ve:
        return f"⚠️ {ve}"

async def handle_family_info(user_uuid: UUID, is_spanish: bool = False) -> str:
    family_service = FamilyService()
    info = await asyncio.to_thread(family_service.get_family_info, user_uuid)
    members_str = []
    default_name = "Usuario" if is_spanish else "User"
    for m in info["members"]:
        raw_name = m.get("full_name") or m.get("username") or default_name
        name = html.escape(raw_name, quote=False)
        handle = f" (@{html.escape(m['username'], quote=False)})" if m.get("username") else ""
        role = " 👑 (Admin)" if m.get("is_admin") else ""
        members_str.append(f"• {name}{handle}{role}")
    empty_label = "• No se encontraron integrantes" if is_spanish else "• No members found"
    members_formatted = "\n".join(members_str) if members_str else empty_label
    plan_type = info.get("plan_type", "free")
    plan_desc = plan_type.replace("_", " ").title()
    if plan_type == "free":
        cmd_hint = "(⚡ Los comandos son 100% gratuitos e ilimitados)" if is_spanish else "(⚡ Commands are 100% free &amp; unlimited)"
        tx_info = f"{info.get('monthly_tx_count', 0)} / 20 {cmd_hint}"
    else:
        unlimited_hint = "(Ilimitado)" if is_spanish else "(Unlimited)"
        tx_info = f"{info.get('monthly_tx_count', 0)} {unlimited_hint}"
        
    return format_family_info_text(
        name=str(info['name']),
        plan_desc=plan_desc,
        tx_info=tx_info,
        members_formatted=members_formatted,
        tx_count=info['transactions_count'],
        invite_count=info['active_invites_count'],
        is_spanish=is_spanish
    )

async def handle_leave_family(
    user_uuid: UUID,
    raw_text: str = "",
    family_service: Optional[FamilyService] = None,
    is_spanish: bool = False
) -> str:
    fam_service = family_service or FamilyService()
    
    # Check for explicit confirmation
    text_clean = (raw_text or "").strip().upper()
    is_confirmed = (
        text_clean in ("CONFIRM LEAVE", "CONFIRMAR SALIR", "/LEAVEFAMILY CONFIRM", "/LEAVEFAMILY CONFIRMAR")
        or text_clean.endswith(" CONFIRM")
        or text_clean.endswith(" CONFIRMAR")
    )
    
    if not is_confirmed:
        preview = await asyncio.to_thread(fam_service.get_leave_family_preview, user_uuid)
        if not preview.get("allowed", True):
            return preview.get("message", "Cannot leave family workspace.")
        if preview.get("requires_confirmation", False):
            return preview.get("prompt", "Please confirm if you wish to leave the family workspace.")

    success, msg, _ = await asyncio.to_thread(fam_service.leave_family, user_uuid)
    return msg

async def handle_remove_member(user_uuid: UUID, target_member: Optional[str], is_spanish: bool = False) -> str:
    family_service = FamilyService()
    target = target_member or ""
    success, msg, removed_user, _ = await asyncio.to_thread(family_service.remove_member, user_uuid, target)
    if success and removed_user and removed_user.telegram_id:
        telegram_service = TelegramService()
        notice_text = format_member_removed_notice(is_spanish=is_spanish)
        try:
            from src.services.ai_orchestrator import create_logged_task
            create_logged_task(
                telegram_service.send_message(
                    chat_id=removed_user.telegram_id,
                    text=notice_text
                ),
                name="notify_removed_member"
            )
        except Exception:
            asyncio.create_task(
                telegram_service.send_message(
                    chat_id=removed_user.telegram_id,
                    text=notice_text
                )
            )
    return msg
