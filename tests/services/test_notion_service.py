import pytest
from uuid import uuid4
from unittest.mock import patch, MagicMock
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
