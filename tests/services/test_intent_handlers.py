import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch
from src.services.handlers.family_handler import (
    handle_create_family,
    handle_generate_invite,
    handle_family_info,
    handle_leave_family,
    handle_remove_member,
)
from src.services.handlers.currency_handler import handle_manage_currency
from src.services.handlers.account_handler import handle_delete_account
from src.services.family_service import PlanLimitExceededError


@pytest.mark.anyio
async def test_handle_create_family():
    user_uuid = uuid4()
    with patch("src.services.handlers.family_handler.FamilyService") as MockFamilyService:
        mock_instance = MockFamilyService.return_value
        mock_instance.create_family.return_value = None

        res = await handle_create_family(user_uuid, "Test Household")
        assert "Test Household" in res
        assert "created" in res


@pytest.mark.anyio
async def test_handle_family_info():
    user_uuid = uuid4()
    with patch("src.services.handlers.family_handler.FamilyService") as MockFamilyService:
        mock_instance = MockFamilyService.return_value
        mock_instance.get_family_info.return_value = {
            "name": "Smith Family",
            "members": [
                {"full_name": "Alice Smith", "username": "alice", "is_admin": True},
                {"full_name": "Bob Smith", "username": "bob", "is_admin": False},
            ],
            "plan_type": "family_pro",
            "monthly_tx_count": 12,
            "transactions_count": 45,
            "active_invites_count": 1,
        }

        res = await handle_family_info(user_uuid)
        assert "Smith Family" in res
        assert "Alice Smith" in res
        assert "Bob Smith" in res
        assert "Family Pro" in res


@pytest.mark.anyio
async def test_handle_generate_invite_success():
    user_uuid = uuid4()
    family_id = uuid4()
    with patch("src.services.handlers.family_handler.FamilyService") as MockFamilyService, \
         patch("src.services.handlers.family_handler.TelegramService") as MockTelegramService:
        
        mock_fs = MockFamilyService.return_value
        mock_fs.create_invite.return_value = (MagicMock(), "https://t.me/ClanomyBot?start=inv_123")

        mock_ts = MockTelegramService.return_value
        mock_ts.get_bot_username = AsyncMock(return_value="ClanomyBot")

        res = await handle_generate_invite(user_uuid, family_id)
        assert "https://t.me/ClanomyBot?start=inv_123" in res


@pytest.mark.anyio
async def test_handle_generate_invite_limit_exceeded():
    user_uuid = uuid4()
    family_id = uuid4()
    with patch("src.services.handlers.family_handler.FamilyService") as MockFamilyService, \
         patch("src.services.handlers.family_handler.TelegramService") as MockTelegramService:
        
        mock_fs = MockFamilyService.return_value
        mock_fs.create_invite.side_effect = PlanLimitExceededError("Limit reached")

        mock_ts = MockTelegramService.return_value
        mock_ts.get_bot_username = AsyncMock(return_value="ClanomyBot")

        res = await handle_generate_invite(user_uuid, family_id)
        assert "Family Invites Require Family Pro" in res


@pytest.mark.anyio
async def test_handle_manage_currency():
    user_uuid = uuid4()
    family_id = uuid4()
    with patch("src.services.handlers.currency_handler.FamilyService") as MockFamilyService:
        mock_fs = MockFamilyService.return_value
        mock_fs.set_family_default_currency.return_value = "EUR"

        res = await handle_manage_currency(user_uuid, family_id, "/currency EUR")
        assert "Default Currency Updated to EUR!" in res


@pytest.mark.anyio
async def test_handle_delete_account():
    user_uuid = uuid4()
    # Confirmation prompt
    res_prompt = await handle_delete_account(user_uuid, "delete account")
    assert "CONFIRM DELETE" in res_prompt

    # Actual deletion
    with patch("src.services.handlers.account_handler.AccountService") as MockAccountService:
        mock_acc = MockAccountService.return_value
        mock_acc.delete_account = AsyncMock(return_value=True)

        res_deleted = await handle_delete_account(user_uuid, "CONFIRM DELETE")
        assert "permanently deleted" in res_deleted
