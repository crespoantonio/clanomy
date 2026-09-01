import pytest
import os
import uuid
import httpx
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock, AsyncMock
from sqlmodel import Session, select, create_engine, SQLModel
from sqlalchemy.pool import StaticPool

from src.core.config import settings
from src.core.encryption import EncryptionService
from src.db.models import User, Family, Transaction
from src.services.telegram_service import TelegramService
from src.services.query.date_resolver import (
    resolve_date_range,
    _resolve_comparison_timeframe,
    _sanitize_concept_for_prompt,
    _parse_amount_string
)
from src.services.extraction.normalizers import (
    normalize_category_value,
    normalize_currency_value
)
from src.services.messaging_service import MessagingService
from src.services.export_service import ExportService
from src.services.account_service import AccountService
from src.services.ai_orchestrator import _format_currency


@pytest.fixture(name="db_engine")
def db_engine_fixture():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)


# ---------------------------------------------------------
# 1. TelegramService Coverage Boost
# ---------------------------------------------------------

@pytest.mark.anyio
async def test_telegram_delete_message_success_and_error():
    service = TelegramService()
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        res = await service.delete_message(chat_id=123, message_id=456)
        assert res is True

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.RequestError("Network error")
        res = await service.delete_message(chat_id=123, message_id=456)
        assert res is False


@pytest.mark.anyio
async def test_telegram_get_file_url_and_bot_username():
    service = TelegramService()

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"ok": True, "result": {"file_path": "voice/audio1.ogg"}}
        mock_get.return_value = mock_resp

        url = await service.get_file_url("file_123")
        assert "voice/audio1.ogg" in url

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = httpx.HTTPError("File not found")
        url = await service.get_file_url("file_123")
        assert url is None

    if hasattr(service, '_bot_username'):
        delattr(service, '_bot_username')
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"ok": True, "result": {"username": "ClanomyTestBot"}}
        mock_get.return_value = mock_resp

        with patch.object(settings, "TELEGRAM_BOT_USERNAME", None):
            name = await service.get_bot_username()
            assert name == "ClanomyTestBot"


# ---------------------------------------------------------
# 2. Date Resolver & Query Formatters Coverage Boost
# ---------------------------------------------------------

def test_date_resolver_branches():
    ref_time = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

    # Regex days / months
    s1, e1 = resolve_date_range("last_15_days", None, None, reference_time=ref_time)
    assert s1 is not None and e1 is not None
    s2, e2 = resolve_date_range("ultimos_2_meses", None, None, reference_time=ref_time)
    assert s2 is not None and e2 is not None

    # Common terms
    st, et = resolve_date_range("hoy", None, None, reference_time=ref_time)
    assert st.day == 15
    sy, ey = resolve_date_range("ayer", None, None, reference_time=ref_time)
    assert sy.day == 14
    sw, ew = resolve_date_range("la_semana_pasada", None, None, reference_time=ref_time)
    assert sw is not None and ew is not None
    sm, em = resolve_date_range("last_month", None, None, reference_time=ref_time)
    assert sm.month == 12 and sm.year == 2025

    # Custom dates
    sc, ec = resolve_date_range("custom", "2026-05-01", "2026-05-10", reference_time=ref_time)
    assert sc.month == 5 and ec.day == 10
    si, ei = resolve_date_range("custom", "invalid-date", "bad-date", reference_time=ref_time)
    assert si is None and ei is None

    # Comparison timeframe in January
    prev_tf, prev_s, prev_e = _resolve_comparison_timeframe("this_month", reference_time=ref_time)
    assert prev_tf == "last_month"
    assert prev_s.month == 12 and prev_s.year == 2025

    prev_today_tf, _, _ = _resolve_comparison_timeframe("today", reference_time=ref_time)
    assert prev_today_tf == "yesterday"

    assert _sanitize_concept_for_prompt("") == ""
    assert _sanitize_concept_for_prompt("Dinner with family! @#$$%^&*") == "Dinner with family"
    assert _parse_amount_string("") == (0.0, "USD")
    assert _parse_amount_string("invalid EUR") == (0.0, "EUR")


# ---------------------------------------------------------
# 3. Extraction Normalizers Coverage Boost
# ---------------------------------------------------------

def test_extraction_normalizers_edge_cases():
    assert normalize_category_value(None) is None
    assert normalize_category_value("") is None
    assert normalize_category_value("unknown_xyz") == "Other"
    assert normalize_category_value("CENA") == "Food/Drink"
    assert normalize_category_value("nafta") == "Transport"
    assert normalize_category_value("alquiler") == "Rent/Bills"

    assert normalize_currency_value(None) is None
    assert normalize_currency_value("") is None
    assert normalize_currency_value("CAD") == "CAD"
    assert normalize_currency_value("jpy") == "JPY"
    assert normalize_currency_value("mangos", default_currency="ARS") == "ARS"
    assert normalize_currency_value("lucas", default_currency="CLP") == "CLP"


# ---------------------------------------------------------
# 4. MessagingService Coverage Boost
# ---------------------------------------------------------

def test_messaging_service_edge_cases(db_engine):
    with Session(db_engine) as session:
        service = MessagingService(session)

        with pytest.raises(ValueError, match="User ID is required"):
            service.get_or_create_user_and_family({"username": "nouserid"})

        u1, f1 = service.get_or_create_user_and_family({
            "id": 999111,
            "username": "user1",
            "first_name": "First",
            "last_name": "Last"
        })
        assert u1.full_name == "First Last"

        u1_up, f1_up = service.get_or_create_user_and_family({
            "id": 999111,
            "username": "user1_new",
            "first_name": "Updated",
            "last_name": "Name"
        })
        assert u1_up.username == "user1_new"
        assert u1_up.full_name == "Updated Name"


# ---------------------------------------------------------
# 5. ExportService Coverage Boost
# ---------------------------------------------------------

@pytest.mark.anyio
async def test_export_service_json_and_empty(db_engine):
    export_service = ExportService(engine_override=db_engine)
    encryption = EncryptionService()
    
    with Session(db_engine) as session:
        fam = Family(name="Export Fam", plan_type="trial")
        session.add(fam)
        session.commit()
        session.refresh(fam)
        fam_id = fam.id

        u = User(telegram_id=112233, username="export_user", family_id=fam_id)
        session.add(u)
        session.commit()
        session.refresh(u)

        tx = Transaction(
            user_id=u.id,
            family_id=fam_id,
            amount=encryption.encrypt("100.00 USD"),
            concept=encryption.encrypt("Monitor"),
            category="Shopping",
            type="expense"
        )
        session.add(tx)
        session.commit()

    temp_path, count = await export_service.export_data(fam_id, format="json")
    assert count == 1
    assert os.path.exists(temp_path)
    os.unlink(temp_path)

    with patch.object(export_service.telegram_service, "send_document", new_callable=AsyncMock) as mock_doc:
        await export_service.export_and_send(fam_id, chat_id=112233, format="csv")
        mock_doc.assert_called_once()


# ---------------------------------------------------------
# 6. AccountService Coverage Boost
# ---------------------------------------------------------

@pytest.mark.anyio
async def test_account_service_nonexistent_and_error(db_engine):
    service = AccountService(engine=db_engine)
    
    res = await service.delete_account(uuid.uuid4())
    assert res is False

    with patch.object(service, "_delete_account_sync", return_value=False):
        res = await service.delete_account(uuid.uuid4())
        assert res is False


# ---------------------------------------------------------
# 7. AIOrchestrator Helpers & Currency Formatter Coverage
# ---------------------------------------------------------

def test_ai_orchestrator_currency_formatting():
    assert "$" in _format_currency(100.0, "USD", show_sign=False)
    assert "€" in _format_currency(50.0, "EUR", show_sign=True)
    assert "£" in _format_currency(-20.0, "GBP")
    assert "R$" in _format_currency(15.0, "BRL")
    assert "S/" in _format_currency(30.0, "PEN")
    assert _format_currency(0.0, "USD") == "$0.00 USD"


# ---------------------------------------------------------
# 8. Database Session Helpers Coverage
# ---------------------------------------------------------

def test_db_session_get_session_and_init(db_engine):
    from src.db.session import get_session
    gen = get_session()
    sess = next(gen)
    assert sess is not None
    sess.close()


# ---------------------------------------------------------
# 9. Cloud AI Provider Coverage Boost
# ---------------------------------------------------------

@pytest.mark.anyio
async def test_cloud_ai_extraction_and_query():
    from src.services.extraction.service import ExtractionService
    from src.services.query.service import QueryService
    from src.services.whisper_service import WhisperService

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        async def fake_post(url, *args, **kwargs):
            mock_resp = MagicMock()
            mock_resp.raise_for_status.return_value = None
            if "audio/transcriptions" in str(url):
                mock_resp.json.return_value = {"text": "spent 50 on dinner"}
            elif "chat/completions" in str(url):
                payload = kwargs.get("json", {})
                payload_str = str(payload)
                if "Classify this financial query" in payload_str:
                    mock_resp.json.return_value = {
                        "choices": [{"message": {"content": '{"intent":"spending_summary","timeframe":"this_month","scope":"family"}'}}]
                    }
                elif "financial assistant" in payload_str:
                    mock_resp.json.return_value = {
                        "choices": [{"message": {"content": "You spent $50 on dinner this month."}}]
                    }
                else:
                    mock_resp.json.return_value = {
                        "choices": [{"message": {"content": '{"intent":"log_transaction","type":"expense","amount":50.0,"category":"Food/Drink","concept":"dinner","currency":"USD"}'}}]
                    }
            return mock_resp

        mock_post.side_effect = fake_post

        with patch.object(settings, "AI_API_KEY", "test_cloud_ai_key"):
            ext_service = ExtractionService()
            c1 = await ext_service._call_cloud_ai_unified("system", "spent 50 on dinner")
            assert "expense" in c1
            c2 = await ext_service._call_cloud_ai("system", "spent 50 on dinner")
            assert "expense" in c2

            query_service = QueryService()
            q1 = await query_service._call_cloud_ai_parse_intent("system", "how much did we spend?")
            assert "spending_summary" in q1
            q2 = await query_service._call_cloud_ai_summary("system", "user prompt")
            assert q2 is not None

            whisper_service = WhisperService()
            txt, lang = await whisper_service.transcribe(audio_bytes=b"dummy_audio_bytes")
            assert txt == "spent 50 on dinner"
            assert lang == "en"


# ---------------------------------------------------------
# 10. NotionService Error Handling & Search Coverage
# ---------------------------------------------------------

@pytest.mark.anyio
async def test_notion_service_errors_and_methods(db_engine):
    from src.services.notion_service import NotionService, NotionServiceError

    class MockAPIResponseError(Exception):
        def __init__(self, code, message):
            self.code = code
            self.message = message
            super().__init__(message)

    with Session(db_engine) as session:
        notion = NotionService(session)

        with patch("src.services.notion_service.AsyncClient") as MockNotion:
            with patch("src.services.notion_service.APIResponseError", MockAPIResponseError):
                mock_client_instance = AsyncMock()
                mock_client_instance.users.me.side_effect = MockAPIResponseError("unauthorized", "Unauthorized")
                MockNotion.return_value.__aenter__.return_value = mock_client_instance

                is_valid = await notion.validate_token("bad_key")
                assert is_valid is False

        with patch("src.services.notion_service.AsyncClient") as MockNotion:
            mock_client_instance = AsyncMock()
            mock_client_instance.users.me.side_effect = Exception("API connection dropped")
            MockNotion.return_value.__aenter__.return_value = mock_client_instance

            with pytest.raises(NotionServiceError, match="Failed to communicate with Notion API"):
                await notion.validate_token("bad_key")

        with patch("src.services.notion_service.AsyncClient") as MockNotion:
            mock_client_instance = AsyncMock()
            mock_client_instance.search.return_value = {
                "results": [
                    {
                        "id": "db-12345",
                        "title": [{"plain_text": "Expenses 2026"}],
                        "url": "https://notion.so/db-12345",
                        "properties": {"Amount": {}, "Concept": {}, "Category": {}}
                    }
                ]
            }
            MockNotion.return_value.__aenter__.return_value = mock_client_instance

            dbs = await notion.search_databases("valid_token")
            assert len(dbs) == 1
            assert dbs[0]["title"] == "Expenses 2026"


# ---------------------------------------------------------
# 11. Telegram Webhook Lifecycle Endpoints Coverage Boost
# ---------------------------------------------------------

@pytest.mark.anyio
async def test_telegram_webhook_lifecycle_endpoints(db_engine):
    from src.api.routes.telegram import handle_renewal, handle_cancellation, handle_failure, LifecyclePayload
    from fastapi import BackgroundTasks, HTTPException

    with Session(db_engine) as session:
        fam = Family(name="Lifecycle Fam", plan_type="solo_pro")
        session.add(fam)
        session.commit()
        session.refresh(fam)
        fam_id_str = str(fam.id)

        # 1. Renewal
        with pytest.raises(HTTPException) as exc:
            await handle_renewal(LifecyclePayload(family_id=fam_id_str), session=session, x_telegram_bot_api_secret_token="bad")
        assert exc.value.status_code == 403

        with pytest.raises(HTTPException) as exc:
            await handle_renewal(LifecyclePayload(family_id="invalid-uuid"), session=session, x_telegram_bot_api_secret_token=settings.MESSAGING_WEBHOOK_SECRET)
        assert exc.value.status_code == 400

        with pytest.raises(HTTPException) as exc:
            await handle_renewal(LifecyclePayload(family_id=str(uuid.uuid4())), session=session, x_telegram_bot_api_secret_token=settings.MESSAGING_WEBHOOK_SECRET)
        assert exc.value.status_code == 404

        res_renew = await handle_renewal(
            LifecyclePayload(family_id=fam_id_str, charge_id="ch_123", expiration_timestamp=1800000000),
            session=session,
            x_telegram_bot_api_secret_token=settings.MESSAGING_WEBHOOK_SECRET
        )
        assert res_renew["status"] == "ok"

        # 2. Cancellation
        with pytest.raises(HTTPException) as exc:
            await handle_cancellation(LifecyclePayload(family_id=fam_id_str), session=session, x_telegram_bot_api_secret_token="bad")
        assert exc.value.status_code == 403

        with pytest.raises(HTTPException) as exc:
            await handle_cancellation(LifecyclePayload(family_id="invalid-uuid"), session=session, x_telegram_bot_api_secret_token=settings.MESSAGING_WEBHOOK_SECRET)
        assert exc.value.status_code == 400

        with pytest.raises(HTTPException) as exc:
            await handle_cancellation(LifecyclePayload(family_id=str(uuid.uuid4())), session=session, x_telegram_bot_api_secret_token=settings.MESSAGING_WEBHOOK_SECRET)
        assert exc.value.status_code == 404

        res_cancel = await handle_cancellation(
            LifecyclePayload(family_id=fam_id_str),
            session=session,
            x_telegram_bot_api_secret_token=settings.MESSAGING_WEBHOOK_SECRET
        )
        assert res_cancel["status"] == "ok"

        # 3. Failure
        bg = BackgroundTasks()
        with pytest.raises(HTTPException) as exc:
            await handle_failure(LifecyclePayload(family_id=fam_id_str), background_tasks=bg, session=session, x_telegram_bot_api_secret_token="bad")
        assert exc.value.status_code == 403

        with pytest.raises(HTTPException) as exc:
            await handle_failure(LifecyclePayload(family_id="invalid-uuid"), background_tasks=bg, session=session, x_telegram_bot_api_secret_token=settings.MESSAGING_WEBHOOK_SECRET)
        assert exc.value.status_code == 400

        with pytest.raises(HTTPException) as exc:
            await handle_failure(LifecyclePayload(family_id=str(uuid.uuid4())), background_tasks=bg, session=session, x_telegram_bot_api_secret_token=settings.MESSAGING_WEBHOOK_SECRET)
        assert exc.value.status_code == 404

        res_fail = await handle_failure(
            LifecyclePayload(family_id=fam_id_str),
            background_tasks=bg,
            session=session,
            x_telegram_bot_api_secret_token=settings.MESSAGING_WEBHOOK_SECRET
        )
        assert res_fail["status"] == "ok"

