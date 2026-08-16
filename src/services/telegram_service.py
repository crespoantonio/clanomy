import httpx
import logging
from src.core.config import settings

logger = logging.getLogger(__name__)

class TelegramService:
    def __init__(self):
        self.bot_token = settings.TELEGRAM_BOT_TOKEN
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}"

    async def send_message(self, chat_id: int, text: str) -> None:
        """Sends a message back to the user via Telegram Bot API."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_url}/sendMessage",
                    json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
                )
                response.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to send telegram message to {chat_id}: {e}")

    async def send_document(self, chat_id: int, file_path: str, caption: str | None = None) -> None:
        """Sends a document back to the user via Telegram Bot API."""
        try:
            with open(file_path, "rb") as f:
                async with httpx.AsyncClient() as client:
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
            async with httpx.AsyncClient() as client:
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
