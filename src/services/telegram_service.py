import asyncio
import httpx
import logging
from src.core.config import settings
from src.core.http_client import get_http_client

from typing import Optional

logger = logging.getLogger(__name__)

class TelegramService:
    def __init__(self):
        self.bot_token = settings.TELEGRAM_BOT_TOKEN
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}"

    async def _post_with_retry(self, endpoint: str, max_attempts: int = 3, **kwargs) -> httpx.Response:
        """Low-level POST with automatic retry on transient network errors and Telegram 429s."""
        client = get_http_client()
        for attempt in range(1, max_attempts + 1):
            try:
                response = await client.post(f"{self.api_url}/{endpoint}", **kwargs)
                if response.status_code == 429:
                    retry_after = 1.5
                    try:
                        data = response.json()
                        retry_after = float(data.get("parameters", {}).get("retry_after", 1.5))
                    except Exception:
                        pass
                    logger.warning(
                        f"[Telegram 429] Rate limited on /{endpoint}. Retrying in {retry_after:.2f}s "
                        f"(attempt {attempt}/{max_attempts})"
                    )
                    if attempt < max_attempts:
                        await asyncio.sleep(retry_after)
                        continue
                if response.status_code in (500, 502, 503, 504):
                    if attempt < max_attempts:
                        backoff = 0.5 * (2 ** (attempt - 1))
                        logger.warning(
                            f"[Telegram {response.status_code}] Transient server error on /{endpoint}. "
                            f"Retrying in {backoff:.2f}s (attempt {attempt}/{max_attempts})..."
                        )
                        await asyncio.sleep(backoff)
                        continue
                response.raise_for_status()
                return response
            except (httpx.TimeoutException, httpx.ConnectError, ConnectionError, OSError) as net_err:
                if attempt == max_attempts:
                    raise
                backoff = 0.5 * (2 ** (attempt - 1))
                logger.warning(f"[Telegram Network Err] {net_err}. Retrying in {backoff:.2f}s (attempt {attempt}/{max_attempts})...")
                await asyncio.sleep(backoff)

    async def send_message(self, chat_id: int, text: str, parse_mode: Optional[str] = "HTML") -> None:
        """Sends a message back to the user via Telegram Bot API with retry on transient errors and fallback on parse errors."""
        try:
            payload = {"chat_id": chat_id, "text": text}
            if parse_mode:
                payload["parse_mode"] = parse_mode
            await self._post_with_retry("sendMessage", json=payload)
        except httpx.HTTPStatusError as e:
            if parse_mode and e.response.status_code == 400 and "can't parse entities" in e.response.text:
                logger.warning(f"Telegram HTML parse error for chat {chat_id}. Retrying as plain text.")
                await self.send_message(chat_id=chat_id, text=text, parse_mode=None)
            else:
                logger.error(f"Failed to send telegram message to {chat_id}: {e}")
        except Exception as e:
            logger.error(f"Failed to send telegram message to {chat_id}: {e}")

    async def delete_message(self, chat_id: int, message_id: int) -> bool:
        """Deletes a message from a Telegram chat."""
        try:
            client = get_http_client()
            response = await client.post(
                f"{self.api_url}/deleteMessage",
                json={"chat_id": chat_id, "message_id": message_id}
            )
            response.raise_for_status()
            return True
        except Exception as e:
            logger.warning(f"Failed to delete message {message_id} in chat {chat_id}: {e}")
            return False

    async def get_file_url(self, file_id: str) -> str:
        """Resolves a Telegram file_id to a direct download URL."""
        return await self.get_file_download_url(file_id)

    async def get_file_download_url(self, file_id: str) -> str:
        """Resolves a Telegram file_id to a direct download URL."""
        client = get_http_client()
        response = await client.get(f"{self.api_url}/getFile?file_id={file_id}")
        response.raise_for_status()
        data = response.json()
        if not data.get("ok") or "result" not in data or "file_path" not in data["result"]:
            raise ValueError(f"Could not resolve Telegram file_id {file_id}")
        file_path = data["result"]["file_path"]
        return f"https://api.telegram.org/file/bot{self.bot_token}/{file_path}"

    async def download_file_bytes(self, file_id: str) -> bytes:
        """Downloads a Telegram file directly into bytes."""
        download_url = await self.get_file_download_url(file_id)
        client = get_http_client()
        response = await client.get(download_url)
        response.raise_for_status()
        return response.content

    async def send_document(self, chat_id: int, file_path: str, caption: str | None = None) -> None:
        """Sends a document back to the user via Telegram Bot API."""
        try:
            with open(file_path, "rb") as f:
                client = get_http_client()
                data = {"chat_id": chat_id, "parse_mode": "HTML"}
                if caption:
                    data["caption"] = caption
                    
                response = await client.post(
                    f"{self.api_url}/sendDocument",
                    data=data,
                    files={"document": f}
                )
                response.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to send telegram document to {chat_id}: {e}")
            raise e

    async def get_file_url(self, file_id: str) -> str | None:
        """Resolves a file_id to its direct download URL."""
        try:
            client = get_http_client()
            response = await client.get(
                f"{self.api_url}/getFile",
                params={"file_id": file_id}
            )
            response.raise_for_status()
            data = response.json()
            if data.get("ok"):
                file_path = data["result"]["file_path"]
                return f"https://api.telegram.org/file/bot{self.bot_token}/{file_path}"
            return None
        except Exception as e:
            logger.error(f"Failed to resolve file_id {file_id}: {e}")
            return None

    async def get_bot_username(self) -> str:
        """Cache bot username or fetch via Telegram getMe."""
        if hasattr(self, '_bot_username'):
            return self._bot_username
            
        if settings.TELEGRAM_BOT_USERNAME:
            self._bot_username = settings.TELEGRAM_BOT_USERNAME
            return self._bot_username
            
        try:
            client = get_http_client()
            response = await client.get(f"{self.api_url}/getMe")
            response.raise_for_status()
            data = response.json()
            if data.get("ok"):
                self._bot_username = data["result"]["username"]
                return self._bot_username
        except Exception as e:
            logger.error(f"Failed to fetch bot username via getMe: {e}")
            
        return "UnknownBot"

    async def send_subscription_invoice(
        self,
        chat_id: int,
        plan_type: str,
        family_id: str | int
    ) -> bool:
        """
        Sends an auto-renewing Telegram Stars subscription invoice via sendInvoice Bot API.
        Currency: XTR (Telegram Stars).
        Subscription period: 2592000 (30 days in seconds).
        Payload identifier: sub_solo_pro_{family_id} or sub_family_pro_{family_id}.
        """
        from src.core.subscription_config import get_tier_config
        config = get_tier_config(plan_type)

        if not config:
            raise ValueError(f"Invalid subscription plan type for invoice: {plan_type}")

        try:
            client = get_http_client()
            body = {
                "chat_id": chat_id,
                "title": config.title,
                "description": config.description,
                "payload": f"sub_{config.code}_{family_id}",
                "provider_token": "",
                "currency": "XTR",
                "prices": [{"label": config.title, "amount": config.stars}],
                "subscription_period": config.subscription_period_seconds,
                "start_parameter": f"sub_{config.code}"
            }
            response = await client.post(
                f"{self.api_url}/sendInvoice",
                json=body
            )
            response.raise_for_status()
            data = response.json()
            return bool(data.get("ok"))
        except Exception as e:
            logger.error(f"Failed to send subscription invoice for plan {plan_type} to chat {chat_id}: {e}")
            raise

    async def answer_pre_checkout_query(
        self,
        pre_checkout_query_id: str,
        ok: bool = True,
        error_message: str | None = None
    ) -> bool:
        """
        Answers a pre-checkout query via Telegram Bot API answerPreCheckoutQuery.
        Must respond within 10 seconds.
        """
        try:
            client = get_http_client()
            body = {
                "pre_checkout_query_id": pre_checkout_query_id,
                "ok": ok
            }
            if not ok and error_message:
                body["error_message"] = error_message

            response = await client.post(
                f"{self.api_url}/answerPreCheckoutQuery",
                json=body
            )
            response.raise_for_status()
            data = response.json()
            return bool(data.get("ok"))
        except Exception as e:
            logger.error(f"Failed to answer pre-checkout query {pre_checkout_query_id}: {e}")
            return False


