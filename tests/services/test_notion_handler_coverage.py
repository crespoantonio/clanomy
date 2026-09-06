import pytest
from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.handlers.notion_handler import (
    handle_notion_manage,
    safe_mirror_to_notion,
    safe_update_notion_page,
    safe_archive_notion_page,
)
from src.db.models import Family

@pytest.mark.anyio
async def test_safe_mirror_to_notion():
    fid = uuid4()
    with patch("src.services.handlers.notion_handler.Session") as mock_session_class, \
         patch("src.services.subscription_service.has_unlimited_access", return_value=True), \
         patch("src.services.handlers.notion_handler.NotionService") as mock_ns_class:
        mock_session = MagicMock()
        mock_session_class.return_value.__enter__.return_value = mock_session
        mock_ns = mock_ns_class.return_value
        mock_ns.mirror_transaction = AsyncMock()

        await safe_mirror_to_notion(
            family_id=fid,
            amount=50.0,
            currency="USD",
            concept="Dinner",
            category="Food",
            timestamp=datetime.now(timezone.utc),
            user_name="Tony"
        )
        assert mock_ns.mirror_transaction.call_count == 1

        # Exception branch
        mock_ns.mirror_transaction.side_effect = Exception("Notion API down")
        await safe_mirror_to_notion(
            family_id=fid,
            amount=50.0,
            currency="USD",
            concept="Dinner",
            category="Food",
            timestamp=datetime.now(timezone.utc),
            user_name="Tony"
        )

@pytest.mark.anyio
async def test_safe_update_notion_page():
    fid = uuid4()
    with patch("src.services.handlers.notion_handler.Session") as mock_session_class, \
         patch("src.services.subscription_service.has_unlimited_access", return_value=True), \
         patch("src.services.handlers.notion_handler.NotionService") as mock_ns_class:
        mock_session = MagicMock()
        mock_session_class.return_value.__enter__.return_value = mock_session
        mock_ns = mock_ns_class.return_value
        mock_ns.update_transaction_page = AsyncMock()

        await safe_update_notion_page(
            family_id=fid,
            page_id="page_abc",
            amount=60.0,
            currency="USD",
            concept="Lunch",
            category="Food",
            timestamp=datetime.now(timezone.utc),
            user_name="Tony"
        )
        assert mock_ns.update_transaction_page.call_count == 1

        # Exception branch
        mock_ns.update_transaction_page.side_effect = Exception("API fail")
        await safe_update_notion_page(
            family_id=fid,
            page_id="page_abc",
            amount=60.0,
            currency="USD",
            concept="Lunch",
            category="Food",
            timestamp=datetime.now(timezone.utc),
            user_name="Tony"
        )

@pytest.mark.anyio
async def test_safe_archive_notion_page():
    fid = uuid4()
    with patch("src.services.handlers.notion_handler.Session") as mock_session_class, \
         patch("src.services.handlers.notion_handler.NotionService") as mock_ns_class:
        mock_session = MagicMock()
        mock_session_class.return_value.__enter__.return_value = mock_session
        mock_ns = mock_ns_class.return_value
        mock_ns.archive_transaction_page = AsyncMock()

        await safe_archive_notion_page(family_id=fid, page_id="page_123")
        assert mock_ns.archive_transaction_page.call_count == 1

        # Exception branch
        mock_ns.archive_transaction_page.side_effect = Exception("API fail")
        await safe_archive_notion_page(family_id=fid, page_id="page_123")

@pytest.mark.anyio
async def test_handle_notion_manage_commands():
    fid = uuid4()
    chat_id = 12345

    with patch("src.services.handlers.notion_handler.Session") as mock_session_class, \
         patch("src.services.subscription_service.has_unlimited_access", return_value=True), \
         patch("src.services.handlers.notion_handler.NotionService") as mock_ns_class:
        mock_session = MagicMock()
        mock_session_class.return_value.__enter__.return_value = mock_session
        mock_ns = mock_ns_class.return_value

        # 1. /notion info
        msg1 = await handle_notion_manage("/notion", fid, chat_id)
        assert "Connect your Notion Workspace" in msg1

        # 2. /notion connect without args
        msg2 = await handle_notion_manage("/notion connect", fid, chat_id)
        assert "Please provide the secret token" in msg2

        # 3. /notion setdb without args
        msg3 = await handle_notion_manage("/notion setdb", fid, chat_id)
        assert "Please provide the database number or ID" in msg3

        # 4. /notion status (not connected)
        mock_ns.get_family_notion_status.return_value = {"is_connected": False}
        msg4 = await handle_notion_manage("/notion status", fid, chat_id)
        assert "Not Connected" in msg4

        # 5. /notion status (connected)
        mock_ns.get_family_notion_status.return_value = {
            "is_connected": True,
            "database_name": "Family Budget",
            "database_id": "db_123",
            "connected_at": datetime.now(timezone.utc)
        }
        msg5 = await handle_notion_manage("/notion status", fid, chat_id)
        assert "Connected ✅" in msg5

        # 6. /notion disconnect
        msg6 = await handle_notion_manage("/notion disconnect", fid, chat_id)
        assert "Notion Disconnected" in msg6

        # 7. /notion test (not connected)
        mock_ns.get_family_notion_status.return_value = {"is_connected": False}
        msg7 = await handle_notion_manage("/notion test", fid, chat_id)
        assert "Notion is not connected" in msg7

        # 8. /notion test (connected success)
        mock_ns.get_family_notion_status.return_value = {"is_connected": True}
        mock_ns.test_connection_mirror = AsyncMock(return_value={
            "database_name": "Budget",
            "page_url": "https://notion.so/test"
        })
        msg8 = await handle_notion_manage("/notion test", fid, chat_id)
        assert "Test Successful" in msg8

        # 9. /notion test (failed)
        mock_ns.test_connection_mirror = AsyncMock(side_effect=Exception("Timeout"))
        msg9 = await handle_notion_manage("/notion test", fid, chat_id)
        assert "Test Failed" in msg9

        # 10. Unknown command
        msg10 = await handle_notion_manage("/notion random_cmd", fid, chat_id)
        assert msg10 == "Unknown Notion command."

@pytest.mark.anyio
async def test_handle_notion_connect_and_setdb_and_sync():
    fid = uuid4()
    chat_id = 12345

    family = Family(id=fid, name="Test Fam")

    with patch("src.services.handlers.notion_handler.Session") as mock_session_class, \
         patch("src.services.subscription_service.has_unlimited_access", return_value=True), \
         patch("src.services.handlers.notion_handler.NotionService") as mock_ns_class, \
         patch("src.services.handlers.notion_handler.TelegramService") as mock_ts_class:
        mock_session = MagicMock()
        mock_session.get.return_value = family
        mock_session_class.return_value.__enter__.return_value = mock_session
        mock_ns = mock_ns_class.return_value
        mock_ts = mock_ts_class.return_value
        mock_ts.delete_message = AsyncMock()

        # 1. /notion connect with invalid token
        mock_ns.validate_token = AsyncMock(return_value=False)
        msg1 = await handle_notion_manage("/notion connect secret_bad", fid, chat_id, message_id=99)
        assert "Invalid Token" in msg1

        # 2. /notion connect with valid token and db_id directly
        mock_ns.validate_token = AsyncMock(return_value=True)
        mock_ns.connect_database = AsyncMock(return_value={"database_name": "DB1", "database_id": "db_123"})
        msg2 = await handle_notion_manage("/notion connect secret_ok db_123", fid, chat_id)
        assert "Notion Workspace Connected" in msg2

        # 3. /notion connect with valid token and db_id that fails
        mock_ns.connect_database = AsyncMock(side_effect=Exception("Not found"))
        msg3 = await handle_notion_manage("/notion connect secret_ok db_bad", fid, chat_id)
        assert "Failed to connect database" in msg3

        # 4. /notion connect with valid token but no databases found
        mock_ns.search_databases = AsyncMock(return_value=[])
        msg4 = await handle_notion_manage("/notion connect secret_ok", fid, chat_id)
        assert "No databases found" in msg4

        # 5. /notion connect with valid token listing databases
        mock_ns.search_databases = AsyncMock(return_value=[{"id": "db_1", "title": "Expenses"}])
        msg5 = await handle_notion_manage("/notion connect secret_ok", fid, chat_id)
        assert "Found 1 Notion Database" in msg5

        # 6. /notion setdb without valid token
        mock_ns.get_family_notion_status.return_value = {"has_valid_token": False}
        msg6 = await handle_notion_manage("/notion setdb 1", fid, chat_id)
        assert "No Notion token found" in msg6

        # 7. /notion setdb 1 with valid token
        mock_ns.get_family_notion_status.return_value = {"has_valid_token": True}
        mock_ns.search_databases = AsyncMock(return_value=[{"id": "db_1", "title": "Expenses"}])
        mock_ns.connect_database = AsyncMock(return_value={"database_name": "Expenses", "database_id": "db_1"})
        with patch("src.services.handlers.notion_handler.EncryptionService.decrypt", return_value="secret_ok"):
            msg7 = await handle_notion_manage("/notion setdb 1", fid, chat_id)
            assert "Notion Workspace Connected" in msg7

        # 8. /notion setdb not_found
        with patch("src.services.handlers.notion_handler.EncryptionService.decrypt", return_value="secret_ok"):
            msg8 = await handle_notion_manage("/notion setdb 99", fid, chat_id)
            assert msg8 == "Database not found."

        # 9. /notion sync with items synced
        mock_ns.get_family_notion_status.return_value = {"is_connected": True, "database_name": "Expenses"}
        mock_ns.sync_pending_transactions = AsyncMock(return_value={"synced": 3, "failed": 0})
        msg9 = await handle_notion_manage("/notion sync", fid, chat_id)
        assert "Notion Sync Complete" in msg9

        # 10. /notion sync with everything up to date
        mock_ns.sync_pending_transactions = AsyncMock(return_value={"synced": 0, "failed": 0})
        msg10 = await handle_notion_manage("/notion sync", fid, chat_id)
        assert "Notion Sync is Up to Date" in msg10

        # 11. /notion sync with failures
        mock_ns.sync_pending_transactions = AsyncMock(return_value={"synced": 0, "failed": 2})
        msg11 = await handle_notion_manage("/notion sync", fid, chat_id)
        assert "Notion Sync Failed" in msg11

@pytest.mark.anyio
async def test_handle_notion_pro_feature_restriction():
    fid = uuid4()
    with patch("src.services.handlers.notion_handler.Session") as mock_session_class, \
         patch("src.services.subscription_service.has_unlimited_access", return_value=False):
        mock_session = MagicMock()
        mock_session_class.return_value.__enter__.return_value = mock_session

        msg = await handle_notion_manage("/notion", fid, 123)
        assert "Notion Mirroring is a Pro Feature" in msg
