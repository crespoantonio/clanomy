import pytest
import asyncio
from datetime import datetime, timezone
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
    assert result.type == "expense"
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

@pytest.mark.anyio
async def test_extract_transaction_date(service, mock_ollama_client):
    mock_response = MagicMock()
    # Explicit past date
    mock_response.message.content = '{"amount": 10.0, "category": "Food/Drink", "concept": "Lunch", "currency": "USD", "transaction_date": "2026-08-10"}'
    mock_ollama_client.chat.return_value = mock_response

    result = await service.extract("Spent 10 for lunch on August 10th")
    assert result.transaction_date == "2026-08-10"
    
    dt = result.to_datetime()
    assert dt.year == 2026
    assert dt.month == 8
    assert dt.day == 10
    assert dt.hour == 12

@pytest.mark.anyio
async def test_extract_transaction_date_fallback():
    # When transaction_date is None, to_datetime should use reference_time
    result = ExtractionResult(amount=10.0, category="Food/Drink", concept="Lunch")
    ref_time = datetime(2026, 8, 18, 12, 0, 0, tzinfo=timezone.utc)
    
    dt = result.to_datetime(reference_time=ref_time)
    assert dt == ref_time

@pytest.mark.anyio
async def test_extract_income_happy_path(service, mock_ollama_client):
    mock_response = MagicMock()
    mock_response.message.content = '{"type": "income", "amount": 3500.0, "category": "Salary", "concept": "Acme Corp", "currency": "USD"}'
    mock_ollama_client.chat.return_value = mock_response

    result = await service.extract("Got my salary of 3500 dollars from Acme Corp")

    assert isinstance(result, ExtractionResult)
    assert result.type == "income"
    assert result.amount == 3500.0
    assert result.category == "Salary"
    assert result.concept == "Acme Corp"
    assert result.currency == "USD"

@pytest.mark.anyio
async def test_extract_default_type_is_expense():
    # When type is omitted or invalid, it defaults to 'expense'
    result = ExtractionResult(amount=25.0, category="Shopping", concept="Book")
    assert result.type == "expense"

    # Type normalization case-insensitivity
    result_upper = ExtractionResult(type="INCOME", amount=50.0, category="Bonus", concept="Work")
    assert result_upper.type == "income"

    result_invalid = ExtractionResult(type="unknown_intent", amount=50.0, category="Other", concept="Work")
    assert result_invalid.type == "expense"

@pytest.mark.anyio
async def test_extract_income_category_normalization():
    # Test income categories normalization
    for cat_input, expected in [
        ("salary", "Salary"),
        ("SALARY", "Salary"),
        ("bonus", "Bonus"),
        ("freelance", "Freelance"),
        ("investment", "Investment"),
        ("gift", "Gift"),
        ("sale", "Sale"),
        ("dividend", "Investment"),
        ("wage", "Salary"),
        ("wages", "Salary"),
    ]:
        result = ExtractionResult(type="income", amount=100.0, category=cat_input, concept="Earned money")
        assert result.category == expected

@pytest.mark.anyio
@pytest.mark.parametrize("prompt,expected_type,expected_amount,expected_currency,expected_cat,expected_concept", [
    ("Got my salary of 3200 dollars from Acme Corp", "income", 3200.0, "USD", "Salary", "Acme Corp"),
    ("Sold my old bike for 150 euros", "income", 150.0, "EUR", "Sale", "old bike"),
    ("Received freelance payment of £800 from Client X", "income", 800.0, "GBP", "Freelance", "Client X"),
    ("Earned $500 bonus from work", "income", 500.0, "USD", "Bonus", "work"),
    ("Received $200 dividend from Apple", "income", 200.0, "USD", "Investment", "Apple"),
    ("Invoice paid $1200 for web design", "income", 1200.0, "USD", "Freelance", "web design"),
    ("Got paid $1000 for tutoring", "income", 1000.0, "USD", "Salary", "tutoring"),
    ("Spent $15 at Starbucks", "expense", 15.0, "USD", "Food/Drink", "Starbucks"),
    ("Bought lunch for 12 EUR", "expense", 12.0, "EUR", "Food/Drink", "lunch"),
    ("Paid for rent 1200 dollars", "expense", 1200.0, "USD", "Rent/Bills", "rent"),
    ("Coffee for 4.50", "expense", 4.50, "USD", "Food/Drink", "coffee"),
    ("50 dollars for project", "expense", 50.0, "USD", "Other", "project"),
])
async def test_extract_dual_intent_benchmark_dataset(service, mock_ollama_client, prompt, expected_type, expected_amount, expected_currency, expected_cat, expected_concept):
    mock_response = MagicMock()
    mock_response.message.content = f'{{"type": "{expected_type}", "amount": {expected_amount}, "category": "{expected_cat}", "concept": "{expected_concept}", "currency": "{expected_currency}"}}'
    mock_ollama_client.chat.return_value = mock_response

    result = await service.extract(prompt)
    assert result.type == expected_type
    assert result.amount == expected_amount
    assert result.currency == expected_currency
    assert result.category == expected_cat
    assert result.concept == expected_concept
    
    # Verify the system prompt contains the markdown prohibition rule
    kwargs = mock_ollama_client.chat.call_args.kwargs
    system_prompt = next(msg["content"] for msg in kwargs["messages"] if msg["role"] == "system")
    assert "Do not include any markdown formatting" in system_prompt

@pytest.mark.anyio
async def test_fallback_regex_extract_dual_intent(service, mock_ollama_client):
    # Simulate network error to trigger regex fallback
    mock_ollama_client.chat.side_effect = ollama.RequestError("Connection failed")

    # Income phrases fallback
    res1 = await service.extract("Got paid salary $2500 from TechCorp")
    assert res1.type == "income"
    assert res1.amount == 2500.0
    assert res1.currency == "USD"
    assert res1.category == "Salary"

    res2 = await service.extract("Sold old laptop for 400 euros")
    assert res2.type == "income"
    assert res2.amount == 400.0
    assert res2.currency == "EUR"
    assert res2.category == "Sale"

    res3 = await service.extract("Received bonus £500 from company")
    assert res3.type == "income"
    assert res3.amount == 500.0
    assert res3.currency == "GBP"
    assert res3.category == "Bonus"

    res4 = await service.extract("Earned $300 dividend from stocks")
    assert res4.type == "income"
    assert res4.amount == 300.0
    assert res4.category == "Investment"

    res5 = await service.extract("Freelance payment 800 USD for app")
    assert res5.type == "income"
    assert res5.amount == 800.0
    assert res5.category == "Freelance"

    # Expense phrases fallback
    res6 = await service.extract("Spent 45 euros for groceries")
    assert res6.type == "expense"
    assert res6.amount == 45.0
    assert res6.currency == "EUR"

    res7 = await service.extract("Paid 1200 dollars for rent")
    assert res7.type == "expense"
    assert res7.amount == 1200.0
    assert res7.currency == "USD"

    # Ambiguous phrase fallback defaults to expense
    res8 = await service.extract("50 dollars for project")
    assert res8.type == "expense"
    assert res8.amount == 50.0
    assert res8.currency == "USD"

@pytest.mark.anyio
async def test_extract_via_cloud_ai_success(monkeypatch):
    monkeypatch.setattr(settings, "AI_API_KEY", "gsk_test_12345")
    ExtractionService._instance = None
    service = ExtractionService()
    
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": '{"type": "expense", "amount": 25.5, "category": "Food/Drink", "concept": "Dinner", "currency": "USD"}'
                }
            }
        ]
    }
    
    with patch("src.core.http_client.HTTPClientManager.client") as mock_client:
        mock_client.post = AsyncMock(return_value=mock_resp)
        result = await service.extract("Dinner $25.50")
        assert result.amount == 25.5
        assert result.category == "Food/Drink"
        assert result.concept == "Dinner"
        assert result.type == "expense"

@pytest.mark.anyio
async def test_extract_currency_ambiguous_pesos_and_explicit_latam(service, mock_ollama_client, monkeypatch):
    # Explicit Mexican Pesos
    mock_resp = MagicMock()
    mock_resp.message.content = '{"type": "expense", "amount": 500.0, "category": "Food/Drink", "concept": "Helado", "currency": "pesos mexicanos"}'
    mock_ollama_client.chat.return_value = mock_resp
    res_mxn = await service.extract("Gasté 500 pesos mexicanos en helado")
    assert res_mxn.currency == "MXN"

    # Explicit Argentine Pesos
    mock_resp.message.content = '{"type": "expense", "amount": 1500.0, "category": "Food/Drink", "concept": "Cena", "currency": "pesos argentinos"}'
    mock_ollama_client.chat.return_value = mock_resp
    res_ars = await service.extract("Cena 1500 pesos argentinos")
    assert res_ars.currency == "ARS"

    # Ambiguous pesos defaults to DEFAULT_CURRENCY (e.g. ARS or USD)
    monkeypatch.setattr(settings, "DEFAULT_CURRENCY", "ARS")
    mock_resp.message.content = '{"type": "expense", "amount": 300.0, "category": "Food/Drink", "concept": "Café", "currency": "pesos"}'
    mock_ollama_client.chat.return_value = mock_resp
    res_default = await service.extract("300 pesos café")
    assert res_default.currency == "ARS"



