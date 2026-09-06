import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch
from src.services.telegram_service import TelegramService
from src.core.config import settings

@pytest.mark.anyio
async def test_telegram_edit_message_text_empty():
    service = TelegramService()
    res = await service.edit_message_text(chat_id=123, message_id=456, text="")
    assert res is False

@pytest.mark.anyio
async def test_telegram_edit_message_text_success():
    service = TelegramService()
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_client = AsyncMock()
    mock_client.post.return_value = mock_resp

    with patch("src.services.telegram_service.get_http_client", return_value=mock_client):
        res = await service.edit_message_text(
            chat_id=123,
            message_id=456,
            text="Updated text",
            parse_mode="HTML",
            reply_markup={"inline_keyboard": []}
        )
        assert res is True
        assert mock_client.post.call_count == 1

@pytest.mark.anyio
async def test_telegram_edit_message_text_parse_error_retry():
    service = TelegramService()
    req = httpx.Request("POST", "http://test")
    resp_400 = httpx.Response(400, request=req, text="can't parse entities in message")
    resp_ok = MagicMock()
    resp_ok.raise_for_status.return_value = None

    mock_client = AsyncMock()
    # First attempt raises 400 with parse entities, second succeeds
    mock_client.post.side_effect = [
        httpx.HTTPStatusError("Bad request", request=req, response=resp_400),
        resp_ok
    ]

    with patch("src.services.telegram_service.get_http_client", return_value=mock_client):
        res = await service.edit_message_text(
            chat_id=123,
            message_id=456,
            text="<b>Malformed<b",
            parse_mode="HTML"
        )
        assert res is True
        assert mock_client.post.call_count == 2

@pytest.mark.anyio
async def test_telegram_edit_message_text_not_modified():
    service = TelegramService()
    req = httpx.Request("POST", "http://test")
    resp_400 = httpx.Response(400, request=req, text="Bad Request: message is not modified")
    mock_client = AsyncMock()
    mock_client.post.side_effect = httpx.HTTPStatusError("Bad request", request=req, response=resp_400)

    with patch("src.services.telegram_service.get_http_client", return_value=mock_client):
        res = await service.edit_message_text(chat_id=123, message_id=456, text="Same text")
        assert res is True

@pytest.mark.anyio
async def test_telegram_edit_message_text_other_errors():
    service = TelegramService()
    req = httpx.Request("POST", "http://test")
    resp_500 = httpx.Response(500, request=req, text="Server error")
    mock_client = AsyncMock()
    mock_client.post.side_effect = httpx.HTTPStatusError("Server error", request=req, response=resp_500)

    with patch("src.services.telegram_service.get_http_client", return_value=mock_client):
        res = await service.edit_message_text(chat_id=123, message_id=456, text="Text")
        assert res is False

    # Generic exception
    mock_client.post.side_effect = RuntimeError("Crash")
    with patch("src.services.telegram_service.get_http_client", return_value=mock_client):
        res = await service.edit_message_text(chat_id=123, message_id=456, text="Text")
        assert res is False

@pytest.mark.anyio
async def test_telegram_answer_callback_query():
    service = TelegramService()
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_client = AsyncMock()
    mock_client.post.return_value = mock_resp

    with patch("src.services.telegram_service.get_http_client", return_value=mock_client):
        res = await service.answer_callback_query(
            callback_query_id="cb_123",
            text="Saved!",
            show_alert=True
        )
        assert res is True
        data = mock_client.post.call_args.kwargs["json"]
        assert data["callback_query_id"] == "cb_123"
        assert data["text"] == "Saved!"
        assert data["show_alert"] is True

        # Exception path
        mock_client.post.side_effect = Exception("Net err")
        res_fail = await service.answer_callback_query(callback_query_id="cb_123")
        assert res_fail is False

@pytest.mark.anyio
async def test_telegram_delete_message_failure():
    service = TelegramService()
    mock_client = AsyncMock()
    mock_client.post.side_effect = Exception("Delete failed")
    with patch("src.services.telegram_service.get_http_client", return_value=mock_client):
        res = await service.delete_message(chat_id=123, message_id=456)
        assert res is False

@pytest.mark.anyio
async def test_telegram_get_file_download_url_validations():
    service = TelegramService()
    mock_client = AsyncMock()

    # 1. Non-ok response
    resp1 = MagicMock()
    resp1.raise_for_status.return_value = None
    resp1.json.return_value = {"ok": False}
    mock_client.get.return_value = resp1

    with patch("src.services.telegram_service.get_http_client", return_value=mock_client):
        with pytest.raises(ValueError, match="Could not resolve Telegram file_id"):
            await service.get_file_download_url("bad_file_id")

    # 2. Exceeds max size
    resp2 = MagicMock()
    resp2.raise_for_status.return_value = None
    resp2.json.return_value = {
        "ok": True,
        "result": {
            "file_path": "voice/audio.oga",
            "file_size": 10 * 1024 * 1024
        }
    }
    mock_client.get.return_value = resp2
    with patch("src.services.telegram_service.get_http_client", return_value=mock_client):
        with pytest.raises(ValueError, match="exceeds limit"):
            await service.get_file_download_url("too_large_file_id")

    # 3. Success
    resp3 = MagicMock()
    resp3.raise_for_status.return_value = None
    resp3.json.return_value = {
        "ok": True,
        "result": {
            "file_path": "voice/audio.oga",
            "file_size": 5000
        }
    }
    mock_client.get.return_value = resp3
    with patch("src.services.telegram_service.get_http_client", return_value=mock_client):
        url = await service.get_file_download_url("good_file_id")
        assert "voice/audio.oga" in url

@pytest.mark.anyio
async def test_telegram_download_file_bytes_and_retries():
    service = TelegramService()
    mock_client = AsyncMock()

    # Test retry on connect error
    resp_ok = MagicMock()
    resp_ok.raise_for_status.return_value = None
    resp_ok.content = b"audio-bytes-data"

    mock_client.get.side_effect = [
        httpx.ConnectError("Connection lost"),
        resp_ok
    ]

    with patch.object(service, "get_file_download_url", AsyncMock(return_value="https://test/file.oga")), \
         patch("src.services.telegram_service.get_http_client", return_value=mock_client), \
         patch("asyncio.sleep", AsyncMock()):
        data = await service.download_file_bytes("file_123")
        assert data == b"audio-bytes-data"
        assert mock_client.get.call_count == 2

    # Test file size too large
    resp_huge = MagicMock()
    resp_huge.raise_for_status.return_value = None
    resp_huge.content = b"x" * (4 * 1024 * 1024)
    mock_client.get.side_effect = None
    mock_client.get.return_value = resp_huge
    with patch.object(service, "get_file_download_url", AsyncMock(return_value="https://test/file.oga")), \
         patch("src.services.telegram_service.get_http_client", return_value=mock_client):
        with pytest.raises(ValueError, match="exceeds limit"):
            await service.download_file_bytes("file_123")

@pytest.mark.anyio
async def test_telegram_send_document(tmp_path):
    service = TelegramService()
    test_file = tmp_path / "test.csv"
    test_file.write_text("a,b,c\n1,2,3")

    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_client = AsyncMock()
    mock_client.post.return_value = mock_resp

    with patch("src.services.telegram_service.get_http_client", return_value=mock_client):
        await service.send_document(chat_id=123, file_path=str(test_file), caption="Your CSV")
        assert mock_client.post.call_count == 1
        data = mock_client.post.call_args.kwargs["data"]
        assert data["caption"] == "Your CSV"

@pytest.mark.anyio
async def test_telegram_get_bot_username():
    service = TelegramService()
    if hasattr(service, '_bot_username'):
        delattr(service, '_bot_username')

    # 1. From settings
    with patch.object(settings, "TELEGRAM_BOT_USERNAME", "ConfiguredBot"):
        assert await service.get_bot_username() == "ConfiguredBot"

    # 2. From getMe API
    delattr(service, '_bot_username')
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {"ok": True, "result": {"username": "FetchedBot"}}
    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp

    with patch.object(settings, "TELEGRAM_BOT_USERNAME", None), \
         patch("src.services.telegram_service.get_http_client", return_value=mock_client):
        assert await service.get_bot_username() == "FetchedBot"

    # 3. Fallback on error
    delattr(service, '_bot_username')
    mock_client.get.side_effect = Exception("API fail")
    with patch.object(settings, "TELEGRAM_BOT_USERNAME", None), \
         patch("src.services.telegram_service.get_http_client", return_value=mock_client):
        assert await service.get_bot_username() == "UnknownBot"
