import time
import logging
import httpx
import datetime
import asyncio
from typing import Optional
from uuid import UUID
from sqlmodel import Session
from src.core.config import settings
from src.services.whisper_service import WhisperService
from src.services.extraction_service import ExtractionService
from src.db.session import engine
from src.db.models import User, Transaction
from src.core.encryption import EncryptionService
from src.services.telegram_service import TelegramService

logger = logging.getLogger(__name__)

class AIOrchestrator:
    def __init__(self):
        self.encryption_service = EncryptionService()

    def _persist_transaction(self, user_uuid: UUID, amount: str, concept: str, category: str) -> None:
        """
        Synchronous helper to write the transaction to the database.
        Runs inside a separate thread via asyncio.to_thread to keep the event loop unblocked.
        """
        with Session(engine) as session:
            try:
                user = session.get(User, user_uuid)
                if not user:
                    raise ValueError(f"User with id {user_uuid} not found.")
                if not user.family_id:
                    raise ValueError(f"User with id {user_uuid} is not associated with any family.")
                    
                transaction = Transaction(
                    user_id=user_uuid,
                    family_id=user.family_id,
                    amount=amount,
                    concept=concept,
                    category=category,
                    timestamp=datetime.datetime.now(datetime.timezone.utc)
                )
                session.add(transaction)
                session.commit()
            except Exception as e:
                session.rollback()
                raise e

    async def orchestrate(self, user_id: str, text: Optional[str], audio_file_id: Optional[str], chat_id: int):
        start_time = time.time()
        status = "success"
        response_text = ""
        extracted_data = None
        
        try:
            # Parse user_id once and validate UUID format
            try:
                user_uuid = UUID(user_id)
            except ValueError:
                raise ValueError(f"Invalid user_id format: {user_id}")

            # 1. Process Audio if provided
            if audio_file_id:
                try:
                    telegram_service = TelegramService()
                    audio_url = await telegram_service.get_file_url(audio_file_id)
                    if not audio_url:
                        raise ValueError(f"Could not resolve Telegram file_id: {audio_file_id}")
                        
                    whisper_service = WhisperService()
                    text, _ = await whisper_service.transcribe(audio_url=audio_url)
                    if not text:
                        raise ValueError("Transcription returned empty text.")
                except Exception as e:
                    logger.error(f"Transcription failed: {e}")
                    status = "error"
                    response_text = "I couldn't understand the audio. Could you please type it or try again?"
                    
            # 2. Extract Data if we have text and no previous error
            if text and status == "success":
                try:
                    extraction_service = ExtractionService()
                    result = await extraction_service.extract(text=text)
                    extracted_data = result.model_dump()
                    
                    # Construct success message
                    response_text = f"Saved {result.amount} {result.currency} for '{result.concept}' under category '{result.category}'."
                except Exception as e:
                    logger.error(f"Extraction failed: {e}")
                    status = "error"
                    response_text = "I couldn't extract the details from your message. Please make sure to include the amount and what it was for."
                    
                if status == "success":
                    try:
                        # Persist Transaction
                        encrypted_amount = self.encryption_service.encrypt(f"{result.amount} {result.currency}")
                        encrypted_concept = self.encryption_service.encrypt(result.concept)
                        
                        await asyncio.to_thread(
                            self._persist_transaction,
                            user_uuid=user_uuid,
                            amount=encrypted_amount,
                            concept=encrypted_concept,
                            category=result.category
                        )
                    except Exception as e:
                        logger.error(f"Persistence failed: {e}")
                        status = "error"
                        response_text = "Failed to save transaction. Please try again later."
            elif not text and status == "success":
                status = "error"
                response_text = "No message or audio was provided."
                
        except Exception as e:
            logger.error(f"Unexpected error in orchestrator: {e}")
            status = "error"
            response_text = "An unexpected error occurred while processing your request."
            
        # 3. Direct Reply via Telegram API
        try:
            telegram_service = TelegramService()
            await telegram_service.send_message(chat_id=chat_id, text=response_text)
        except Exception as e:
            logger.error(f"Failed to send direct reply to Telegram: {e}")
            
        # 4. Log 3s Audit
        duration = time.time() - start_time
        logger.info(f"[3s Audit] Total pipeline orchestration took {duration:.2f} seconds (user_id: {user_id}, text: '{text}')")
