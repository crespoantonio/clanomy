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

