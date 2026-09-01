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

logger = logging.getLogger(__name__)

async def handle_notion_manage(
    raw_text: str,
    family_id: UUID,
    chat_id: int,
    message_id: Optional[int] = None
) -> str:
    raw_lower = raw_text.lower().strip()
    parts = raw_text.split()
    encryption_service = EncryptionService()

    with Session(engine) as session:
        family = session.get(Family, family_id)
        notion_service = NotionService(session)
        from src.services.subscription_service import has_unlimited_access
        if family and not has_unlimited_access(family):
            return (
                "⭐️ <b>Notion Mirroring is a Pro Feature</b>\n\n"
                "Real-time Notion database synchronization is available on <b>Solo Pro</b> and <b>Family Pro</b> plans.\n\n"
                "Type /upgrade to connect your Notion database."
            )
        elif raw_lower == "/notion" or raw_lower == "connect notion":
            return (
                "🔗 <b>Connect your Notion Workspace</b>\n\n"
                "Follow these quick steps:\n"
                "1. Go to https://www.notion.so/my-integrations and create an <b>Internal Integration</b>.\n"
                "2. Copy the <b>Internal Integration Secret</b> (token).\n"
                "3. Open your Notion expenses database, click <b>•••</b> (top right) -> <b>Add connections</b>, and select your integration.\n"
                "4. Reply here with:\n"
                "   <code>/notion connect &lt;your_secret_token&gt;</code>"
            )
        elif raw_lower.startswith("/notion connect") or raw_lower.startswith("notion connect"):
            if len(parts) < 3:
                return "Please provide the secret token. Usage: <code>/notion connect &lt;your_secret_token&gt;</code>"
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
                return "⚠️ <b>Invalid Token!</b> Please check your Integration Secret and try again.\n\n🔒 <i>Your secret token message was automatically deleted for security.</i>"
            elif db_id:
                try:
                    res = await notion_service.connect_database(family_id, token, db_id)
                    return f"✅ <b>Notion Workspace Connected!</b>\n\n📁 <b>Database:</b> {res['database_name']}\n🆔 <b>ID:</b> <code>{res['database_id']}</code>\n\nYour transactions are now linked and ready for automatic mirroring!\n\n🔒 <i>Your secret token message was automatically deleted for security.</i>"
                except Exception as e:
                    logger.error(f"Failed to connect database: {e}")
                    return "⚠️ <b>Failed to connect database.</b> Please verify the database ID and try again.\n\n🔒 <i>Your secret token message was automatically deleted for security.</i>"
            else:
                dbs = await notion_service.search_databases(token)
                if not dbs:
                    return (
                        "⚠️ <b>No databases found!</b>\n"
                        "Your Notion token is valid, but no databases have been shared with this integration yet.\n\n"
                        "Please open your Notion database, click <b>•••</b> -> <b>Add connections</b>, select your integration, and run <code>/notion connect &lt;token&gt;</code> again.\n\n"
                        "🔒 <i>Your secret token message was automatically deleted for security.</i>"
                    )
                family = session.get(Family, family_id)
                family.notion_api_key = encryption_service.encrypt(token)
                family.notion_database_id = None
                family.notion_database_name = None
                session.add(family)
                session.commit()
                
                db_list = "\n".join([f"{i+1}. 📊 <b>{db['title']}</b> (ID: <code>{db['id']}</code>)" for i, db in enumerate(dbs)])
                return (
                    f"📋 <b>Found {len(dbs)} Notion Database(s):</b>\n\n{db_list}\n\n"
                    "Reply with: <code>/notion setdb &lt;number or ID&gt;</code> (e.g. <code>/notion setdb 1</code>)\n\n"
                    "🔒 <i>Your secret token message was automatically deleted for security.</i>"
                )
        elif raw_lower.startswith("/notion setdb") or raw_lower.startswith("notion setdb"):
            if len(parts) < 3:
                return "Please provide the database number or ID. Usage: <code>/notion setdb &lt;number or ID&gt;</code>"
            target = parts[2]
            status = notion_service.get_family_notion_status(family_id)
            if not status["has_valid_token"]:
                return "No Notion token found. Please run <code>/notion connect &lt;token&gt;</code> first."
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
                return "Database not found."
            res = await notion_service.connect_database(family_id, token, selected_db["id"], selected_db["title"])
            return f"✅ <b>Notion Workspace Connected!</b>\n\n📁 <b>Database:</b> {res['database_name']}\n🆔 <b>ID:</b> <code>{res['database_id']}</code>\n\nYour transactions are now linked and ready for automatic mirroring!"
        elif raw_lower == "/notion status" or raw_lower == "notion status":
            status = notion_service.get_family_notion_status(family_id)
            if status["is_connected"]:
                dt_str = status['connected_at'].strftime('%Y-%m-%d %H:%M UTC') if status.get('connected_at') else "N/A"
                return f"📊 <b>Notion Connection Status:</b> Connected ✅\n📁 <b>Target Database:</b> {status['database_name']}\n🆔 <b>Database ID:</b> <code>{status['database_id']}</code>\n📅 <b>Connected:</b> {dt_str}"
            return "📊 <b>Notion Connection Status:</b> Not Connected ❌"
        elif raw_lower == "/notion disconnect" or raw_lower == "disconnect notion":
            notion_service.disconnect_workspace(family_id)
            return "🔌 <b>Notion Disconnected</b>\nYour Notion workspace connection has been removed. Transaction mirroring is now disabled."
        elif raw_lower == "/notion test" or raw_lower == "notion test":
            status = notion_service.get_family_notion_status(family_id)
            if not status["is_connected"]:
                return "⚠️ <b>Notion is not connected.</b>\nPlease run <code>/notion</code> to connect your workspace first."
            try:
                res = await notion_service.test_connection_mirror(family_id)
                if res:
                    return f"✅ <b>Notion Mirror Test Successful!</b>\nCreated test record in database: <b>{res['database_name']}</b>\n🔗 <a href=\"{res['page_url']}\">View in Notion</a>"
                return "⚠️ <b>Test Failed:</b> Could not verify connection."
            except Exception as e:
                return f"⚠️ <b>Test Failed:</b> {e}"
        elif raw_lower == "/notion sync" or raw_lower == "notion sync":
            status = notion_service.get_family_notion_status(family_id)
            if status["is_connected"]:
                res = await notion_service.sync_pending_transactions(family_id)
                synced = res.get("synced", 0)
                failed = res.get("failed", 0)
                db_name = status.get("database_name", "Notion")
                if synced > 0:
                    msg = f"✅ <b>Notion Sync Complete!</b>\nSuccessfully synchronized <b>{synced}</b> pending transaction(s) to <b>{db_name}</b>."
                    if failed > 0:
                        msg += f"\n\n⚠️ Could not sync {failed} transaction(s)."
                    return msg
                elif synced == 0 and failed == 0:
                    return f"✅ <b>Notion Sync is Up to Date!</b>\nAll transactions are already synchronized with your Notion database <b>{db_name}</b>."
                else:
                    return f"⚠️ <b>Notion Sync Failed:</b> Could not reach Notion API for {failed} transaction(s). The system will retry on your next sync or message."
            return "⚠️ <b>Notion is not connected.</b>\nPlease run <code>/notion</code> to connect your workspace first."
        else:
            return "Unknown Notion command."
