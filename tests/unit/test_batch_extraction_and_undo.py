import asyncio
from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from sqlmodel import Session, SQLModel, create_engine, select
from sqlalchemy.pool import StaticPool

from src.core.encryption import EncryptionService
from src.db.models import User, Family, Transaction
from src.services.extraction.models import PayloadTruncatedError, ParsedItem, UnifiedResult
from src.services.handlers.batch_tracker import BatchTracker
from src.services.handlers.transaction_handler import handle_transaction_undo
from src.services.query.models import ParsedQueryIntent
from src.services.ai_orchestrator import AIOrchestrator
from src.core.llm.providers.openai_provider import OpenAICompatibleProvider


@pytest.fixture
def db_setup(monkeypatch):
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    SQLModel.metadata.create_all(test_engine)

    monkeypatch.setattr("src.db.session.engine", test_engine)
    monkeypatch.setattr("src.services.ai_orchestrator.engine", test_engine)
    monkeypatch.setattr("src.services.handlers.transaction_handler.engine", test_engine)
    monkeypatch.setattr("src.services.handlers.notion_handler.engine", test_engine)

    encryption = EncryptionService()
    family_id = uuid4()
    user_id = uuid4()

    with Session(test_engine) as session:
        family = Family(id=family_id, name="Test Family", plan_type="free")
        user = User(id=user_id, telegram_id=987654321, username="testuser", full_name="Test User", family_id=family_id)
        session.add(family)
        session.add(user)
        session.commit()

    return {"family_id": family_id, "user_id": user_id, "encryption": encryption, "engine": test_engine}


def test_batch_tracker_basic_flow():
    user_id = uuid4()
    tx_ids = [uuid4(), uuid4(), uuid4()]

    # Initially empty
    assert BatchTracker.get_last_batch(user_id) is None

    # Set batch
    BatchTracker.set_last_batch(user_id, tx_ids)
    retrieved = BatchTracker.get_last_batch(user_id)
    assert retrieved == tx_ids

    # Clear batch
    BatchTracker.clear_last_batch(user_id)
    assert BatchTracker.get_last_batch(user_id) is None


def test_openai_provider_truncation_detection():
    from pydantic import BaseModel

    class DummySchema(BaseModel):
        val: str

    provider = OpenAICompatibleProvider(api_key="test_key")

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {"content": '{"val": "truncated'},
                "finish_reason": "length"
            }
        ]
    }

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response

    with patch("src.core.llm.providers.openai_provider.get_http_client", return_value=mock_client):
        with pytest.raises(PayloadTruncatedError) as exc_info:
            asyncio.run(provider.complete_structured(
                system_prompt="system",
                user_prompt="user",
                schema=DummySchema
            ))
        assert "exceeded token budget" in str(exc_info.value)


def test_ai_orchestrator_truncation_guard_rejects_without_saving(db_setup):
    orchestrator = AIOrchestrator()
    user_id = str(db_setup["user_id"])
    chat_id = 987654321

    mock_extraction_svc = MagicMock()
    mock_extraction_svc.classify_and_extract = AsyncMock(side_effect=PayloadTruncatedError("Token budget exceeded"))

    sent_messages = []
    async def mock_send(chat_id, text, **kwargs):
        sent_messages.append(text)

    mock_tg = MagicMock()
    mock_tg.send_message = AsyncMock(side_effect=mock_send)

    with patch("src.services.ai_orchestrator.ExtractionService", return_value=mock_extraction_svc):
        with patch("src.services.ai_orchestrator.TelegramService", return_value=mock_tg):
            asyncio.run(orchestrator.orchestrate(
                user_id=user_id,
                chat_id=chat_id,
                text="*Gastos Septiembre\n-1/9 Empanadas $20000\n-2/9 Cheroga $4800",
                audio_file_id=None
            ))

    assert len(sent_messages) == 1
    assert "Lista demasiado extensa" in sent_messages[0] or "List is too long" in sent_messages[0]


def test_batch_undo_removes_all_items_in_batch(db_setup):
    test_engine = db_setup["engine"]
    user_uuid = db_setup["user_id"]
    family_id = db_setup["family_id"]
    enc = db_setup["encryption"]

    with Session(test_engine) as session:
        tx1 = Transaction(
            family_id=family_id,
            user_id=user_uuid,
            amount=enc.encrypt("20000.00 USD"),
            concept=enc.encrypt("Empanadas"),
            category="Food/Drink",
            timestamp=datetime.now(timezone.utc),
            type="expense"
        )
        tx2 = Transaction(
            family_id=family_id,
            user_id=user_uuid,
            amount=enc.encrypt("6500.00 USD"),
            concept=enc.encrypt("Manglar"),
            category="Food/Drink",
            timestamp=datetime.now(timezone.utc),
            type="expense"
        )
        tx3 = Transaction(
            family_id=family_id,
            user_id=user_uuid,
            amount=enc.encrypt("4800.00 USD"),
            concept=enc.encrypt("Cheroga"),
            category="Food/Drink",
            timestamp=datetime.now(timezone.utc),
            type="expense"
        )
        session.add_all([tx1, tx2, tx3])
        session.commit()
        session.refresh(tx1)
        session.refresh(tx2)
        session.refresh(tx3)
        tx1_id, tx2_id, tx3_id = tx1.id, tx2.id, tx3.id

    # Track in BatchTracker
    BatchTracker.set_last_batch(user_uuid, [tx1_id, tx2_id, tx3_id])

    # Perform bare /undo
    result = handle_transaction_undo(
        user_uuid=user_uuid,
        parsed_query=None,
        encryption_service=enc
    )

    # Verify response lists all 3 transactions
    assert "Removed 3 transactions from your last message" in result
    assert "Empanadas" in result
    assert "Manglar" in result
    assert "Cheroga" in result

    # Verify all 3 transactions were deleted from DB
    with Session(test_engine) as session:
        remaining = session.exec(select(Transaction).where(Transaction.user_id == user_uuid)).all()
        assert len(remaining) == 0

    # Verify BatchTracker was cleared
    assert BatchTracker.get_last_batch(user_uuid) is None


def test_targeted_undo_only_removes_specified_item(db_setup):
    test_engine = db_setup["engine"]
    user_uuid = db_setup["user_id"]
    family_id = db_setup["family_id"]
    enc = db_setup["encryption"]

    with Session(test_engine) as session:
        tx1 = Transaction(
            family_id=family_id,
            user_id=user_uuid,
            amount=enc.encrypt("20000.00 USD"),
            concept=enc.encrypt("Empanadas"),
            category="Food/Drink",
            timestamp=datetime.now(timezone.utc),
            type="expense"
        )
        tx2 = Transaction(
            family_id=family_id,
            user_id=user_uuid,
            amount=enc.encrypt("4800.00 USD"),
            concept=enc.encrypt("Cheroga"),
            category="Food/Drink",
            timestamp=datetime.now(timezone.utc),
            type="expense"
        )
        session.add_all([tx1, tx2])
        session.commit()
        session.refresh(tx1)
        session.refresh(tx2)
        tx1_id, tx2_id = tx1.id, tx2.id

    BatchTracker.set_last_batch(user_uuid, [tx1_id, tx2_id])

    # Targeted undo for Cheroga
    query = ParsedQueryIntent(intent="undo_last", target_concept="Cheroga")
    result = handle_transaction_undo(
        user_uuid=user_uuid,
        parsed_query=query,
        encryption_service=enc
    )

    assert "Cheroga" in result
    with Session(test_engine) as session:
        remaining = session.exec(select(Transaction).where(Transaction.user_id == user_uuid)).all()
        assert len(remaining) == 1
        assert remaining[0].id == tx1_id


@pytest.mark.anyio
async def test_batch_confirmation_formatting_mixed_income_and_expense(db_setup):
    user_uuid = db_setup["user_id"]
    orchestrator = AIOrchestrator()

    mock_unified = UnifiedResult(
        action="log_transaction",
        items=[
            ParsedItem(concept="trabajo freelance", amount=450.0, currency="USD", type="income", category="Freelance"),
            ParsedItem(concept="seña bicicleta", amount=25000.0, currency="ARS", type="income", category="Sale"),
            ParsedItem(concept="verdulería", amount=3500.0, currency="ARS", type="expense", category="Food/Drink"),
            ParsedItem(concept="nafta", amount=18000.0, currency="ARS", type="expense", category="Transport"),
        ]
    )

    mock_tg = AsyncMock()
    with patch("src.services.ai_orchestrator.ExtractionService.classify_and_extract", AsyncMock(return_value=mock_unified)), \
         patch("src.services.ai_orchestrator.TelegramService.send_message", mock_tg):
        
        # Test in Spanish
        await orchestrator.orchestrate(
            user_id=str(user_uuid),
            text="cobré 450 dólares freelance, 25000 de seña, gasté 3500 en verdulería y 18000 de nafta",
            audio_file_id=None,
            chat_id=12345
        )

        mock_tg.assert_called_once()
        reply = mock_tg.call_args[1]["text"]

        assert "4 Transacciones Registradas" in reply
        assert "• 💰 <b>trabajo freelance:</b> +$450.00 USD (Freelance)" in reply
        assert "• 💰 <b>seña bicicleta:</b> +$25,000.00 ARS (Sale)" in reply
        assert "• 💸 <b>verdulería:</b> $3,500.00 ARS (Food/Drink)" in reply
        assert "• 💸 <b>nafta:</b> $18,000.00 ARS (Transport)" in reply


@pytest.mark.anyio
async def test_batch_confirmation_formatting_incomes_only(db_setup):
    user_uuid = db_setup["user_id"]
    orchestrator = AIOrchestrator()

    mock_unified = UnifiedResult(
        action="log_transaction",
        items=[
            ParsedItem(concept="freelance", amount=500.0, currency="USD", type="income", category="Freelance"),
            ParsedItem(concept="dividendos", amount=120.0, currency="USD", type="income", category="Investment"),
        ]
    )

    mock_tg = AsyncMock()
    with patch("src.services.ai_orchestrator.ExtractionService.classify_and_extract", AsyncMock(return_value=mock_unified)), \
         patch("src.services.ai_orchestrator.TelegramService.send_message", mock_tg):
        
        await orchestrator.orchestrate(
            user_id=str(user_uuid),
            text="cobré 500 de freelance y 120 de dividendos",
            audio_file_id=None,
            chat_id=12345
        )

        mock_tg.assert_called_once()
        reply = mock_tg.call_args[1]["text"]

        assert "2 Ingreso(s) Registrado(s)" in reply
        assert "• 💰 <b>freelance:</b> +$500.00 USD (Freelance)" in reply
        assert "• 💰 <b>dividendos:</b> +$120.00 USD (Investment)" in reply


@pytest.mark.anyio
async def test_batch_confirmation_formatting_expenses_only(db_setup):
    user_uuid = db_setup["user_id"]
    orchestrator = AIOrchestrator()

    mock_unified = UnifiedResult(
        action="log_transaction",
        items=[
            ParsedItem(concept="almuerzo", amount=15.0, currency="USD", type="expense", category="Food/Drink"),
            ParsedItem(concept="taxi", amount=10.0, currency="USD", type="expense", category="Transport"),
        ]
    )

    mock_tg = AsyncMock()
    with patch("src.services.ai_orchestrator.ExtractionService.classify_and_extract", AsyncMock(return_value=mock_unified)), \
         patch("src.services.ai_orchestrator.TelegramService.send_message", mock_tg):
        
        await orchestrator.orchestrate(
            user_id=str(user_uuid),
            text="gastos de hoy: almuerzo 15 y taxi 10",
            audio_file_id=None,
            chat_id=12345
        )

        mock_tg.assert_called_once()
        reply = mock_tg.call_args[1]["text"]

        assert "2 Gasto(s) Registrado(s)" in reply
        assert "• 💸 <b>almuerzo:</b> $15.00 USD (Food/Drink)" in reply
        assert "• 💸 <b>taxi:</b> $10.00 USD (Transport)" in reply


def test_inline_batch_fallback_expenses():
    from src.services.extraction.fallback import fallback_regex_classify

    res1 = fallback_regex_classify("2509 verdu y 5999 almacén", default_currency="ARS")
    assert res1.action == "log_transaction"
    assert len(res1.items) == 2
    assert res1.items[0].amount == 2509.0
    assert res1.items[0].concept == "verdu"
    assert res1.items[0].category == "Food/Drink"
    assert res1.items[0].currency == "ARS"
    assert res1.items[1].amount == 5999.0
    assert res1.items[1].concept == "almacén"
    assert res1.items[1].category == "Food/Drink"
    assert res1.items[1].currency == "ARS"

    res2 = fallback_regex_classify("Gaste 399 en el súper y 599 en nafta", default_currency="ARS")
    assert res2.action == "log_transaction"
    assert len(res2.items) == 2
    assert res2.items[0].amount == 399.0
    assert res2.items[0].concept == "súper"
    assert res2.items[0].category == "Food/Drink"
    assert res2.items[0].currency == "ARS"
    assert res2.items[1].amount == 599.0
    assert res2.items[1].concept == "nafta"
    assert res2.items[1].category == "Transport"
    assert res2.items[1].currency == "ARS"


@pytest.mark.anyio
async def test_inline_batch_live_ollama_ai():
    """Live AI test running against real local Ollama (e.g. llama3) if reachable."""
    import os
    if os.environ.get("RUN_LIVE_AI") != "true":
        pytest.skip("Skipping live AI test during fast unit test runs. Set RUN_LIVE_AI=true to execute.")

    import httpx
    ollama_url = "http://localhost:11434"
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{ollama_url}/api/tags")
            if resp.status_code != 200:
                pytest.skip("Local Ollama is not running on port 11434")
            data = resp.json()
            models = [m.get("name", "") for m in data.get("models", [])]
            if not any("llama3" in m for m in models):
                pytest.skip(f"llama3 not available in Ollama models: {models}")
    except Exception:
        pytest.skip("Local Ollama is not reachable on port 11434")

    from src.core.llm.providers.ollama_provider import OllamaProvider
    from src.services.extraction.prompts import UNIFIED_SYSTEM_PROMPT

    provider = OllamaProvider(model="llama3:latest", host=ollama_url)
    user_prompt = (
        "<system_context>\n"
        "Default Workspace Currency: ARS\n"
        "Current Reference Date: 2026-09-03\n"
        "</system_context>\n"
        "<user_input>\n"
        "2509 verdu y 5999 almacén\n"
        "</user_input>"
    )

    raw_json = await provider.complete_structured(
        system_prompt=UNIFIED_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        schema=UnifiedResult,
        temperature=0.0
    )

    parsed = UnifiedResult.model_validate_json(raw_json)
    assert parsed.action == "log_transaction"
    assert len(parsed.items) == 2
    amounts = [item.amount for item in parsed.items]
    assert 2509.0 in amounts
    assert 5999.0 in amounts

