import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from uuid import uuid4

from src.services.handlers.currency_handler import (
    CURRENCY_PAGES,
    build_currency_keyboard,
    format_currency_menu_text,
    format_currency_success_text,
    handle_manage_currency
)


def test_currency_catalog_structure():
    """Catalog should have 2 pages with 9 items each (3x3 grid)."""
    assert len(CURRENCY_PAGES) == 2
    for page in CURRENCY_PAGES:
        assert len(page) == 9
        for code, label, full_name in page:
            assert len(code) == 3
            assert len(label) > 0
            assert len(full_name) > 0


def test_build_currency_keyboard_page_1():
    """Page 1 keyboard should have 3 rows of 3 currency buttons and 1 nav row."""
    keyboard = build_currency_keyboard(page=1, active_currency="USD")
    rows = keyboard.get("inline_keyboard", [])
    assert len(rows) == 4  # 3 currency rows + 1 nav row

    # First 3 rows must have 3 buttons each
    for r in rows[:3]:
        assert len(r) == 3
        for btn in r:
            assert btn["callback_data"].startswith("curr_set:")

    # USD should have the checkmark
    usd_btn = rows[0][0]
    assert usd_btn["callback_data"] == "curr_set:USD"
    assert usd_btn["text"].startswith("✓ ")

    # EUR should not have a checkmark
    eur_btn = rows[0][1]
    assert eur_btn["callback_data"] == "curr_set:EUR"
    assert not eur_btn["text"].startswith("✓ ")

    # Nav row
    nav_row = rows[3]
    assert len(nav_row) == 3
    assert nav_row[0]["callback_data"] == "curr_p:2"
    assert nav_row[1]["callback_data"] == "noop"
    assert "Page 1/2" in nav_row[1]["text"]
    assert nav_row[2]["callback_data"] == "curr_p:2"


def test_build_currency_keyboard_page_2():
    """Page 2 keyboard should highlight active currency on page 2."""
    keyboard = build_currency_keyboard(page=2, active_currency="JPY")
    rows = keyboard.get("inline_keyboard", [])
    assert len(rows) == 4

    # Find JPY
    found_jpy = False
    for r in rows[:3]:
        for btn in r:
            if btn["callback_data"] == "curr_set:JPY":
                assert btn["text"].startswith("✓ ")
                found_jpy = True
    assert found_jpy

    # Nav row points back to page 1
    nav_row = rows[3]
    assert nav_row[0]["callback_data"] == "curr_p:1"
    assert "Page 2/2" in nav_row[1]["text"]
    assert nav_row[2]["callback_data"] == "curr_p:1"


def test_format_currency_menu_text():
    """Menu text introduces current currency and instructions."""
    text = format_currency_menu_text("ARS")
    assert "ARS" in text
    assert "Select Household Default Currency" in text


def test_format_currency_success_text():
    """Success text confirms updated currency."""
    text = format_currency_success_text("EUR")
    assert "EUR" in text
    assert "Default Currency Updated to EUR" in text
    assert "/currency" in text


def test_handle_manage_currency():
    """handle_manage_currency fetches currency and returns menu + keyboard."""
    import asyncio
    user_id = uuid4()
    family_id = uuid4()

    with patch("src.services.handlers.currency_handler.FamilyService") as mock_fs_class:
        mock_fs = mock_fs_class.return_value
        mock_fs.get_family_default_currency.return_value = "CLP"

        text, keyboard = asyncio.run(handle_manage_currency(user_id, family_id))

        assert "CLP" in text
        assert "inline_keyboard" in keyboard
        # Check CLP has checkmark
        clp_found = False
        for row in keyboard["inline_keyboard"][:3]:
            for btn in row:
                if btn["callback_data"] == "curr_set:CLP":
                    assert btn["text"].startswith("✓ ")
                    clp_found = True
        assert clp_found


def test_telegram_webhook_callback_query_page_flip():
    """Simulates receiving a curr_p:2 callback query and verifies edit_message_text & answer_callback_query."""
    import asyncio
    from fastapi import BackgroundTasks
    from unittest.mock import AsyncMock
    from src.api.routes.telegram import telegram_webhook

    mock_request = MagicMock()
    mock_request.json = AsyncMock(return_value={
        "callback_query": {
            "id": "cb_123",
            "data": "curr_p:2",
            "from": {"id": 9999, "first_name": "Tester"},
            "message": {
                "message_id": 444,
                "chat": {"id": 9999, "type": "private"}
            }
        }
    })

    mock_user = MagicMock()
    mock_family = MagicMock()
    mock_family.id = uuid4()

    bg_tasks = BackgroundTasks()

    with patch("src.api.routes.telegram.verify_messaging_secret", return_value=True), \
         patch("src.api.routes.telegram.MessagingService") as mock_ms_class, \
         patch("src.api.routes.telegram.FamilyService") as mock_fs_class, \
         patch("src.api.routes.telegram.TelegramService") as mock_ts_class:

        mock_ms = mock_ms_class.return_value
        mock_ms.get_or_create_user_and_family.return_value = (mock_user, mock_family)

        mock_fs = mock_fs_class.return_value
        mock_fs.get_family_default_currency.return_value = "USD"

        mock_ts = mock_ts_class.return_value
        mock_ts.edit_message_text = AsyncMock()
        mock_ts.answer_callback_query = AsyncMock()

        result = asyncio.run(telegram_webhook(
            request=mock_request,
            background_tasks=bg_tasks,
            x_telegram_bot_api_secret_token="dummy_token",
            session=MagicMock()
        ))

        assert result == {"status": "ok"}

        mock_ts.edit_message_text.assert_called_once()
        call_kwargs = mock_ts.edit_message_text.call_args[1]
        assert call_kwargs["chat_id"] == 9999
        assert call_kwargs["message_id"] == 444
        # Verify page 2 keyboard was built
        assert "Page 2/2" in str(call_kwargs["reply_markup"])
        mock_ts.answer_callback_query.assert_called_once_with(callback_query_id="cb_123")


def test_telegram_webhook_callback_query_set_currency():
    """Simulates receiving curr_set:EUR callback query and verifies DB update & response."""
    import asyncio
    from fastapi import BackgroundTasks
    from unittest.mock import AsyncMock
    from src.api.routes.telegram import telegram_webhook

    mock_request = MagicMock()
    mock_request.json = AsyncMock(return_value={
        "callback_query": {
            "id": "cb_456",
            "data": "curr_set:EUR",
            "from": {"id": 8888, "first_name": "Tester"},
            "message": {
                "message_id": 555,
                "chat": {"id": 8888, "type": "private"}
            }
        }
    })

    mock_user = MagicMock()
    mock_family = MagicMock()
    mock_family.id = uuid4()

    bg_tasks = BackgroundTasks()

    with patch("src.api.routes.telegram.verify_messaging_secret", return_value=True), \
         patch("src.api.routes.telegram.MessagingService") as mock_ms_class, \
         patch("src.api.routes.telegram.FamilyService") as mock_fs_class, \
         patch("src.api.routes.telegram.TelegramService") as mock_ts_class:

        mock_ms = mock_ms_class.return_value
        mock_ms.get_or_create_user_and_family.return_value = (mock_user, mock_family)

        mock_fs = mock_fs_class.return_value
        mock_fs.set_family_default_currency = MagicMock()

        mock_ts = mock_ts_class.return_value
        mock_ts.delete_message = AsyncMock(return_value=True)
        mock_ts.send_message = AsyncMock()
        mock_ts.answer_callback_query = AsyncMock()

        result = asyncio.run(telegram_webhook(
            request=mock_request,
            background_tasks=bg_tasks,
            x_telegram_bot_api_secret_token="dummy_token",
            session=MagicMock()
        ))

        assert result == {"status": "ok"}

        mock_fs.set_family_default_currency.assert_called_once_with(mock_family.id, "EUR")
        mock_ts.delete_message.assert_called_once_with(chat_id=8888, message_id=555)
        mock_ts.send_message.assert_called_once()
        send_kwargs = mock_ts.send_message.call_args[1]
        assert send_kwargs["chat_id"] == 8888
        assert "Default Currency Updated to EUR" in send_kwargs["text"]
        mock_ts.answer_callback_query.assert_called_once_with(
            callback_query_id="cb_456",
            text="Default currency set to EUR"
        )


def test_ensure_webhook_allowed_updates_adds_callback_query():
    """When Telegram allowed_updates is ['message'], ensure_webhook_allowed_updates updates it."""
    import asyncio
    from src.services.telegram_service import TelegramService

    svc = TelegramService()
    svc.bot_token = "fake_token_123"

    mock_webhook_info = {
        "url": "https://clanomy-api.onrender.com/api/v1/telegram/webhook",
        "allowed_updates": ["message"]
    }

    with patch.object(svc, "get_webhook_info", AsyncMock(return_value=mock_webhook_info)), \
         patch.object(svc, "_post_with_retry", AsyncMock()) as mock_post:

        updated = asyncio.run(svc.ensure_webhook_allowed_updates(["message", "callback_query"]))

        assert updated is True
        mock_post.assert_called_once()
        endpoint, payload_kwargs = mock_post.call_args[0][0], mock_post.call_args[1]["json"]
        assert endpoint == "setWebhook"
        assert set(payload_kwargs["allowed_updates"]) == {"message", "callback_query"}
        assert payload_kwargs["url"] == "https://clanomy-api.onrender.com/api/v1/telegram/webhook"


def test_ensure_webhook_allowed_updates_skips_when_already_allowed():
    """When Telegram already has callback_query in allowed_updates, setWebhook is not called."""
    import asyncio
    from src.services.telegram_service import TelegramService

    svc = TelegramService()
    svc.bot_token = "fake_token_123"

    mock_webhook_info = {
        "url": "https://clanomy-api.onrender.com/api/v1/telegram/webhook",
        "allowed_updates": ["message", "callback_query"]
    }

    with patch.object(svc, "get_webhook_info", AsyncMock(return_value=mock_webhook_info)), \
         patch.object(svc, "_post_with_retry", AsyncMock()) as mock_post:

        updated = asyncio.run(svc.ensure_webhook_allowed_updates(["message", "callback_query"]))

        assert updated is True
        mock_post.assert_not_called()



