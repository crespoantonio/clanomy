import pytest
from uuid import uuid4
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, AsyncMock

from src.services.handlers.bill_handler import handle_bills_interactive
from src.db.models import User, Family

@pytest.mark.anyio
async def test_handle_bills_interactive():
    user = User(id=uuid4(), timezone="UTC")
    family = Family(id=uuid4(), timezone="UTC")

    with patch("src.services.query.service.QueryService._resolve_date_range", return_value=(datetime.now(timezone.utc), datetime.now(timezone.utc))), \
         patch("src.services.query.service.QueryService._fetch_and_decrypt_scheduled_bills", return_value=[]), \
         patch("src.services.query.formatters.format_bills_summary", return_value="Summary text"), \
         patch("src.services.handlers.bill_handler.build_bills_keyboard", return_value={"inline_keyboard": []}):

        # 1. default args (this_month)
        text, kb = await handle_bills_interactive(user, family, args="", page=1)
        assert text == "Summary text"
        assert kb == {"inline_keyboard": []}

        # 2. next month args
        text2, kb2 = await handle_bills_interactive(user, family, args="next", page=2)
        assert text2 == "Summary text"
