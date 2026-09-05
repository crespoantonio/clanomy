import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from uuid import uuid4
from fastapi import BackgroundTasks

from src.api.routes.telegram import telegram_webhook


def test_telegram_webhook_bills_command():
    """Simulates /bills slash command and verifies interactive menu & keyboard are sent."""
    mock_request = MagicMock()
    mock_request.json = AsyncMock(return_value={
        "message": {
            "message_id": 101,
            "text": "/bills",
            "chat": {"id": 12345, "type": "private"},
            "from": {"id": 12345, "first_name": "Tony"}
        }
    })

    mock_user = MagicMock()
    mock_user.id = uuid4()
    mock_family = MagicMock()
    mock_family.id = uuid4()

    bg_tasks = BackgroundTasks()

    with patch("src.api.routes.telegram.verify_messaging_secret", return_value=True), \
         patch("src.api.routes.telegram.MessagingService") as mock_ms_class, \
         patch("src.api.routes.telegram.CommandHandler") as mock_cmd_class, \
         patch("src.api.routes.telegram.TelegramService") as mock_ts_class:

        mock_ms = mock_ms_class.return_value
        mock_ms.get_or_create_user_and_family.return_value = (mock_user, mock_family)

        mock_cmd = mock_cmd_class.return_value
        mock_cmd.handle_bills_interactive = AsyncMock(return_value=(
            "⏰ Upcoming Bills",
            {"inline_keyboard": [[{"text": "💳 Rent ($800.00)", "callback_data": "bill_v:xyz:1:this"}]]}
        ))

        mock_ts = mock_ts_class.return_value
        mock_ts.send_message = AsyncMock()

        result = asyncio.run(telegram_webhook(
            request=mock_request,
            background_tasks=bg_tasks,
            x_telegram_bot_api_secret_token="dummy_token",
            session=MagicMock()
        ))

        assert result == {"status": "ok"}
        mock_cmd.handle_bills_interactive.assert_called_once()
        # Verify background task was scheduled with keyboard
        assert len(bg_tasks.tasks) == 1
        task = bg_tasks.tasks[0]
        assert task.kwargs["chat_id"] == 12345
        assert task.kwargs["reply_markup"] is not None


def test_telegram_webhook_callback_bills_pagination():
    """Simulates bills_p:2:this pagination callback and verifies edit_message_text call."""
    mock_request = MagicMock()
    mock_request.json = AsyncMock(return_value={
        "callback_query": {
            "id": "cb_p2",
            "data": "bills_p:2:this",
            "from": {"id": 12345, "first_name": "Tony"},
            "message": {
                "message_id": 202,
                "chat": {"id": 12345, "type": "private"}
            }
        }
    })

    mock_user = MagicMock()
    mock_user.id = uuid4()
    mock_family = MagicMock()
    mock_family.id = uuid4()

    bg_tasks = BackgroundTasks()

    with patch("src.api.routes.telegram.verify_messaging_secret", return_value=True), \
         patch("src.api.routes.telegram.MessagingService") as mock_ms_class, \
         patch("src.api.routes.telegram.CommandHandler") as mock_cmd_class, \
         patch("src.api.routes.telegram.TelegramService") as mock_ts_class:

        mock_ms = mock_ms_class.return_value
        mock_ms.get_or_create_user_and_family.return_value = (mock_user, mock_family)

        mock_cmd = mock_cmd_class.return_value
        mock_cmd.handle_bills_interactive = AsyncMock(return_value=(
            "⏰ Upcoming Bills (Page 2)",
            {"inline_keyboard": [[{"text": "Page 2/3", "callback_data": "noop"}]]}
        ))

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
        assert call_kwargs["chat_id"] == 12345
        assert call_kwargs["message_id"] == 202
        assert "Page 2" in call_kwargs["text"]
        mock_ts.answer_callback_query.assert_called_once_with(callback_query_id="cb_p2")


def test_telegram_webhook_callback_bill_view_card():
    """Simulates bill_v:<uuid>:1:this callback and verifies settlement card display."""
    target_bill_id = uuid4()
    mock_request = MagicMock()
    mock_request.json = AsyncMock(return_value={
        "callback_query": {
            "id": "cb_view",
            "data": f"bill_v:{target_bill_id}:1:this",
            "from": {"id": 12345, "first_name": "Tony"},
            "message": {
                "message_id": 303,
                "chat": {"id": 12345, "type": "private"}
            }
        }
    })

    mock_user = MagicMock()
    mock_user.id = uuid4()
    mock_family = MagicMock()
    mock_family.id = uuid4()

    bg_tasks = BackgroundTasks()

    with patch("src.api.routes.telegram.verify_messaging_secret", return_value=True), \
         patch("src.api.routes.telegram.MessagingService") as mock_ms_class, \
         patch("src.api.routes.telegram.build_bill_settlement_card", return_value=("⚡ Settle Bill: Electricity", {"inline_keyboard": []})) as mock_card, \
         patch("src.api.routes.telegram.TelegramService") as mock_ts_class:

        mock_ms = mock_ms_class.return_value
        mock_ms.get_or_create_user_and_family.return_value = (mock_user, mock_family)

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
        mock_card.assert_called_once()
        mock_ts.edit_message_text.assert_called_once()
        assert "Settle Bill" in mock_ts.edit_message_text.call_args[1]["text"]


def test_telegram_webhook_callback_bill_pay():
    """Simulates bill_pay:<uuid>:this 1-tap payment callback."""
    target_bill_id = uuid4()
    mock_request = MagicMock()
    mock_request.json = AsyncMock(return_value={
        "callback_query": {
            "id": "cb_pay",
            "data": f"bill_pay:{target_bill_id}:this",
            "from": {"id": 12345, "first_name": "Tony"},
            "message": {
                "message_id": 404,
                "chat": {"id": 12345, "type": "private"}
            }
        }
    })

    mock_user = MagicMock()
    mock_user.id = uuid4()
    mock_family = MagicMock()
    mock_family.id = uuid4()

    bg_tasks = BackgroundTasks()

    with patch("src.api.routes.telegram.verify_messaging_secret", return_value=True), \
         patch("src.api.routes.telegram.MessagingService") as mock_ms_class, \
         patch("src.api.routes.telegram.settle_bill_by_id", return_value=(True, "✅ Bill marked as paid")) as mock_settle, \
         patch("src.api.routes.telegram.TelegramService") as mock_ts_class:

        mock_ms = mock_ms_class.return_value
        mock_ms.get_or_create_user_and_family.return_value = (mock_user, mock_family)

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
        mock_settle.assert_called_once_with(
            bill_id=target_bill_id,
            user_id=mock_user.id,
            family_id=mock_family.id,
            is_spanish=False
        )
        mock_ts.edit_message_text.assert_called_once()
        mock_ts.answer_callback_query.assert_called_once_with(callback_query_id="cb_pay", text="Bill marked as paid!")


def test_telegram_webhook_force_reply_override_amount():
    """Simulates user replying to ForceReply prompt with a new amount (52.50)."""
    target_bill_id = uuid4()
    mock_request = MagicMock()
    mock_request.json = AsyncMock(return_value={
        "message": {
            "message_id": 505,
            "text": "52.50",
            "chat": {"id": 12345, "type": "private"},
            "from": {"id": 12345, "first_name": "Tony"},
            "reply_to_message": {
                "message_id": 504,
                "text": "✏️ Settle 'Electricity':\nReply with the paid amount:",
                "entities": [
                    {"type": "text_link", "url": f"tg://bill/{target_bill_id}"}
                ]
            }
        }
    })

    mock_user = MagicMock()
    mock_user.id = uuid4()
    mock_family = MagicMock()
    mock_family.id = uuid4()

    bg_tasks = BackgroundTasks()

    with patch("src.api.routes.telegram.verify_messaging_secret", return_value=True), \
         patch("src.api.routes.telegram.MessagingService") as mock_ms_class, \
         patch("src.api.routes.telegram.settle_bill_by_id", return_value=(True, "✅ Bill marked as paid with updated amount")) as mock_settle, \
         patch("src.api.routes.telegram.TelegramService") as mock_ts_class:

        mock_ms = mock_ms_class.return_value
        mock_ms.get_or_create_user_and_family.return_value = (mock_user, mock_family)

        mock_ts = mock_ts_class.return_value
        mock_ts.send_message = AsyncMock()

        result = asyncio.run(telegram_webhook(
            request=mock_request,
            background_tasks=bg_tasks,
            x_telegram_bot_api_secret_token="dummy_token",
            session=MagicMock()
        ))

        assert result == {"status": "ok"}
        mock_settle.assert_called_once_with(
            bill_id=target_bill_id,
            user_id=mock_user.id,
            family_id=mock_family.id,
            override_amount=52.50,
            is_spanish=False
        )
        assert len(bg_tasks.tasks) == 1
        assert "Bill marked as paid" in bg_tasks.tasks[0].kwargs["text"]


def test_telegram_webhook_force_reply_cancel():
    """Simulates user typing 'cancel' to abort bill amount change."""
    target_bill_id = uuid4()
    mock_request = MagicMock()
    mock_request.json = AsyncMock(return_value={
        "message": {
            "message_id": 606,
            "text": "cancel",
            "chat": {"id": 12345, "type": "private"},
            "from": {"id": 12345, "first_name": "Tony"},
            "reply_to_message": {
                "message_id": 605,
                "text": "✏️ Settle 'Electricity':\nReply with the paid amount:",
                "entities": [
                    {"type": "text_link", "url": f"tg://bill/{target_bill_id}"}
                ]
            }
        }
    })

    mock_user = MagicMock()
    mock_user.id = uuid4()
    mock_family = MagicMock()
    mock_family.id = uuid4()

    bg_tasks = BackgroundTasks()

    with patch("src.api.routes.telegram.verify_messaging_secret", return_value=True), \
         patch("src.api.routes.telegram.MessagingService") as mock_ms_class, \
         patch("src.api.routes.telegram.settle_bill_by_id") as mock_settle, \
         patch("src.api.routes.telegram.TelegramService") as mock_ts_class:

        mock_ms = mock_ms_class.return_value
        mock_ms.get_or_create_user_and_family.return_value = (mock_user, mock_family)

        mock_ts = mock_ts_class.return_value
        mock_ts.send_message = AsyncMock()

        result = asyncio.run(telegram_webhook(
            request=mock_request,
            background_tasks=bg_tasks,
            x_telegram_bot_api_secret_token="dummy_token",
            session=MagicMock()
        ))

        assert result == {"status": "ok"}
        mock_settle.assert_not_called()
        assert len(bg_tasks.tasks) == 1
        assert "cancelled" in bg_tasks.tasks[0].kwargs["text"].lower()


def test_telegram_webhook_force_reply_voice_charges_ai_quota():
    """Simulates user replying with a voice note: transcribes, settles, and increments monthly_tx_count."""
    target_bill_id = uuid4()
    mock_request = MagicMock()
    mock_request.json = AsyncMock(return_value={
        "message": {
            "message_id": 707,
            "voice": {"file_id": "voice_file_123", "duration": 5, "file_size": 1000},
            "chat": {"id": 12345, "type": "private"},
            "from": {"id": 12345, "first_name": "Tony"},
            "reply_to_message": {
                "message_id": 706,
                "text": "✏️ Settle 'Electricity':\nReply with the paid amount:",
                "entities": [
                    {"type": "text_link", "url": f"tg://bill/{target_bill_id}"}
                ]
            }
        }
    })

    mock_user = MagicMock()
    mock_user.id = uuid4()
    mock_family = MagicMock()
    mock_family.id = uuid4()
    mock_family.monthly_tx_count = 5
    mock_family.daily_tx_count = 5

    bg_tasks = BackgroundTasks()

    with patch("src.api.routes.telegram.verify_messaging_secret", return_value=True), \
         patch("src.api.routes.telegram.MessagingService") as mock_ms_class, \
         patch("src.api.routes.telegram.check_transaction_allowance", return_value=(True, None, 20)), \
         patch("src.api.routes.telegram.WhisperService") as mock_whisper_class, \
         patch("src.api.routes.telegram.settle_bill_by_id", return_value=(True, "✅ Bill marked as paid with updated amount")) as mock_settle, \
         patch("src.api.routes.telegram.TelegramService") as mock_ts_class:

        mock_ms = mock_ms_class.return_value
        mock_ms.get_or_create_user_and_family.return_value = (mock_user, mock_family)

        mock_ts = mock_ts_class.return_value
        mock_ts.download_file_bytes = AsyncMock(return_value=b"fake_audio")
        mock_ts.send_message = AsyncMock()

        mock_whisper = mock_whisper_class.return_value
        mock_whisper.transcribe = AsyncMock(return_value=("pagamos 48.50", {}))

        result = asyncio.run(telegram_webhook(
            request=mock_request,
            background_tasks=bg_tasks,
            x_telegram_bot_api_secret_token="dummy_token",
            session=MagicMock()
        ))

        assert result == {"status": "ok"}
        mock_settle.assert_called_once_with(
            bill_id=target_bill_id,
            user_id=mock_user.id,
            family_id=mock_family.id,
            override_amount=48.50,
            is_spanish=False
        )
        # Verify AI quota was charged (+1)
        assert mock_family.monthly_tx_count == 6
        assert mock_family.daily_tx_count == 6


def test_telegram_webhook_force_reply_voice_quota_exceeded():
    """Simulates voice note when free AI quota is exhausted: rejects and asks to type text."""
    target_bill_id = uuid4()
    mock_request = MagicMock()
    mock_request.json = AsyncMock(return_value={
        "message": {
            "message_id": 808,
            "voice": {"file_id": "voice_file_123", "duration": 5, "file_size": 1000},
            "chat": {"id": 12345, "type": "private"},
            "from": {"id": 12345, "first_name": "Tony"},
            "reply_to_message": {
                "message_id": 807,
                "text": "✏️ Settle 'Electricity':\nReply with the paid amount:",
                "entities": [
                    {"type": "text_link", "url": f"tg://bill/{target_bill_id}"}
                ]
            }
        }
    })

    mock_user = MagicMock()
    mock_user.id = uuid4()
    mock_family = MagicMock()
    mock_family.id = uuid4()
    mock_family.monthly_tx_count = 20
    mock_family.daily_tx_count = 20

    bg_tasks = BackgroundTasks()

    with patch("src.api.routes.telegram.verify_messaging_secret", return_value=True), \
         patch("src.api.routes.telegram.MessagingService") as mock_ms_class, \
         patch("src.api.routes.telegram.check_transaction_allowance", return_value=(False, "monthly_limit", 20)), \
         patch("src.api.routes.telegram.settle_bill_by_id") as mock_settle, \
         patch("src.api.routes.telegram.TelegramService") as mock_ts_class:

        mock_ms = mock_ms_class.return_value
        mock_ms.get_or_create_user_and_family.return_value = (mock_user, mock_family)

        mock_ts = mock_ts_class.return_value
        mock_ts.send_message = AsyncMock()

        result = asyncio.run(telegram_webhook(
            request=mock_request,
            background_tasks=bg_tasks,
            x_telegram_bot_api_secret_token="dummy_token",
            session=MagicMock()
        ))

        assert result == {"status": "ok"}
        mock_settle.assert_not_called()
        assert len(bg_tasks.tasks) == 1
        assert "Quota Reached" in bg_tasks.tasks[0].kwargs["text"]
        # Quota remained at 20 (not incremented)
        assert mock_family.monthly_tx_count == 20


def test_telegram_webhook_bare_amount_after_daily_error():
    """Simulates user sending bare text '45.50' (no reply_to_message) after daily error while pending edit is active."""
    import time
    from src.api.routes.telegram import _pending_bill_edits

    target_bill_id = uuid4()
    user_tg_id = 556677
    _pending_bill_edits[user_tg_id] = {"bill_id": target_bill_id, "timestamp": time.time()}

    mock_request = MagicMock()
    # Notice: NO reply_to_message!
    mock_request.json = AsyncMock(return_value={
        "message": {
            "message_id": 901,
            "text": "45.50",
            "chat": {"id": user_tg_id, "type": "private"},
            "from": {"id": user_tg_id, "first_name": "Tony"}
        }
    })

    mock_user = MagicMock()
    mock_user.id = uuid4()
    mock_family = MagicMock()
    mock_family.id = uuid4()
    mock_family.monthly_tx_count = 5
    mock_family.daily_tx_count = 5

    bg_tasks = BackgroundTasks()

    with patch("src.api.routes.telegram.verify_messaging_secret", return_value=True), \
         patch("src.api.routes.telegram.MessagingService") as mock_ms_class, \
         patch("src.api.routes.telegram.settle_bill_by_id", return_value=(True, "✅ Bill marked as paid for $45.50.")) as mock_settle, \
         patch("src.api.routes.telegram.TelegramService") as mock_ts_class:

        mock_ms = mock_ms_class.return_value
        mock_ms.get_or_create_user_and_family.return_value = (mock_user, mock_family)

        mock_ts = mock_ts_class.return_value
        mock_ts.send_message = AsyncMock()

        result = asyncio.run(telegram_webhook(
            request=mock_request,
            background_tasks=bg_tasks,
            x_telegram_bot_api_secret_token="dummy_token",
            session=MagicMock()
        ))

        assert result == {"status": "ok"}
        mock_settle.assert_called_once_with(
            bill_id=target_bill_id,
            user_id=mock_user.id,
            family_id=mock_family.id,
            override_amount=45.50,
            is_spanish=False
        )
        # Verify text was free (no AI quota consumed)
        assert mock_family.monthly_tx_count == 5
        assert mock_family.daily_tx_count == 5
        # Verify pending edit was cleared
        assert user_tg_id not in _pending_bill_edits


def test_telegram_webhook_reply_to_daily_limit_error_message():
    """Simulates user swiping-to-reply directly on the daily limit error message."""
    import time
    from src.api.routes.telegram import _pending_bill_edits

    target_bill_id = uuid4()
    user_tg_id = 998877
    _pending_bill_edits[user_tg_id] = {"bill_id": target_bill_id, "timestamp": time.time()}

    mock_request = MagicMock()
    mock_request.json = AsyncMock(return_value={
        "message": {
            "message_id": 905,
            "text": "$52.00",
            "chat": {"id": user_tg_id, "type": "private"},
            "from": {"id": user_tg_id, "first_name": "Tony"},
            "reply_to_message": {
                "message_id": 904,
                "text": "Daily AI voice limit reached. You can still type the amount for free to settle this bill!"
            }
        }
    })

    mock_user = MagicMock()
    mock_user.id = uuid4()
    mock_family = MagicMock()
    mock_family.id = uuid4()

    bg_tasks = BackgroundTasks()

    with patch("src.api.routes.telegram.verify_messaging_secret", return_value=True), \
         patch("src.api.routes.telegram.MessagingService") as mock_ms_class, \
         patch("src.api.routes.telegram.settle_bill_by_id", return_value=(True, "✅ Bill marked as paid for $52.00.")) as mock_settle, \
         patch("src.api.routes.telegram.TelegramService") as mock_ts_class:

        mock_ms = mock_ms_class.return_value
        mock_ms.get_or_create_user_and_family.return_value = (mock_user, mock_family)

        mock_ts = mock_ts_class.return_value
        mock_ts.send_message = AsyncMock()

        result = asyncio.run(telegram_webhook(
            request=mock_request,
            background_tasks=bg_tasks,
            x_telegram_bot_api_secret_token="dummy_token",
            session=MagicMock()
        ))

        assert result == {"status": "ok"}
        mock_settle.assert_called_once_with(
            bill_id=target_bill_id,
            user_id=mock_user.id,
            family_id=mock_family.id,
            override_amount=52.00,
            is_spanish=False
        )
        assert user_tg_id not in _pending_bill_edits


def test_telegram_webhook_bare_cancel():
    """Simulates user sending bare text 'cancel' without replying while pending edit is active."""
    import time
    from src.api.routes.telegram import _pending_bill_edits

    target_bill_id = uuid4()
    user_tg_id = 334455
    _pending_bill_edits[user_tg_id] = {"bill_id": target_bill_id, "timestamp": time.time()}

    mock_request = MagicMock()
    mock_request.json = AsyncMock(return_value={
        "message": {
            "message_id": 910,
            "text": "cancel",
            "chat": {"id": user_tg_id, "type": "private"},
            "from": {"id": user_tg_id, "first_name": "Tony"}
        }
    })

    mock_user = MagicMock()
    mock_user.id = uuid4()
    mock_family = MagicMock()
    mock_family.id = uuid4()

    bg_tasks = BackgroundTasks()

    with patch("src.api.routes.telegram.verify_messaging_secret", return_value=True), \
         patch("src.api.routes.telegram.MessagingService") as mock_ms_class, \
         patch("src.api.routes.telegram.settle_bill_by_id") as mock_settle, \
         patch("src.api.routes.telegram.TelegramService") as mock_ts_class:

        mock_ms = mock_ms_class.return_value
        mock_ms.get_or_create_user_and_family.return_value = (mock_user, mock_family)

        mock_ts = mock_ts_class.return_value
        mock_ts.send_message = AsyncMock()

        result = asyncio.run(telegram_webhook(
            request=mock_request,
            background_tasks=bg_tasks,
            x_telegram_bot_api_secret_token="dummy_token",
            session=MagicMock()
        ))

        assert result == {"status": "ok"}
        mock_settle.assert_not_called()
        assert len(bg_tasks.tasks) == 1
        assert "cancelled" in bg_tasks.tasks[0].kwargs["text"]
        assert user_tg_id not in _pending_bill_edits


