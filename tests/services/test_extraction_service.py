import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from src.services.extraction_service import ExtractionService, ExtractionResult, ExtractionError
import ollama
from src.core.config import settings

@pytest.fixture
def mock_ollama_client():
    with patch("src.services.extraction_service.ollama.AsyncClient") as mock_client_cls:
        mock_instance = AsyncMock()
        mock_client_cls.return_value = mock_instance
        yield mock_instance

@pytest.fixture
def service(mock_ollama_client):
    # Reset singleton for testing
    ExtractionService._instance = None
    return ExtractionService()

@pytest.mark.anyio
async def test_extract_happy_path(service, mock_ollama_client):
    # Mocking the chat response
    mock_response = MagicMock()
    mock_response.message.content = '{"amount": 15.0, "category": "Food/Drink", "concept": "Starbucks", "currency": "USD"}'
    mock_ollama_client.chat.return_value = mock_response

    result = await service.extract("I spent $15 at Starbucks")

    assert isinstance(result, ExtractionResult)
    assert result.amount == 15.0
    assert result.category == "Food/Drink"
    assert result.concept == "Starbucks"
    assert result.currency == "USD"

    # Verify client chat was called correctly
    mock_ollama_client.chat.assert_called_once()
    kwargs = mock_ollama_client.chat.call_args.kwargs
    assert kwargs["model"] == settings.OLLAMA_MODEL
    assert "format" in kwargs

@pytest.mark.anyio
async def test_extract_validation_failures(service):
    # Empty inputs raise ValueError
    with pytest.raises(ValueError, match="Input text is empty"):
        await service.extract("")
    
    with pytest.raises(ValueError, match="Input text is empty"):
        await service.extract("   ")

@pytest.mark.anyio
async def test_extract_pydantic_amount_bounds():
    # Transaction amount must be greater than 0
    with pytest.raises(ValueError, match="Input should be greater than 0"):
        ExtractionResult(amount=0.0, category="Food/Drink", concept="Starbucks")
    with pytest.raises(ValueError, match="Input should be greater than 0"):
        ExtractionResult(amount=-1.0, category="Food/Drink", concept="Starbucks")

@pytest.mark.anyio
async def test_extract_category_normalization(service, mock_ollama_client):
    mock_response = MagicMock()
    # Test lowercase standard categories map to their correctly cased equivalents
    mock_response.message.content = '{"amount": 10.0, "category": "shopping", "concept": "Shoes", "currency": "USD"}'
    mock_ollama_client.chat.return_value = mock_response
    result = await service.extract("Bought shoes")
    assert result.category == "Shopping"

    # Test unknown category maps to "Other"
    mock_response.message.content = '{"amount": 5.0, "category": "Crypto", "concept": "Bitcoin", "currency": "USD"}'
    mock_ollama_client.chat.return_value = mock_response
    result = await service.extract("Bought bitcoin")
    assert result.category == "Other"

@pytest.mark.anyio
async def test_extract_currency_normalization(service, mock_ollama_client):
    mock_response = MagicMock()
    mock_response.message.content = '{"amount": 10.0, "category": "Food/Drink", "concept": "Lunch", "currency": "euros"}'
    mock_ollama_client.chat.return_value = mock_response

    result = await service.extract("10 euros for lunch")
    assert result.amount == 10.0
    assert result.currency == "EUR"

    # Test symbol mapping
    mock_response.message.content = '{"amount": 10.0, "category": "Food/Drink", "concept": "Lunch", "currency": "€"}'
    mock_ollama_client.chat.return_value = mock_response
    result = await service.extract("10 euros for lunch")
    assert result.currency == "EUR"

@pytest.mark.anyio
async def test_extract_timeout(service, mock_ollama_client):
    # Mocking call to hang and raise TimeoutError
    mock_ollama_client.chat.side_effect = asyncio.TimeoutError()

    # The service will catch the timeout and attempt fallback on the text
    result = await service.extract("I paid $15.50 for lunch")
    assert result.amount == 15.50
    assert result.category == "Other"
    assert result.currency == "USD"

@pytest.mark.anyio
async def test_extract_network_error(service, mock_ollama_client):
    mock_ollama_client.chat.side_effect = ollama.RequestError("Connection failed")

    result = await service.extract("100 euros for shopping")
    assert result.amount == 100.0
    assert result.currency == "EUR"

@pytest.mark.anyio
async def test_extract_invalid_json(service, mock_ollama_client):
    mock_response = MagicMock()
    mock_response.message.content = 'invalid json'
    mock_ollama_client.chat.return_value = mock_response

    result = await service.extract("Spent £50 on a gift")
    assert result.amount == 50.0
    assert result.currency == "GBP"

@pytest.mark.anyio
async def test_extract_empty_response(service, mock_ollama_client):
    mock_response = MagicMock()
    mock_response.message.content = ''
    mock_ollama_client.chat.return_value = mock_response

    with pytest.raises(ExtractionError, match="Received empty response"):
        await service.extract("test")
