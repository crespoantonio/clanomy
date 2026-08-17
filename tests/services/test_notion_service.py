import pytest
from uuid import uuid4
from unittest.mock import patch, MagicMock, AsyncMock
from src.services.notion_service import NotionService, NotionAuthError, NotionDatabaseNotFoundError, NotionServiceError
from src.db.models import Family
from src.core.encryption import EncryptionService
from sqlmodel import Session, create_engine, SQLModel
from datetime import datetime, timezone

@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session

@pytest.fixture(name="notion_service")
def notion_service_fixture(session: Session):
    return NotionService(session)

@pytest.fixture(name="family")
def family_fixture(session: Session):
    family = Family(name="Test Family")
    session.add(family)
    session.commit()
    session.refresh(family)
    return family

@pytest.mark.anyio
@patch("src.services.notion_service.AsyncClient")
async def test_validate_token_success(mock_client_cls, notion_service):
    mock_notion = MagicMock()
    mock_client_cls.return_value.__aenter__.return_value = mock_notion
    mock_notion.users.me = MagicMock()
    # Mock it as async
    async def mock_me():
        pass
    mock_notion.users.me.side_effect = mock_me

    assert await notion_service.validate_token("valid_token") is True

@pytest.mark.anyio
@patch("src.services.notion_service.AsyncClient")
async def test_search_databases(mock_client_cls, notion_service):
    mock_notion = MagicMock()
    mock_client_cls.return_value.__aenter__.return_value = mock_notion
    
    async def mock_search(*args, **kwargs):
        return {
            "results": [
                {
                    "id": "db_123",
                    "title": [{"plain_text": "Budget"}],
                    "url": "http://notion.so/db_123",
                    "properties": {"Amount": {}, "Date": {}}
                }
            ]
        }
    mock_notion.search.side_effect = mock_search

    dbs = await notion_service.search_databases("token")
    assert len(dbs) == 1
    assert dbs[0]["id"] == "db_123"
    assert dbs[0]["title"] == "Budget"

@pytest.mark.anyio
@patch("src.services.notion_service.AsyncClient")
async def test_connect_database(mock_client_cls, notion_service, family, session):
    mock_notion = MagicMock()
    mock_client_cls.return_value.__aenter__.return_value = mock_notion
    
    async def mock_retrieve(database_id):
        return {
            "id": database_id,
            "title": [{"plain_text": "My Database"}],
            "url": f"http://notion.so/{database_id}",
            "properties": {"Name": {}}
        }
    mock_notion.databases.retrieve.side_effect = mock_retrieve

    res = await notion_service.connect_database(family.id, "my_token", "db_456")
    
    assert res["database_id"] == "db_456"
    assert res["database_name"] == "My Database"
    
    # Verify persistence
    session.refresh(family)
    assert family.notion_api_key is not None
    encryption = EncryptionService()
    assert encryption.decrypt(family.notion_api_key) == "my_token"
    assert family.notion_database_id == "db_456"

def test_disconnect_workspace(notion_service, family, session):
    family.notion_api_key = "some_encrypted_key"
    family.notion_database_id = "db_789"
    family.notion_database_name = "To Disconnect"
    family.notion_connected_at = datetime.now(timezone.utc)
    session.add(family)
    session.commit()

    assert notion_service.disconnect_workspace(family.id) is True
    session.refresh(family)
    assert family.notion_api_key is None
    assert family.notion_database_id is None

def test_get_status(notion_service, family, session):
    status = notion_service.get_family_notion_status(family.id)
    assert status["is_connected"] is False
    assert status["has_valid_token"] is False

    family.notion_api_key = "some_key"
    family.notion_database_id = "db_abc"
    session.add(family)
    session.commit()

    status = notion_service.get_family_notion_status(family.id)
    assert status["is_connected"] is True
    assert status["database_id"] == "db_abc"

@pytest.mark.anyio
async def test_mirror_transaction_not_connected(notion_service, family):
    # Family without Notion connected
    result = await notion_service.mirror_transaction(
        family_id=family.id,
        amount=50.0,
        currency="USD",
        concept="Groceries",
        category="Food",
        timestamp=datetime.now(timezone.utc)
    )
    assert result is None

@pytest.mark.anyio
@patch("src.services.notion_service.AsyncClient")
async def test_mirror_transaction_success(mock_client_cls, notion_service, family, session):
    # Setup family with Notion connected
    family.notion_api_key = notion_service.encryption.encrypt("test_token")
    family.notion_database_id = "test_db_id"
    session.add(family)
    session.commit()

    mock_notion = MagicMock()
    mock_client_cls.return_value.__aenter__.return_value = mock_notion

    # Mock database details to provide schema
    notion_service.get_database_details = AsyncMock(return_value={
        "id": "test_db_id",
        "properties_schema": {
            "Concept": {"type": "title"},
            "Amount": {"type": "number"},
            "Category": {"type": "select"},
            "Date": {"type": "date"}
        }
    })

    async def mock_create(**kwargs):
        return {"id": "page_123", "url": "http://notion.so/page_123"}
    mock_notion.pages.create.side_effect = mock_create

    result = await notion_service.mirror_transaction(
        family_id=family.id,
        amount=50.0,
        currency="USD",
        concept="Groceries",
        category="Food",
        timestamp=datetime.now(timezone.utc)
    )
    assert result is not None
    assert result["page_id"] == "page_123"
    assert result["status"] == "mirrored"
    mock_notion.pages.create.assert_called_once()

def test_build_page_properties(notion_service):
    schema = {
        "Name": {"type": "title"},
        "Cost": {"type": "number"},
        "Tags": {"type": "multi_select"},
        "When": {"type": "date"},
        "Who": {"type": "select"}
    }
    
    timestamp = datetime.now(timezone.utc)
    props = notion_service._build_page_properties(
        schema=schema,
        concept="Dinner",
        amount=100.50,
        currency="EUR",
        category="Dining",
        timestamp=timestamp,
        user_name="Alice"
    )
    
    assert "Name" in props
    assert props["Name"]["title"][0]["text"]["content"] == "Dinner"
    assert "Cost" in props
    assert props["Cost"]["number"] == 100.50
    assert "Tags" in props
    assert props["Tags"]["multi_select"][0]["name"] == "Dining"
    assert "When" in props
    assert props["When"]["date"]["start"] == timestamp.isoformat()
    assert "Who" in props
    assert props["Who"]["select"]["name"] == "Alice"

@pytest.mark.anyio
@patch("src.services.notion_service.AsyncClient")
async def test_test_connection_mirror(mock_client_cls, notion_service, family, session):
    family.notion_api_key = notion_service.encryption.encrypt("test_token")
    family.notion_database_id = "test_db_id"
    family.notion_database_name = "My DB"
    session.add(family)
    session.commit()

    mock_notion = MagicMock()
    mock_client_cls.return_value.__aenter__.return_value = mock_notion

    notion_service.get_database_details = AsyncMock(return_value={
        "id": "test_db_id",
        "title": "My DB",
        "properties_schema": {"Name": {"type": "title"}}
    })

    async def mock_create(**kwargs):
        return {"id": "page_456", "url": "http://notion.so/page_456"}
    mock_notion.pages.create.side_effect = mock_create

    result = await notion_service.test_connection_mirror(family.id)
    assert result["database_name"] == "My DB"
    assert result["page_url"] == "http://notion.so/page_456"
