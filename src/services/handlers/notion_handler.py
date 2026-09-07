import logging
import asyncio
from uuid import UUID
from typing import Optional
from sqlmodel import Session
from src.db.session import engine
from src.db.models import Family
from src.core.encryption import EncryptionService
from src.services.notion_service import NotionService
from src.services.telegram_service import TelegramService

from src.templates.telegram_messages import (
    format_notion_pro_required,
    format_notion_connect_instructions,
    format_notion_invalid_token,
    format_notion_connected_success,
    format_notion_no_databases,
    format_notion_status_message,
    format_notion_disconnected,
    is_spanish_text,
)

logger = logging.getLogger(__name__)

async def handle_notion_manage(
    raw_text: str,
    family_id: UUID,
    chat_id: int,
    message_id: Optional[int] = None,
    is_spanish: bool = False
) -> str:
    raw_lower = raw_text.lower().strip()
    parts = raw_text.split()
    encryption_service = EncryptionService()
    is_es = is_spanish or is_spanish_text(raw_text)

    with Session(engine) as session:
        family = session.get(Family, family_id)
        notion_service = NotionService(session)
        from src.services.subscription_service import has_unlimited_access
        if family and not has_unlimited_access(family):
            return format_notion_pro_required(is_spanish=is_es)
        elif raw_lower == "/notion" or raw_lower == "connect notion":
            return format_notion_connect_instructions(is_spanish=is_es)
        elif raw_lower.startswith("/notion connect") or raw_lower.startswith("notion connect"):
            if len(parts) < 3:
                return (
                    "Por favor proporciona el token secreto. Uso: <code>/notion connect &lt;tu_token_secreto&gt;</code>"
                    if is_es else
                    "Please provide the secret token. Usage: <code>/notion connect &lt;your_secret_token&gt;</code>"
                )
            token = parts[2]
            db_id = parts[3] if len(parts) > 3 else None
            if message_id:
                ts = TelegramService()
                try:
                    from src.services.ai_orchestrator import create_logged_task
                    create_logged_task(ts.delete_message(chat_id, message_id), name="delete_secret_token_message")
                except Exception:
                    asyncio.create_task(ts.delete_message(chat_id, message_id))

            is_valid = await notion_service.validate_token(token)
            if not is_valid:
                return format_notion_invalid_token(is_spanish=is_es)
            elif db_id:
                try:
                    res = await notion_service.connect_database(family_id, token, db_id)
                    return format_notion_connected_success(res['database_name'], res['database_id'], is_spanish=is_es)
                except Exception as e:
                    logger.error(f"Failed to connect database: {e}")
                    return (
                        "⚠️ <b>Error al conectar la base de datos.</b> Por favor verifica el ID de la base de datos e intenta de nuevo.\n\n🔒 <i>Tu mensaje con el token fue eliminado automáticamente por seguridad.</i>"
                        if is_es else
                        "⚠️ <b>Failed to connect database.</b> Please verify the database ID and try again.\n\n🔒 <i>Your secret token message was automatically deleted for security.</i>"
                    )
            else:
                dbs = await notion_service.search_databases(token)
                if not dbs:
                    return format_notion_no_databases(is_spanish=is_es)
                family = session.get(Family, family_id)
                family.notion_api_key = encryption_service.encrypt(token)
                family.notion_database_id = None
                family.notion_database_name = None
                session.add(family)
                session.commit()
                
                db_list = "\n".join([f"{i+1}. 📊 <b>{db['title']}</b> (ID: <code>{db['id']}</code>)" for i, db in enumerate(dbs)])
                header = (
                    f"📋 <b>Encontré {len(dbs)} Base(s) de Datos de Notion:</b>\n\n"
                    if is_es else
                    f"📋 <b>Found {len(dbs)} Notion Database(s):</b>\n\n"
                )
                reply_prompt = (
                    "Responde con: <code>/notion setdb &lt;número o ID&gt;</code> (ej. <code>/notion setdb 1</code>)\n\n"
                    if is_es else
                    "Reply with: <code>/notion setdb &lt;number or ID&gt;</code> (e.g. <code>/notion setdb 1</code>)\n\n"
                )
                footer = (
                    "🔒 <i>Tu mensaje con el token fue eliminado automáticamente por seguridad.</i>"
                    if is_es else
                    "🔒 <i>Your secret token message was automatically deleted for security.</i>"
                )
                return f"{header}{db_list}\n\n{reply_prompt}{footer}"
        elif raw_lower.startswith("/notion setdb") or raw_lower.startswith("notion setdb"):
            if len(parts) < 3:
                return (
                    "Por favor proporciona el número o ID de la base de datos. Uso: <code>/notion setdb &lt;número o ID&gt;</code>"
                    if is_es else
                    "Please provide the database number or ID. Usage: <code>/notion setdb &lt;number or ID&gt;</code>"
                )
            target = parts[2]
            status = notion_service.get_family_notion_status(family_id)
            if not status["has_valid_token"]:
                return (
                    "No se encontró token de Notion. Por favor ejecuta <code>/notion connect &lt;token&gt;</code> primero."
                    if is_es else
                    "No Notion token found. Please run <code>/notion connect &lt;token&gt;</code> first."
                )
            family = session.get(Family, family_id)
            token = encryption_service.decrypt(family.notion_api_key)
            dbs = await notion_service.search_databases(token)
            selected_db = None
            if target.isdigit():
                idx = int(target) - 1
                if 0 <= idx < len(dbs):
                    selected_db = dbs[idx]
            else:
                selected_db = next((db for db in dbs if db["id"] == target), None)
            
            if not selected_db:
                return "Base de datos no encontrada." if is_es else "Database not found."
            res = await notion_service.connect_database(family_id, token, selected_db["id"], selected_db["title"])
            return format_notion_connected_success(res['database_name'], res['database_id'], is_spanish=is_es)
        elif raw_lower == "/notion status" or raw_lower == "notion status":
            status = notion_service.get_family_notion_status(family_id)
            dt_str = status['connected_at'].strftime('%Y-%m-%d %H:%M UTC') if status.get('connected_at') else None
            return format_notion_status_message(
                is_connected=status["is_connected"],
                db_name=status.get("database_name"),
                db_id=status.get("database_id"),
                connected_at_str=dt_str,
                is_spanish=is_es
            )
        elif raw_lower == "/notion disconnect" or raw_lower == "disconnect notion":
            notion_service.disconnect_workspace(family_id)
            return format_notion_disconnected(is_spanish=is_es)
        elif raw_lower == "/notion test" or raw_lower == "notion test":
            status = notion_service.get_family_notion_status(family_id)
            if not status["is_connected"]:
                return (
                    "⚠️ <b>Notion no está conectado.</b>\nPor favor ejecuta <code>/notion</code> para conectar tu espacio primero."
                    if is_es else
                    "⚠️ <b>Notion is not connected.</b>\nPlease run <code>/notion</code> to connect your workspace first."
                )
            try:
                res = await notion_service.test_connection_mirror(family_id)
                if res:
                    return (
                        f"✅ <b>¡Prueba de Espejo de Notion Exitosa!</b>\nSe creó un registro de prueba en la base de datos: <b>{res['database_name']}</b>\n🔗 <a href=\"{res['page_url']}\">Ver en Notion</a>"
                        if is_es else
                        f"✅ <b>Notion Mirror Test Successful!</b>\nCreated test record in database: <b>{res['database_name']}</b>\n🔗 <a href=\"{res['page_url']}\">View in Notion</a>"
                    )
                return (
                    "⚠️ <b>Prueba fallida:</b> No se pudo verificar la conexión."
                    if is_es else
                    "⚠️ <b>Test Failed:</b> Could not verify connection."
                )
            except Exception as e:
                return f"⚠️ <b>Prueba fallida:</b> {e}" if is_es else f"⚠️ <b>Test Failed:</b> {e}"
        elif raw_lower == "/notion sync" or raw_lower == "notion sync":
            status = notion_service.get_family_notion_status(family_id)
            if status["is_connected"]:
                res = await notion_service.sync_pending_transactions(family_id)
                synced = res.get("synced", 0)
                failed = res.get("failed", 0)
                db_name = status.get("database_name", "Notion")
                if synced > 0:
                    msg = (
                        f"✅ <b>¡Sincronización con Notion Completa!</b>\nSe sincronizaron con éxito <b>{synced}</b> transacción(es) pendiente(s) a <b>{db_name}</b>."
                        if is_es else
                        f"✅ <b>Notion Sync Complete!</b>\nSuccessfully synchronized <b>{synced}</b> pending transaction(s) to <b>{db_name}</b>."
                    )
                    if failed > 0:
                        msg += (
                            f"\n\n⚠️ No se pudieron sincronizar {failed} transacción(es)."
                            if is_es else
                            f"\n\n⚠️ Could not sync {failed} transaction(s)."
                        )
                    return msg
                elif synced == 0 and failed == 0:
                    return (
                        f"✅ <b>¡La Sincronización con Notion está al Día!</b>\nTodas las transacciones ya están sincronizadas con tu base de datos <b>{db_name}</b>."
                        if is_es else
                        f"✅ <b>Notion Sync is Up to Date!</b>\nAll transactions are already synchronized with your Notion database <b>{db_name}</b>."
                    )
                else:
                    return (
                        f"⚠️ <b>Falló la Sincronización con Notion:</b> No se pudo conectar a la API de Notion para {failed} transacción(es). El sistema reintentará en el próximo mensaje o sincronización."
                        if is_es else
                        f"⚠️ <b>Notion Sync Failed:</b> Could not reach Notion API for {failed} transaction(s). The system will retry on your next sync or message."
                    )
        else:
            return "Comando de Notion desconocido." if is_es else "Unknown Notion command."


async def safe_mirror_to_notion(
    family_id: UUID,
    amount: float,
    currency: str,
    concept: str,
    category: str,
    timestamp,
    user_name: Optional[str],
    transaction_id: Optional[UUID] = None,
    tx_type: str = "expense"
):
    """Background task for Notion Mirroring. Fails silently with logs."""
    try:
        with Session(engine) as session:
            family = session.get(Family, family_id)
            from src.services.subscription_service import has_unlimited_access
            if family and not has_unlimited_access(family):
                return
            notion_service = NotionService(session)
            await notion_service.mirror_transaction(
                family_id=family_id,
                amount=amount,
                currency=currency,
                concept=concept,
                category=category,
                timestamp=timestamp,
                user_name=user_name,
                transaction_id=transaction_id,
                tx_type=tx_type
            )
    except Exception as e:
        logger.error(f"[Notion Mirror] Uncaught error in mirror background task: {e}")


async def safe_update_notion_page(
    family_id: UUID,
    page_id: str,
    amount: float,
    currency: str,
    concept: str,
    category: str,
    timestamp,
    user_name: Optional[str],
    tx_type: str = "expense"
):
    """Background task for Notion Page Updates. Fails silently with logs."""
    try:
        with Session(engine) as session:
            family = session.get(Family, family_id)
            from src.services.subscription_service import has_unlimited_access
            if family and not has_unlimited_access(family):
                return
            notion_service = NotionService(session)
            await notion_service.update_transaction_page(
                family_id=family_id,
                page_id=page_id,
                amount=amount,
                currency=currency,
                concept=concept,
                category=category,
                timestamp=timestamp,
                user_name=user_name,
                tx_type=tx_type
            )
    except Exception as e:
        logger.error(f"[Notion Mirror] Uncaught error in update background task: {e}")


async def safe_archive_notion_page(family_id: UUID, page_id: str):
    """Background task for Notion Page Archival. Fails silently with logs."""
    try:
        with Session(engine) as session:
            notion_service = NotionService(session)
            await notion_service.archive_transaction_page(family_id=family_id, page_id=page_id)
    except Exception as e:
        logger.error(f"[Notion Mirror] Uncaught error in archive background task: {e}")

