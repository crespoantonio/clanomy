import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import BackgroundTasks
from sqlmodel import Session

from src.services.billing.billing_service import BillingService
from src.db.models import User, Family
from src.core.config import settings

@pytest.mark.anyio
async def test_billing_service_graduation_flows():
    mock_ts = MagicMock()
    mock_ts.send_message = AsyncMock()
    mock_ts.get_bot_username = AsyncMock(return_value="clanomy_bot")
    service = BillingService(mock_ts)

    fid = uuid4()
    admin_id = uuid4()
    member_id = uuid4()

    family = Family(id=fid, name="The Smiths", timezone="UTC")
    admin_user = User(id=admin_id, family_id=fid, username="smith_admin", is_admin=True)
    member_user = User(id=member_id, family_id=fid, username="smith_member", is_admin=False)

    with patch.object(settings, "ENABLE_SUBSCRIPTIONS", True):
        # 1. Non-admin member running /upgrade (triggers graduation menu with admin name)
        bg = BackgroundTasks()
        with patch("src.services.family_service.FamilyService.is_family_admin", return_value=False), \
             patch("src.services.family_service.FamilyService.engine") as mock_engine, \
             patch("src.services.billing.billing_service.Session") as mock_session_class:
            mock_session = MagicMock()
            mock_session.exec.return_value.all.return_value = [admin_user, member_user]
            mock_session_class.return_value.__enter__.return_value = mock_session

            res = await service.handle_upgrade_command(
                background_tasks=bg,
                chat_id=123,
                text="/upgrade",
                user=member_user,
                family=family
            )
            assert res == {"status": "ok"}
            assert len(bg.tasks) == 1

        # 2. Non-admin member running /upgrade solo (triggers graduation solo text)
        bg2 = BackgroundTasks()
        with patch("src.services.family_service.FamilyService.is_family_admin", return_value=False):
            res2 = await service.handle_upgrade_command(
                background_tasks=bg2,
                chat_id=123,
                text="/upgrade solo",
                user=member_user,
                family=family
            )
            assert res2 == {"status": "ok"}
            assert len(bg2.tasks) == 1
            assert "Upgrade to Your Own Solo Pro Workspace" in bg2.tasks[0].kwargs["text"]

        # 3. Non-admin member running /upgrade duo
        bg3 = BackgroundTasks()
        with patch("src.services.family_service.FamilyService.is_family_admin", return_value=False):
            res3 = await service.handle_upgrade_command(
                background_tasks=bg3,
                chat_id=123,
                text="/upgrade duo",
                user=member_user,
                family=family
            )
            assert res3 == {"status": "ok"}
            assert len(bg3.tasks) == 1

        # 4. Non-admin member running /upgrade family
        bg4 = BackgroundTasks()
        with patch("src.services.family_service.FamilyService.is_family_admin", return_value=False):
            res4 = await service.handle_upgrade_command(
                background_tasks=bg4,
                chat_id=123,
                text="/upgrade family",
                user=member_user,
                family=family
            )
            assert res4 == {"status": "ok"}
            assert len(bg4.tasks) == 1

        # 5. /upgrade annual
        bg5 = BackgroundTasks()
        res5 = await service.handle_upgrade_command(
            background_tasks=bg5,
            chat_id=123,
            text="/upgrade annual",
            user=admin_user,
            family=family
        )
        assert res5 == {"status": "ok"}
        assert len(bg5.tasks) == 1
