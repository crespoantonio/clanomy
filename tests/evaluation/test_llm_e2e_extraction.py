"""
End-to-End Integration Tests for Message Simulation Endpoint and Extraction Dataset.
Verifies authentication secrets, header propagation, fallback parsing,
and end-to-end bot message formatting.
"""

import os
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock

from src.main import app
from src.core.config import settings
from src.services.extraction.models import UnifiedResult, ParsedItem
from tests.data.llm_extraction_dataset import DATASET


@pytest.mark.anyio
async def test_simulation_endpoint_requires_secret():
    """Verifies that missing or invalid X-Simulation-Secret returns 403 Forbidden."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Missing secret
        resp = await ac.post(
            "/api/v1/simulate/message",
            json={"text": "2509 verdu y 5999 almacén"}
        )
        assert resp.status_code == 403
        assert "Forbidden" in resp.json().get("detail", "")

        # 2. Invalid secret
        resp_invalid = await ac.post(
            "/api/v1/simulate/message",
            json={"text": "2509 verdu y 5999 almacén"},
            headers={"X-Simulation-Secret": "invalid_wrong_secret"}
        )
        assert resp_invalid.status_code == 403

        # 3. Webhook secret does NOT grant access (strict isolation)
        with patch.object(settings, "SIMULATION_SECRET", "strict_sim_secret"), \
             patch.object(settings, "MESSAGING_WEBHOOK_SECRET", "telegram_webhook_secret"):
            resp_webhook = await ac.post(
                "/api/v1/simulate/message",
                json={"text": "2509 verdu"},
                headers={"X-Simulation-Secret": "telegram_webhook_secret"}
            )
            assert resp_webhook.status_code == 403


@pytest.mark.anyio
async def test_simulation_endpoint_gemini_requires_api_key_header():
    """Verifies that when testing Gemini, X-Gemini-Api-Key is mandatory as a header."""
    valid_secret = "test_simulation_secret"
    with patch.object(settings, "SIMULATION_SECRET", valid_secret):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(
                "/api/v1/simulate/message",
                json={"text": "1500 café"},
                headers={
                    "X-Simulation-Secret": valid_secret,
                    "X-AI-Provider": "gemini"
                }
            )
            assert resp.status_code == 400
            assert "X-Gemini-Api-Key" in resp.json().get("detail", "")


@pytest.mark.anyio
async def test_simulation_endpoint_openai_requires_api_key_header():
    """Verifies that cloud providers (openai/groq) require X-AI-Api-Key and do not fall back to server env."""
    valid_secret = "test_simulation_secret"
    with patch.object(settings, "SIMULATION_SECRET", valid_secret), \
         patch.object(settings, "AI_API_KEY", "server_confidential_key"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(
                "/api/v1/simulate/message",
                json={"text": "1500 café"},
                headers={
                    "X-Simulation-Secret": valid_secret,
                    "X-AI-Provider": "openai"
                }
            )
            assert resp.status_code == 400
            assert "X-AI-Api-Key" in resp.json().get("detail", "")


@pytest.mark.anyio
async def test_simulation_endpoint_successful_mocked_gemini_flow():
    """Verifies full end-to-end response generation via the simulation endpoint with mocked GeminiProvider."""
    valid_secret = "test_simulation_secret"
    mock_items = [
        ParsedItem(concept="verdu", amount=2509.0, currency="ARS", type="expense", category="Food/Drink"),
        ParsedItem(concept="almacén", amount=5999.0, currency="ARS", type="expense", category="Food/Drink"),
    ]
    mock_unified = UnifiedResult(
        action="log_transaction",
        items=mock_items,
        amount=2509.0,
        concept="verdu",
        category="Food/Drink",
        currency="ARS",
        type="expense"
    )

    with patch.object(settings, "SIMULATION_SECRET", valid_secret), \
         patch("src.core.llm.providers.gemini_provider.GeminiProvider.complete_structured", AsyncMock(return_value=mock_unified.model_dump_json())):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(
                "/api/v1/simulate/message",
                json={
                    "text": "2509 verdu y 5999 almacén",
                    "default_currency": "ARS",
                    "dry_run": True
                },
                headers={
                    "X-Simulation-Secret": valid_secret,
                    "X-AI-Provider": "gemini",
                    "X-Gemini-Api-Key": "AIzaSyTestMockKeyForSimulatedEndpoint"
                }
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "success"
            assert data["item_count"] == 2
            assert data["action"] == "log_transaction"
            assert data["provider"] == "gemini"
            assert "2 Gasto(s) Registrado(s)" in data["bot_response"]
            assert "verdu" in data["bot_response"]
            assert "almacén" in data["bot_response"]


@pytest.mark.anyio
async def test_simulation_endpoint_mixed_batch_15_items():
    """Verifies end-to-end formatting for a 15-item stress test batch (case_55)."""
    valid_secret = "test_simulation_secret"
    case_55 = next(c for c in DATASET if c["id"] == "case_55")

    # Generate 15 items corresponding to case_55
    items = []
    for i, (amt, tp) in enumerate(zip(case_55["expected_amounts"], case_55["expected_types"])):
        cat = "Salary" if tp == "income" else "Food/Drink"
        items.append(ParsedItem(
            concept=f"item_{i+1}",
            amount=amt,
            currency="USD" if amt < 10000 else "ARS",
            type=tp,
            category=cat
        ))

    mock_unified = UnifiedResult(
        action="log_transaction",
        items=items,
        amount=items[0].amount,
        concept=items[0].concept,
        category=items[0].category,
        currency=items[0].currency,
        type=items[0].type
    )

    with patch.object(settings, "SIMULATION_SECRET", valid_secret), \
         patch("src.services.extraction.service.ExtractionService.classify_and_extract", AsyncMock(return_value=mock_unified)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(
                "/api/v1/simulate/message",
                json={
                    "text": case_55["text"],
                    "default_currency": "ARS",
                    "dry_run": True
                },
                headers={"X-Simulation-Secret": valid_secret}
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["item_count"] == 15
            # Header for mixed transactions
            assert "15 Transacciones Registradas" in data["bot_response"]


def test_dataset_coverage():
    """Verifies that dataset contains at least 50 cases covering 1 to 15 items."""
    assert len(DATASET) >= 50
    counts = {c["expected_count"] for c in DATASET}
    for required_count in range(1, 16):
        assert required_count in counts, f"Missing test case for item count {required_count}"


def test_match_items_with_types_logic():
    """Verifies that match_items_with_types strictly validates count, amount, and type pairs."""
    from scripts.run_llm_eval import match_items_with_types

    # 1. Perfect match
    c, a, t = match_items_with_types(
        expected_amounts=[1200.0, 150.0],
        expected_types=["income", "expense"],
        extracted_amounts=[1200.0, 150.0],
        extracted_types=["income", "expense"]
    )
    assert c and a and t

    # 2. Amount matches but type inverted (income marked as expense)
    c, a, t = match_items_with_types(
        expected_amounts=[1200.0, 150.0],
        expected_types=["income", "expense"],
        extracted_amounts=[1200.0, 150.0],
        extracted_types=["expense", "income"]
    )
    assert c is True
    assert a is True
    assert t is False  # Type failed!

    # 3. Count mismatch
    c, a, t = match_items_with_types(
        expected_amounts=[100.0],
        expected_types=["expense"],
        extracted_amounts=[100.0, 200.0],
        extracted_types=["expense", "expense"]
    )
    assert c is False


def test_fallback_regex_preserves_concepts_with_periods():
    """Verifies that fallback regex does not discard concepts in phrases with periods."""
    from src.services.extraction.fallback import fallback_regex_classify

    res1 = fallback_regex_classify("Pagué en el almacén. 1500 pesos", default_currency="ARS")
    assert res1.action == "log_transaction"
    assert len(res1.items) == 1
    assert res1.items[0].amount == 1500.0
    assert "almacén" in res1.items[0].concept.lower()

    res2 = fallback_regex_classify("Dr. Smith 200 usd", default_currency="USD")
    assert res2.action == "log_transaction"
    assert len(res2.items) == 1
    assert res2.items[0].amount == 200.0
    assert "smith" in res2.items[0].concept.lower()


@pytest.mark.anyio
async def test_simulation_endpoint_rejects_unsupported_provider():
    """Verifies that an unknown provider cannot fall back to server env credentials."""
    valid_secret = "test_simulation_secret"
    with patch.object(settings, "SIMULATION_SECRET", valid_secret):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(
                "/api/v1/simulate/message",
                json={"text": "1500 café"},
                headers={
                    "X-Simulation-Secret": valid_secret,
                    "X-AI-Provider": "unsupported_provider"
                }
            )
            assert resp.status_code == 400
            assert "Unsupported simulation provider" in resp.json().get("detail", "")


@pytest.mark.anyio
async def test_cloudflare_origin_shield_applies_to_simulation():
    """Verifies that simulation endpoint enforces Cloudflare Origin Shield when configured."""
    with patch.object(settings, "CLOUDFLARE_ORIGIN_SECRET", "cf_secret_shield"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(
                "/api/v1/simulate/message",
                json={"text": "1500 café"},
                headers={"X-Simulation-Secret": "any_secret"}
            )
            assert resp.status_code == 403
            assert "Direct origin access forbidden" in resp.json().get("detail", "")

