import asyncio
import logging
import os
import tempfile
import time
import threading
from typing import Optional, Tuple, Union, BinaryIO
import httpx
from faster_whisper import WhisperModel
from src.core.config import settings
from src.core.http_client import get_http_client
from src.core.security import sanitize_exception_message

logger = logging.getLogger("clanomy.whisper")

class InferenceError(Exception):
    """Raised when audio transcription or inference fails."""
    pass

class WhisperService:
    _instance = None
    _model: Optional[WhisperModel] = None
    _lock = threading.Lock()
    _transcribe_lock = threading.Lock()
    _failed_init = False

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super().__new__(cls, *args, **kwargs)
        return cls._instance

    def get_model(self) -> WhisperModel:
        """
        Lazily loads and returns the WhisperModel instance in a thread-safe manner.
        """
        if self._failed_init:
            raise InferenceError("WhisperModel initialization previously failed and will not be retried.")
            
        if self._model is None:
            with self._lock:
                if self._failed_init:
                    raise InferenceError("WhisperModel initialization previously failed and will not be retried.")
                if self._model is None:
                    logger.info(
                        f"Initializing WhisperModel (model: {settings.WHISPER_MODEL_SIZE}, "
                        f"device: {settings.WHISPER_DEVICE}, compute_type: {settings.WHISPER_COMPUTE_TYPE})"
                    )
                    try:
                        self._model = WhisperModel(
                            model_size_or_path=settings.WHISPER_MODEL_SIZE,
                            device=settings.WHISPER_DEVICE,
                            compute_type=settings.WHISPER_COMPUTE_TYPE
                        )
                    except Exception as e:
                        self._failed_init = True
                        logger.error(f"Failed to initialize WhisperModel: {e}", exc_info=True)
                        raise InferenceError(f"Model initialization failed: {e}")
        return self._model

    async def transcribe(
        self,
        audio_url: Optional[str] = None,
        audio_bytes: Optional[Union[bytes, BinaryIO]] = None,
        language: Optional[str] = None
    ) -> Tuple[str, str]:
        """
        Transcribes audio from a URL or binary bytes/stream to text.
        Returns a tuple of (transcribed_text, detected_language).
        
        This method runs the CPU-bound transcription in a thread pool using asyncio.to_thread
        and logs performance metrics for the '3s Audit'.
        """
        # Start total transaction time measurement
        total_start_time = time.perf_counter()

        # 1. Validation
        if audio_url is None and audio_bytes is None:
            raise ValueError("Either audio_url or audio_bytes must be provided")
            
        if audio_url is not None and audio_bytes is not None:
            raise ValueError("Both audio_url and audio_bytes cannot be provided simultaneously")

        # Support raw binary stream/file-like objects
        if audio_bytes is not None:
            if hasattr(audio_bytes, "read"):
                audio_bytes = audio_bytes.read()
            if len(audio_bytes) == 0:
                raise ValueError("audio_bytes cannot be empty")

        # 2. Download audio if URL is provided
        if audio_url is not None:
            try:
                client = get_http_client()
                response = await client.get(audio_url)
                response.raise_for_status()
                
                # Prevent DoS/OOM on huge files
                MAX_AUDIO_SIZE = 20 * 1024 * 1024  # 20MB limit
                content_length = response.headers.get("Content-Length")
                if content_length and int(content_length) > MAX_AUDIO_SIZE:
                    raise InferenceError(f"Audio file is too large ({content_length} bytes)")
                    
                audio_bytes = response.content
                if len(audio_bytes) > MAX_AUDIO_SIZE:
                    raise InferenceError(f"Audio file is too large ({len(audio_bytes)} bytes)")
            except Exception as e:
                logger.error(f"Failed to download audio from {audio_url}: {e}", exc_info=True)
                if not isinstance(e, InferenceError):
                    raise InferenceError(f"Failed to download audio from {audio_url}: {e}")
                raise

            if not audio_bytes or len(audio_bytes) == 0:
                raise InferenceError(f"Downloaded audio from {audio_url} is empty")

        # 3. Cloud Whisper Inference (if AI_API_KEY is configured)
        if settings.AI_API_KEY and settings.AI_API_KEY.strip():
            try:
                inference_start_time = time.perf_counter()
                client = get_http_client()
                headers = {"Authorization": f"Bearer {settings.AI_API_KEY}"}
                files = {"file": ("audio.ogg", audio_bytes, "audio/ogg")}
                data = {
                    "model": settings.AI_WHISPER_MODEL,
                    "response_format": "json",
                    "temperature": "0.0"
                }
                if language:
                    data["language"] = language
                
                resp = await client.post(
                    f"{settings.AI_BASE_URL}/audio/transcriptions",
                    headers=headers,
                    files=files,
                    data=data,
                    timeout=30.0
                )
                resp.raise_for_status()
                result_data = resp.json()
                text = (result_data.get("text") or "").strip()
                detected_lang = language or "en"
                inference_duration = time.perf_counter() - inference_start_time
                total_duration = time.perf_counter() - total_start_time
                logger.info(
                    f"[3s Audit] Cloud Whisper transcription took {inference_duration:.4f} seconds "
                    f"| Total transaction took {total_duration:.4f} seconds (model: {settings.AI_WHISPER_MODEL})"
                )
                return text, detected_lang
            except Exception as e:
                sanitized_err = sanitize_exception_message(e)
                logger.warning(
                    f"[Cloud Whisper] Transcription failed: {sanitized_err}. "
                    "Falling back to local Faster-Whisper."
                )

        # 4. Local faster-whisper Fallback (Write audio to temporary file)
        # On Windows, we must close the file before passing the path to WhisperModel
        # to prevent file sharing/locking violations.
        temp_file_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as temp_file:
                temp_file_path = temp_file.name
                temp_file.write(audio_bytes)
                temp_file.flush()

            # 4. Run CPU-bound model loading and transcription in a separate thread pool
            # to keep lazy loading completely non-blocking to the main event loop
            inference_start_time = time.perf_counter()

            def _execute_transcribe():
                # We load the model synchronously inside the thread pool to avoid blocking the main loop
                model = self.get_model()
                # We consume the generator within the thread so the processing happens synchronously
                with self._transcribe_lock:
                    segments, info = model.transcribe(
                        temp_file_path, 
                        beam_size=settings.WHISPER_BEAM_SIZE,
                        temperature=settings.WHISPER_TEMPERATURE,
                        vad_filter=settings.WHISPER_VAD_FILTER,
                        language=language
                    )
                    text = " ".join([segment.text for segment in segments]).strip()
                return text, info.language

            if not hasattr(self, '_sem') or getattr(self, '_sem') is None:
                self._sem = asyncio.Semaphore(settings.WHISPER_MAX_CONCURRENT)
                
            async with getattr(self, '_sem'):
                text, detected_lang = await asyncio.to_thread(_execute_transcribe)

            # End time measurements
            inference_duration = time.perf_counter() - inference_start_time
            total_duration = time.perf_counter() - total_start_time
            
            # Log 3s Audit performance metrics separately
            logger.info(
                f"[3s Audit] Whisper transcription took {inference_duration:.4f} seconds (inference only) "
                f"| Total transaction took {total_duration:.4f} seconds (including download/load) "
                f"(model: {settings.WHISPER_MODEL_SIZE}, device: {settings.WHISPER_DEVICE}, "
                f"detected_language: {detected_lang})"
            )
            
            return text, detected_lang

        except Exception as e:
            logger.error(f"Error during transcription: {e}", exc_info=True)
            if not isinstance(e, InferenceError):
                raise InferenceError(f"Transcription failed: {e}")
            raise
        finally:
            # 5. Clean up temporary file
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except Exception as e:
                    logger.warning(f"Failed to clean up temporary file {temp_file_path}: {e}")
