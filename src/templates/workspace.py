"""
Multi-user workspace management, invites, member administration, and Notion integration templates.
"""
import html
from typing import Optional, Any, List, Dict
from datetime import datetime
from src.templates.common import is_spanish_text

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

def format_family_created_text(name: str, is_spanish: bool = False) -> str:
    """Confirmation text upon creating a new family workspace."""
    safe_name = html.escape(name, quote=False)
    if is_spanish:
        return f"✅ ¡El grupo familiar '{safe_name}' ha sido creado! Para invitar a otros, simplemente pídeme 'generar un link de invitación'."
    return f"✅ Family group '{safe_name}' has been created! To invite others, just ask me to 'generate an invite link'."

def format_family_invite_text(link: str, is_spanish: bool = False) -> str:
    """Invite link message for inviting partners/roommates to workspace."""
    if is_spanish:
        return f"🔗 Aquí tienes el link de invitación para tu familia:\n\n{link}\n\n⏳ Este enlace expirará en 1 hora."
    return f"🔗 Here is your family invite link:\n\n{link}\n\n⏳ This invite link will expire in 1 hour."

def format_family_info_text(
    name: str,
    plan_desc: str,
    tx_info: str,
    members_formatted: str,
    tx_count: int,
    invite_count: int,
    is_spanish: bool = False
) -> str:
    """Information summary card for the /family command."""
    safe_name = html.escape(name, quote=False)
    if is_spanish:
        return (
            f"👪 <b>Espacio Familiar: {safe_name}</b>\n"
            f"📋 <b>Plan:</b> {plan_desc}\n"
            f"📊 <b>Registros de IA:</b> {tx_info}\n\n"
            f"<b>Integrantes:</b>\n{members_formatted}\n\n"
            f"<b>Total de Transacciones:</b> {tx_count}\n"
            f"<b>Invitaciones Activas:</b> {invite_count}"
        )
    return (
        f"👪 <b>Family Workspace: {safe_name}</b>\n"
        f"📋 <b>Plan:</b> {plan_desc}\n"
        f"📊 <b>AI Logs:</b> {tx_info}\n\n"
        f"<b>Members:</b>\n{members_formatted}\n\n"
        f"<b>Total Transactions:</b> {tx_count}\n"
        f"<b>Active Invites:</b> {invite_count}"
    )

def format_member_removed_notice(is_spanish: bool = False) -> str:
    """Notification sent to a user removed from a household workspace."""
    if is_spanish:
        return (
            "ℹ️ Has sido removido del espacio familiar por el administrador. "
            "Se ha creado un nuevo espacio personal para ti con todo tu historial de transacciones intacto."
        )
    return (
        "ℹ️ You have been removed from the family workspace by the admin. "
        "A new personal workspace has been created for you with all your personal transaction history intact."
    )

def format_notion_pro_required(is_spanish: bool = False) -> str:
    """Paywall notice for Notion mirroring."""
    if is_spanish:
        return (
            "⭐️ <b>La Sincronización con Notion es una Función Pro</b>\n\n"
            "La sincronización de base de datos en tiempo real con Notion está disponible en los planes <b>Solo Pro</b> y <b>Family Pro</b>.\n\n"
            "Escribe /upgrade para conectar tu base de datos de Notion."
        )
    return (
        "⭐️ <b>Notion Mirroring is a Pro Feature</b>\n\n"
        "Real-time Notion database synchronization is available on <b>Solo Pro</b> and <b>Family Pro</b> plans.\n\n"
        "Type /upgrade to connect your Notion database."
    )

def format_notion_connect_instructions(is_spanish: bool = False) -> str:
    """Instructions on obtaining and providing an internal integration token."""
    if is_spanish:
        return (
            "🔗 <b>Conecta tu Espacio de Notion</b>\n\n"
            "Sigue estos rápidos pasos:\n"
            "1. Ve a https://www.notion.so/my-integrations y crea una <b>Integración Interna</b>.\n"
            "2. Copia el <b>Token Secreto de Integración</b>.\n"
            "3. Abre tu base de datos de gastos en Notion, haz clic en <b>•••</b> (arriba a la derecha) -> <b>Conexiones</b>, y selecciona tu integración.\n"
            "4. Responde aquí con:\n"
            "   <code>/notion connect &lt;tu_token_secreto&gt;</code>"
        )
    return (
        "🔗 <b>Connect your Notion Workspace</b>\n\n"
        "Follow these quick steps:\n"
        "1. Go to https://www.notion.so/my-integrations and create an <b>Internal Integration</b>.\n"
        "2. Copy the <b>Internal Integration Secret</b> (token).\n"
        "3. Open your Notion expenses database, click <b>•••</b> (top right) -> <b>Add connections</b>, and select your integration.\n"
        "4. Reply here with:\n"
        "   <code>/notion connect &lt;your_secret_token&gt;</code>"
    )

def format_notion_invalid_token(is_spanish: bool = False) -> str:
    """Error message when a provided Notion token is invalid."""
    if is_spanish:
        return "⚠️ <b>¡Token Inválido!</b> Por favor verifica tu Token Secreto de Integración e intenta de nuevo.\n\n🔒 <i>Tu mensaje con el token fue eliminado automáticamente por seguridad.</i>"
    return "⚠️ <b>Invalid Token!</b> Please check your Integration Secret and try again.\n\n🔒 <i>Your secret token message was automatically deleted for security.</i>"

def format_notion_connected_success(database_name: Any, database_id: str, is_spanish: bool = False) -> str:
    """Success message when Notion integration connects."""
    if isinstance(database_name, list) and database_name and isinstance(database_name[0], dict) and "plain_text" in database_name[0]:
        db_title = database_name[0]["plain_text"]
    else:
        db_title = str(database_name)
    safe_db = html.escape(db_title)
    if is_spanish:
        return (
            f"✅ <b>¡Espacio de Notion Conectado!</b>\n\n"
            f"📁 <b>Base de Datos:</b> {safe_db}\n"
            f"🆔 <b>ID:</b> <code>{database_id}</code>\n\n"
            "¡Tus transacciones ahora están vinculadas y listas para sincronización automática!\n\n"
            "🔒 <i>Tu mensaje con el token fue eliminado automáticamente por seguridad.</i>"
        )
    return (
        f"✅ <b>Notion Workspace Connected!</b>\n\n"
        f"📁 <b>Database:</b> {safe_db}\n"
        f"🆔 <b>ID:</b> <code>{database_id}</code>\n\n"
        "Your transactions are now linked and ready for automatic mirroring!\n\n"
        "🔒 <i>Your secret token message was automatically deleted for security.</i>"
    )

def format_notion_no_databases(is_spanish: bool = False) -> str:
    """Message when token is valid but no databases are shared."""
    if is_spanish:
        return (
            "⚠️ <b>¡No se encontraron bases de datos!</b>\n"
            "Tu token de Notion es válido, pero aún no has compartido ninguna base de datos con esta integración.\n\n"
            "Por favor abre tu base de datos en Notion, haz clic en <b>•••</b> -> <b>Conexiones</b>, selecciona tu integración y envía <code>/notion connect &lt;token&gt;</code> de nuevo.\n\n"
            "🔒 <i>Tu mensaje con el token fue eliminado automáticamente por seguridad.</i>"
        )
    return (
        "⚠️ <b>No databases found!</b>\n"
        "Your Notion token is valid, but no databases have been shared with this integration yet.\n\n"
        "Please open your Notion database, click <b>•••</b> -> <b>Add connections</b>, select your integration, and run <code>/notion connect &lt;token&gt;</code> again.\n\n"
        "🔒 <i>Your secret token message was automatically deleted for security.</i>"
    )

def format_notion_status_message(
    is_connected: bool,
    db_name: Optional[str] = None,
    db_id: Optional[str] = None,
    connected_at_str: Optional[str] = None,
    is_spanish: bool = False
) -> str:
    """Status report for Notion workspace connection."""
    if is_spanish:
        if is_connected:
            return (
                f"📊 <b>Estado de Conexión con Notion:</b> Conectado ✅\n"
                f"📁 <b>Base de Datos:</b> {html.escape(db_name or 'N/A')}\n"
                f"🆔 <b>ID de Base de Datos:</b> <code>{db_id or 'N/A'}</code>\n"
                f"📅 <b>Conectado:</b> {connected_at_str or 'N/A'}"
            )
        return "📊 <b>Estado de Conexión con Notion:</b> No Conectado ❌"
    if is_connected:
        return (
            f"📊 <b>Notion Connection Status:</b> Connected ✅\n"
            f"📁 <b>Target Database:</b> {html.escape(db_name or 'N/A')}\n"
            f"🆔 <b>Database ID:</b> <code>{db_id or 'N/A'}</code>\n"
            f"📅 <b>Connected:</b> {connected_at_str or 'N/A'}"
        )
    return "📊 <b>Notion Connection Status:</b> Not Connected ❌"

def format_notion_disconnected(is_spanish: bool = False) -> str:
    """Notice upon disconnecting Notion."""
    if is_spanish:
        return "🔌 <b>Notion Desconectado</b>\nLa conexión con tu espacio de Notion ha sido eliminada. La sincronización de transacciones está desactivada."
    return "🔌 <b>Notion Disconnected</b>\nYour Notion workspace connection has been removed. Transaction mirroring is now disabled."
