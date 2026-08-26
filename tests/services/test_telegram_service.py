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
async def test_send_subscription_invoice_solo_pro_success(telegram_service):
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"ok": True, "result": {"message_id": 999}}
        mock_post.return_value = mock_response

        res = await telegram_service.send_subscription_invoice(
            chat_id=555,
            plan_type="solo_pro",
            family_id="fam-uuid-111"
        )
        assert res is True
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == "https://api.telegram.org/bottest_token/sendInvoice"
        json_body = kwargs["json"]
        assert json_body["chat_id"] == 555
        assert json_body["title"] == "Clanomy Solo Pro"
        assert json_body["payload"] == "sub_solo_pro_fam-uuid-111"
        assert json_body["currency"] == "XTR"
        assert json_body["subscription_period"] == 2592000
        assert json_body["provider_token"] == ""
        assert json_body["prices"] == [{"label": "Clanomy Solo Pro", "amount": 150}]

@pytest.mark.anyio
async def test_send_subscription_invoice_family_pro_success(telegram_service):
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"ok": True, "result": {"message_id": 1000}}
        mock_post.return_value = mock_response

        res = await telegram_service.send_subscription_invoice(
            chat_id=777,
            plan_type="family_pro",
            family_id="fam-uuid-222"
        )
        assert res is True
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == "https://api.telegram.org/bottest_token/sendInvoice"
        json_body = kwargs["json"]
        assert json_body["chat_id"] == 777
        assert json_body["title"] == "Clanomy Family Pro"
        assert json_body["payload"] == "sub_family_pro_fam-uuid-222"
        assert json_body["currency"] == "XTR"
        assert json_body["subscription_period"] == 2592000
        assert json_body["provider_token"] == ""
        assert json_body["prices"] == [{"label": "Clanomy Family Pro", "amount": 300}]

@pytest.mark.anyio
async def test_send_subscription_invoice_invalid_plan(telegram_service):
    with pytest.raises(ValueError, match="Invalid subscription plan type"):
        await telegram_service.send_subscription_invoice(
            chat_id=123,
            plan_type="invalid_plan",
            family_id="fam-123"
        )

@pytest.mark.anyio
async def test_send_subscription_invoice_http_error(telegram_service):
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.HTTPError("Telegram API error")
        with pytest.raises(httpx.HTTPError):
            await telegram_service.send_subscription_invoice(
                chat_id=123,
                plan_type="solo_pro",
                family_id="fam-123"
            )

@pytest.mark.anyio
async def test_answer_pre_checkout_query_ok_true(telegram_service):
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"ok": True, "result": True}
        mock_post.return_value = mock_response

        res = await telegram_service.answer_pre_checkout_query(
            pre_checkout_query_id="query_12345",
            ok=True
        )
        assert res is True
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == "https://api.telegram.org/bottest_token/answerPreCheckoutQuery"
        json_body = kwargs["json"]
        assert json_body["pre_checkout_query_id"] == "query_12345"
        assert json_body["ok"] is True
        assert "error_message" not in json_body

@pytest.mark.anyio
async def test_answer_pre_checkout_query_ok_false_with_error(telegram_service):
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"ok": True, "result": True}
        mock_post.return_value = mock_response

        res = await telegram_service.answer_pre_checkout_query(
            pre_checkout_query_id="query_67890",
            ok=False,
            error_message="Invalid plan or payment expired."
        )
        assert res is True
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == "https://api.telegram.org/bottest_token/answerPreCheckoutQuery"
        json_body = kwargs["json"]
        assert json_body["pre_checkout_query_id"] == "query_67890"
        assert json_body["ok"] is False
        assert json_body["error_message"] == "Invalid plan or payment expired."

@pytest.mark.anyio
async def test_answer_pre_checkout_query_failure(telegram_service):
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.HTTPError("Network failure")
        with patch("src.services.telegram_service.logger.error") as mock_logger:
            res = await telegram_service.answer_pre_checkout_query(
                pre_checkout_query_id="query_fail",
                ok=True
            )
            assert res is False
            mock_logger.assert_called_once()
            assert "Failed to answer pre-checkout query" in mock_logger.call_args[0][0]



