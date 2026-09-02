import io
import pytest
import os
from unittest.mock import MagicMock, patch, AsyncMock
import httpx
from src.core.config import settings
from src.services.whisper_service import WhisperService, InferenceError

@pytest.fixture(autouse=True)
def reset_whisper_service():
    # Reset singleton state before and after each test
    WhisperService._instance = None
    WhisperService._model = None
    WhisperService._failed_init = False
    yield
    WhisperService._instance = None
    WhisperService._model = None
    WhisperService._failed_init = False

@pytest.fixture
def mock_whisper_model():
    with patch("faster_whisper.WhisperModel") as mock_model_class:
        mock_model_instance = MagicMock()
        mock_model_class.return_value = mock_model_instance
        
        # Mock transcribe method return value: (segments, info)
        mock_segment = MagicMock()
        mock_segment.text = "Hello, this is a test transcription."
        mock_info = MagicMock()
        mock_info.language = "en"
        
        mock_model_instance.transcribe.return_value = ([mock_segment], mock_info)
        yield mock_model_class, mock_model_instance

def test_whisper_service_lazy_init(mock_whisper_model):
    mock_class, mock_inst = mock_whisper_model
    
    service = WhisperService()
    
    # Model should not be initialized immediately on construction
    mock_class.assert_not_called()
    
    # Model initialized on first access
    model = service.get_model()
    mock_class.assert_called_once()
    assert model == mock_inst
    
    # Second access returns the same instance without calling constructor again
    model2 = service.get_model()
    mock_class.assert_called_once()
    assert model2 == mock_inst

@pytest.mark.anyio
async def test_transcribe_validation():
    service = WhisperService()
    
    # Neither audio_url nor audio_bytes provided
    with pytest.raises(ValueError, match="Either audio_url or audio_bytes must be provided"):
        await service.transcribe()
        
    # Empty audio_bytes
    with pytest.raises(ValueError, match="audio_bytes cannot be empty"):
        await service.transcribe(audio_bytes=b"")

    # Conflicting inputs
    with pytest.raises(ValueError, match="Both audio_url and audio_bytes cannot be provided simultaneously"):
        await service.transcribe(audio_url="http://example.com/audio.ogg", audio_bytes=b"some bytes")

@pytest.mark.anyio
async def test_transcribe_from_bytes_success(mock_whisper_model):
    _, mock_inst = mock_whisper_model
    service = WhisperService()
    audio_data = b"fake-audio-content"
    
    # We patch NamedTemporaryFile to inspect its usage and verify cleanup
    with patch("tempfile.NamedTemporaryFile") as mock_temp_file_class:
        mock_temp_file = MagicMock()
        mock_temp_file.name = "fake_temp_file.ogg"
        mock_temp_file_class.return_value.__enter__.return_value = mock_temp_file
        
        text, lang = await service.transcribe(audio_bytes=audio_data)
        
        assert text == "Hello, this is a test transcription."
        assert lang == "en"
        
        # Verify model's transcribe was called with the temp file name
        mock_inst.transcribe.assert_called_once()
        args, kwargs = mock_inst.transcribe.call_args
        assert args[0] == "fake_temp_file.ogg"
        
        # Verify writing audio bytes
        mock_temp_file.write.assert_called_once_with(audio_data)
        mock_temp_file.flush.assert_called_once()

@pytest.mark.anyio
async def test_transcribe_from_stream_success(mock_whisper_model):
    _, mock_inst = mock_whisper_model
    service = WhisperService()
    audio_data = b"stream-audio-content"
    audio_stream = io.BytesIO(audio_data)
    
    with patch("tempfile.NamedTemporaryFile") as mock_temp_file_class:
        mock_temp_file = MagicMock()
        mock_temp_file.name = "fake_temp_file_stream.ogg"
        mock_temp_file_class.return_value.__enter__.return_value = mock_temp_file
        
        text, lang = await service.transcribe(audio_bytes=audio_stream)
        
        assert text == "Hello, this is a test transcription."
        assert lang == "en"
        
        # Verify writing stream contents
        mock_temp_file.write.assert_called_once_with(audio_data)

@pytest.mark.anyio
async def test_transcribe_from_url_success(mock_whisper_model):
    _, mock_inst = mock_whisper_model
    service = WhisperService()
    audio_url = "http://example.com/audio.ogg"
    audio_data = b"downloaded-audio-content"
    
    # Mock httpx response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = audio_data
    mock_response.headers = {}
    mock_response.raise_for_status = MagicMock()
    
    # We patch NamedTemporaryFile and httpx AsyncClient
    with patch("tempfile.NamedTemporaryFile") as mock_temp_file_class, \
         patch("httpx.AsyncClient.get") as mock_get:
        
        mock_get.return_value = mock_response
        mock_temp_file = MagicMock()
        mock_temp_file.name = "fake_temp_file_url.ogg"
        mock_temp_file_class.return_value.__enter__.return_value = mock_temp_file
        
        text, lang = await service.transcribe(audio_url=audio_url)
        
        assert text == "Hello, this is a test transcription."
        assert lang == "en"
        
        # Verify URL get called
        mock_get.assert_called_once_with(audio_url)
        mock_response.raise_for_status.assert_called_once()
        
        # Verify writing downloaded content
        mock_temp_file.write.assert_called_once_with(audio_data)
        
        # Verify model's transcribe was called
        mock_inst.transcribe.assert_called_once()

@pytest.mark.anyio
async def test_transcribe_download_too_large():
    service = WhisperService()
    audio_url = "http://example.com/huge.ogg"
    
    # Mock response with large Content-Length
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"Content-Length": str(25 * 1024 * 1024)}  # 25MB
    mock_response.raise_for_status = MagicMock()
    
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = mock_response
        with pytest.raises(InferenceError, match="Audio file is too large"):
            await service.transcribe(audio_url=audio_url)

@pytest.mark.anyio
async def test_transcribe_download_failure():
    service = WhisperService()
    audio_url = "http://example.com/audio.ogg"
    
    # Mock httpx download raising error
    with patch("httpx.AsyncClient.get", side_effect=httpx.HTTPStatusError("Mock error", request=MagicMock(), response=MagicMock())):
        with pytest.raises(InferenceError, match="Failed to download audio from"):
            await service.transcribe(audio_url=audio_url)

@pytest.mark.anyio
async def test_transcribe_model_failure(mock_whisper_model):
    _, mock_inst = mock_whisper_model
    service = WhisperService()
    
    # Make model transcribe raise exception
    mock_inst.transcribe.side_effect = Exception("Whisper failed")
    
    with pytest.raises(InferenceError, match="Transcription failed: Whisper failed"):
        await service.transcribe(audio_bytes=b"fake-audio-bytes")

@pytest.mark.anyio
async def test_transcribe_model_failed_init_caching():
    service = WhisperService()
    
    with patch("faster_whisper.WhisperModel", side_effect=Exception("Failed to load weights")) as mock_class:
        # First call fails
        with pytest.raises(InferenceError, match="Failed to load weights"):
            await service.transcribe(audio_bytes=b"fake-bytes")
        
        # Verify WhisperModel constructor was called once
        mock_class.assert_called_once()
        
        # Second call should immediately raise InferenceError without calling constructor again
        with pytest.raises(InferenceError, match="WhisperModel initialization previously failed"):
            await service.transcribe(audio_bytes=b"fake-bytes")
        mock_class.assert_called_once()

@pytest.mark.anyio
async def test_transcribe_via_cloud_whisper(monkeypatch):
    monkeypatch.setattr(settings, "AI_API_KEY", "gsk_test_groq_key")
    WhisperService._instance = None
    service = WhisperService()
    
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"text": "Coffee for four dollars"}
    
    with patch("src.core.http_client.HTTPClientManager.client") as mock_client:
        mock_client.post = AsyncMock(return_value=mock_resp)
        text, lang = await service.transcribe(audio_bytes=b"fake_audio_stream")
        assert text == "Coffee for four dollars"
        assert lang == "en"

@pytest.mark.anyio
async def test_transcribe_cloud_whisper_429_retry_success(monkeypatch):
    monkeypatch.setattr(settings, "AI_API_KEY", "gsk_test_groq_key")
    WhisperService._instance = None
    service = WhisperService()

    resp_429 = MagicMock()
    resp_429.status_code = 429
    resp_429.headers = {"retry-after": "0.01"}

    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.json.return_value = {"text": "Lunch for twelve euros"}

    with patch("src.core.http_client.HTTPClientManager.client") as mock_client, \
         patch.object(service, "get_model") as mock_get_model:
        mock_client.post = AsyncMock(side_effect=[resp_429, resp_200])
        text, lang = await service.transcribe(audio_bytes=b"fake_audio_stream")
        assert text == "Lunch for twelve euros"
        assert lang == "en"
        assert mock_client.post.call_count == 2
        mock_get_model.assert_not_called()

@pytest.mark.anyio
async def test_transcribe_cloud_whisper_exhaustion_raises_inference_error_no_local_fallback(monkeypatch):
    monkeypatch.setattr(settings, "AI_API_KEY", "gsk_test_groq_key")
    WhisperService._instance = None
    service = WhisperService()

    resp_429 = MagicMock()
    resp_429.status_code = 429
    resp_429.headers = {"retry-after": "0.01"}
    resp_429.raise_for_status.side_effect = httpx.HTTPStatusError("429 Rate Limit", request=MagicMock(), response=resp_429)

    with patch("src.core.http_client.HTTPClientManager.client") as mock_client, \
         patch.object(service, "get_model") as mock_get_model:
        mock_client.post = AsyncMock(return_value=resp_429)
        with pytest.raises(InferenceError, match="Audio transcription service is momentarily busy"):
            await service.transcribe(audio_bytes=b"fake_audio_stream")
        assert mock_client.post.call_count == 3

@pytest.mark.anyio
async def test_transcribe_rejects_audio_bytes_exceeding_max_audio_size():
    service = WhisperService()
    oversized_bytes = b"x" * (settings.MAX_AUDIO_SIZE_BYTES + 1024)
    with pytest.raises(InferenceError, match="Audio file is too large"):
        await service.transcribe(audio_bytes=oversized_bytes)



