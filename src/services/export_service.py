import os
import tempfile
import csv
import json
import time
import logging
import asyncio
from typing import List, Optional, Tuple
from uuid import UUID
from datetime import datetime, timezone
from sqlmodel import Session, select
from threading import Lock

from src.db.models import Transaction
from src.core.encryption import EncryptionService
from src.services.telegram_service import TelegramService
from src.services.query_service import DecryptedTransaction

logger = logging.getLogger(__name__)

class ExportService:
    _instance = None
    _lock = Lock()

    def __new__(cls, engine_override=None):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ExportService, cls).__new__(cls)
                cls._instance.encryption_service = EncryptionService()
                cls._instance.telegram_service = TelegramService()
            if engine_override is not None:
                cls._instance.engine = engine_override
            elif not hasattr(cls._instance, 'engine'):
                from src.db.session import engine as db_engine
                cls._instance.engine = db_engine
            return cls._instance

    def _decrypt_transaction(self, tx: Transaction) -> Optional[DecryptedTransaction]:
        """Decrypts a single transaction."""
        try:
            decrypted_amount_str = self.encryption_service.decrypt(tx.amount)
            amount_parts = decrypted_amount_str.split(" ", 1)
            amount = float(amount_parts[0])
            currency = amount_parts[1] if len(amount_parts) > 1 else "USD"

            concept = self.encryption_service.decrypt(tx.concept)

            return DecryptedTransaction(
                id=tx.id,
                family_id=tx.family_id,
                user_id=tx.user_id,
                timestamp=tx.timestamp,
                amount=amount,
                currency=currency,
                category=tx.category,
                concept=concept
            )
        except Exception as e:
            logger.error(f"Failed to decrypt transaction {tx.id}: {e}")
            return None

    def generate_csv(self, transactions: List[DecryptedTransaction], file_path: str) -> None:
        """Generates a CSV file from a list of decrypted transactions."""
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["Timestamp (UTC)", "Amount", "Currency", "Category", "Concept"])
            for tx in transactions:
                writer.writerow([
                    tx.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC"),
                    tx.amount,
                    tx.currency,
                    tx.category,
                    tx.concept
                ])

    def generate_json(self, transactions: List[DecryptedTransaction], family_id: UUID, file_path: str) -> None:
        """Generates a JSON file from a list of decrypted transactions."""
        data = {
            "family_id": str(family_id),
            "exported_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "total_count": len(transactions),
            "transactions": [
                {
                    "id": str(tx.id),
                    "timestamp": tx.timestamp.isoformat().replace("+00:00", "Z"),
                    "amount": tx.amount,
                    "currency": tx.currency,
                    "category": tx.category,
                    "concept": tx.concept
                }
                for tx in transactions
            ]
        }
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    async def export_data(self, family_id: UUID, format: str = "csv") -> Tuple[str, int]:
        """Fetches, decrypts, and writes transactions to a temp file."""
        start_time = time.time()
        
        def fetch_and_process():
            with Session(self.engine) as session:
                statement = select(Transaction).where(Transaction.family_id == family_id).order_by(Transaction.timestamp.desc())
                results = session.exec(statement).all()
                
                decrypted = []
                for tx in results:
                    dtx = self._decrypt_transaction(tx)
                    if dtx:
                        decrypted.append(dtx)
                
                return decrypted
            
        transactions = await asyncio.to_thread(fetch_and_process)
        count = len(transactions)
        
        fd, temp_path = tempfile.mkstemp(prefix=f"famfin_export_{family_id}_", suffix=f".{format}")
        os.close(fd) # Close immediately, we use standard open()
        
        try:
            if format.lower() == "json":
                await asyncio.to_thread(self.generate_json, transactions, family_id, temp_path)
            else:
                await asyncio.to_thread(self.generate_csv, transactions, temp_path)
                
            duration = time.time() - start_time
            logger.info(f"[3s Audit] Data export took {duration:.2f} seconds (format: {format}, count: {count}, family_id: {family_id})")
            
            return temp_path, count
        except Exception as e:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise e

    async def export_and_send(self, family_id: UUID, chat_id: int, format: str = "csv") -> None:
        """Exports data and sends it to the user via Telegram, ensuring temp file is deleted."""
        temp_path = None
        try:
            temp_path, count = await self.export_data(family_id, format)
            
            if count == 0:
                caption = "📊 Your transaction history is currently empty."
            else:
                caption = f"📊 Here is your exported transaction history (Total: {count} transactions)."
                
            await self.telegram_service.send_document(chat_id=chat_id, file_path=temp_path, caption=caption)
        except Exception as e:
            logger.error(f"Failed to export and send data: {e}")
            await self.telegram_service.send_message(chat_id=chat_id, text="Sorry, an error occurred while generating your export.")
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except Exception as e:
                    logger.error(f"Failed to cleanup temp file {temp_path}: {e}")
