import asyncio
import base64
import logging
import os
import tempfile
import time
import threading
from typing import Optional, Tuple, Union, BinaryIO, TYPE_CHECKING, Any
import httpx
if TYPE_CHECKING:
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
    _model: Optional[Any] = None
    _lock = threading.Lock()
    _transcribe_lock = threading.Lock()
    _failed_init = False

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super().__new__(cls, *args, **kwargs)
        return cls._instance

    def get_model(self) -> Any:
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
                        from faster_whisper import WhisperModel
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

        max_size = getattr(settings, "MAX_AUDIO_SIZE_BYTES", 3 * 1024 * 1024)

        # Support raw binary stream/file-like objects
        if audio_bytes is not None:
            if hasattr(audio_bytes, "read"):
                audio_bytes = audio_bytes.read()
            if len(audio_bytes) == 0:
                raise ValueError("audio_bytes cannot be empty")
            if len(audio_bytes) > max_size:
                raise InferenceError(f"Audio file is too large ({len(audio_bytes)} bytes > {max_size} bytes limit)")

        # 2. Download audio if URL is provided
        if audio_url is not None:
            try:
                client = get_http_client()
                response = await client.get(audio_url)
                response.raise_for_status()
                
                # Prevent DoS/OOM on huge files
                content_length = response.headers.get("Content-Length")
                if content_length and int(content_length) > max_size:
                    raise InferenceError(f"Audio file is too large ({content_length} bytes > {max_size} bytes limit)")
                    
                audio_bytes = response.content
                if len(audio_bytes) > max_size:
                    raise InferenceError(f"Audio file is too large ({len(audio_bytes)} bytes > {max_size} bytes limit)")
            except Exception as e:
                logger.error(f"Failed to download audio from {audio_url}: {e}", exc_info=True)
                if not isinstance(e, InferenceError):
                    raise InferenceError(f"Failed to download audio from {audio_url}: {e}")
                raise


            if not audio_bytes or len(audio_bytes) == 0:
                raise InferenceError(f"Downloaded audio from {audio_url} is empty")

        # 3. Cloud Audio Inference (Gemini Multimodal OR Groq/OpenAI Cloud Whisper)
        if settings.AI_API_KEY and settings.AI_API_KEY.strip():
            client = get_http_client()
            if settings.effective_ai_provider == "gemini":
                return await self._transcribe_gemini(client, audio_bytes, language=language, total_start_time=total_start_time)

            headers = {"Authorization": f"Bearer {settings.AI_API_KEY}"}
            files = {"file": ("audio.ogg", audio_bytes, "audio/ogg")}
            data = {
                "model": settings.AI_WHISPER_MODEL,
                "response_format": "json",
                "temperature": "0.0"
            }
            if language:
                data["language"] = language

            # Resilient retry loop for Groq Cloud Audio API (avoids fatal Render OOM on local fallback)
            max_whisper_attempts = 3
            for attempt in range(1, max_whisper_attempts + 1):
                try:
                    inference_start_time = time.perf_counter()
                    resp = await client.post(
                        f"{settings.AI_BASE_URL}/audio/transcriptions",
                        headers=headers,
                        files=files,
                        data=data,
                        timeout=30.0
                    )
                    if resp.status_code == 429 and attempt < max_whisper_attempts:
                        retry_after = 1.5
                        try:
                            retry_after = float(resp.headers.get("retry-after", 1.5))
                        except (ValueError, TypeError):
                            pass
                        logger.warning(
                            f"[Groq Whisper 429] Rate limited on /audio/transcriptions. Retrying in {retry_after:.2f}s "
                            f"(attempt {attempt}/{max_whisper_attempts})..."
                        )
                        await asyncio.sleep(retry_after)
                        continue

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
                except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.ConnectError) as e:
                    sanitized_err = sanitize_exception_message(e)
                    if attempt == max_whisper_attempts:
                        logger.error(f"[Cloud Whisper] All {max_whisper_attempts} attempts failed: {sanitized_err}")
                        # On cloud deployments, raise InferenceError instead of triggering fatal OOM in CTranslate2
                        raise InferenceError("Audio transcription service is momentarily busy. Please try again or send as text.") from e
                    backoff = 1.0 * attempt
                    logger.warning(f"[Cloud Whisper Retry] Attempt {attempt}/{max_whisper_attempts} failed: {sanitized_err}. Retrying in {backoff:.2f}s...")
                    await asyncio.sleep(backoff)
                except Exception as e:
                    sanitized_err = sanitize_exception_message(e)
                    logger.error(f"[Cloud Whisper] Unexpected error: {sanitized_err}")
                    raise InferenceError("Audio transcription encountered an unexpected error. Please try again or send as text.") from e

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

    async def _transcribe_gemini(
        self,
        client: httpx.AsyncClient,
        audio_bytes: bytes,
        language: Optional[str] = None,
        total_start_time: float = 0.0
    ) -> Tuple[str, str]:
        """
        Transcribes audio directly using Google Gemini's native multimodal audio understanding.
        Bypasses Whisper entirely, delivering high-speed bilingual transcription.
        """
        b64_audio = base64.b64encode(audio_bytes).decode("utf-8")
        model = settings.AI_WHISPER_MODEL or settings.AI_MODEL or "gemini-2.5-flash-lite"
        if not model.startswith("gemini") or model == "gemini-2.0-flash":
            model = "gemini-2.5-flash-lite"

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": settings.AI_API_KEY
        }
        lang_note = f" The speaker is speaking {language}." if language else ""
        prompt_text = (
            f"Transcribe the spoken audio verbatim in its original language (Spanish or English).{lang_note} "
            "Return ONLY the raw transcription text. "
            "Do NOT add explanations, timestamps, markdown formatting, introductory text, or quotation marks."
        )
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "inline_data": {
                                "mime_type": "audio/ogg",
                                "data": b64_audio
                            }
                        },
                        {
                            "text": prompt_text
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.0,
                "maxOutputTokens": 1000
            }
        }

        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                inference_start_time = time.perf_counter()
                resp = await client.post(url, headers=headers, json=payload, timeout=30.0)
                if resp.status_code == 429 and attempt < max_attempts:
                    retry_after = 1.5
                    try:
                        retry_after = float(resp.headers.get("retry-after", 1.5))
                    except (ValueError, TypeError):
                        pass
                    logger.warning(
                        f"[Gemini Audio 429] Rate limited. Retrying in {retry_after:.2f}s "
                        f"(attempt {attempt}/{max_attempts})..."
                    )
                    await asyncio.sleep(retry_after)
                    continue

                resp.raise_for_status()
                result_data = resp.json()
                text = ""
                candidates = result_data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        text = parts[0].get("text", "").strip()

                detected_lang = language or "auto"
                inference_duration = time.perf_counter() - inference_start_time
                total_duration = time.perf_counter() - total_start_time if total_start_time else inference_duration
                logger.info(
                    f"[3s Audit] Gemini Multimodal Audio transcription took {inference_duration:.4f} seconds "
                    f"| Total transaction took {total_duration:.4f} seconds (model: {model})"
                )
                return text, detected_lang
            except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.ConnectError) as e:
                sanitized_err = sanitize_exception_message(e)
                if attempt == max_attempts:
                    logger.error(f"[Gemini Audio] All {max_attempts} attempts failed: {sanitized_err}")
                    raise InferenceError("Audio transcription service is momentarily busy. Please try again or send as text.") from e
                backoff = 1.0 * attempt
                logger.warning(f"[Gemini Audio Retry] Attempt {attempt}/{max_attempts} failed: {sanitized_err}. Retrying in {backoff:.2f}s...")
                await asyncio.sleep(backoff)
            except Exception as e:
                sanitized_err = sanitize_exception_message(e)
                logger.error(f"[Gemini Audio] Unexpected error: {sanitized_err}")
                raise InferenceError("Audio transcription encountered an unexpected error. Please try again or send as text.") from e
