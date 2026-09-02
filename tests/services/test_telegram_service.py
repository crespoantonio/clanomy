import pytest
import httpx
from unittest.mock import patch, MagicMock, AsyncMock
from src.services.telegram_service import TelegramService

@pytest.fixture
def telegram_service():
    with patch('src.services.telegram_service.settings') as mock_settings:
        mock_settings.TELEGRAM_BOT_TOKEN = "test_token"
        service = TelegramService()
        yield service

@pytest.mark.anyio
async def test_send_document_success(telegram_service, tmp_path):
    test_file = tmp_path / "test.csv"
    test_file.write_text("a,b,c\n1,2,3")
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        await telegram_service.send_document(chat_id=123, file_path=str(test_file), caption="Test")
        
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == "https://api.telegram.org/bottest_token/sendDocument"
        assert kwargs["data"]["chat_id"] == 123
        assert kwargs["data"]["caption"] == "Test"
        assert kwargs["data"]["parse_mode"] == "HTML"
        assert "document" in kwargs["files"]

@pytest.mark.anyio
async def test_send_document_failure(telegram_service, tmp_path):
    test_file = tmp_path / "test.csv"
    test_file.write_text("a,b,c\n1,2,3")
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.HTTPError("Test error")
        
        with patch("src.services.telegram_service.logger.error") as mock_logger:
            with pytest.raises(httpx.HTTPError):
                await telegram_service.send_document(chat_id=123, file_path=str(test_file))
            mock_logger.assert_called_once()
            assert "Failed to send telegram document" in mock_logger.call_args[0][0]

@pytest.mark.anyio
async def test_send_message_with_reply_markup(telegram_service):
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True, "result": {"message_id": 999}}
        mock_post.return_value = mock_response

        reply_markup = {
            "inline_keyboard": [
                [{"text": "Upgrade", "url": "https://checkout.lemonsqueezy.com/buy/123"}]
            ]
        }
        await telegram_service.send_message(
            chat_id=555,
            text="Choose your plan",
            reply_markup=reply_markup
        )

        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert "sendMessage" in args[0]
        json_body = kwargs["json"]
        assert json_body["chat_id"] == 555
        assert json_body["text"] == "Choose your plan"
        assert json_body["reply_markup"] == reply_markup

@pytest.mark.anyio
async def test_post_with_retry_502_retry_success(telegram_service):
    resp_502 = MagicMock()
    resp_502.status_code = 502

    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.raise_for_status.return_value = None

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [resp_502, resp_200]
        resp = await telegram_service._post_with_retry("sendMessage", json={"chat_id": 123, "text": "hello"})
        assert resp == resp_200
        assert mock_post.call_count == 2

@pytest.mark.anyio
async def test_post_with_retry_502_exhaustion(telegram_service):
    resp_502 = MagicMock()
    resp_502.status_code = 502
    resp_502.raise_for_status.side_effect = httpx.HTTPStatusError("502 Bad Gateway", request=MagicMock(), response=resp_502)

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = resp_502
        with pytest.raises(httpx.HTTPStatusError):
            await telegram_service._post_with_retry("sendMessage", max_attempts=3, json={"chat_id": 123, "text": "hello"})
        assert mock_post.call_count == 3




