import pytest
import os
import csv
import json
from uuid import uuid4
from datetime import datetime, timezone
from sqlmodel import create_engine, Session, SQLModel

from src.db.models import Family, User, Transaction
from src.core.encryption import EncryptionService
from src.services.export_service import ExportService
from src.services.query_service import DecryptedTransaction

from sqlalchemy.pool import StaticPool

@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session

@pytest.fixture(autouse=True)
def reset_export_service():
    ExportService._instance = None
    yield
    ExportService._instance = None

@pytest.fixture
def encryption_service():
    service = EncryptionService()
    # Mock or use real? The real EncryptionService reads from settings.ENCRYPTION_KEY
    # It's better to use real or a fixture that configures a dummy key
    return service

@pytest.fixture
def test_family(session):
    family = Family()
    session.add(family)
    session.commit()
    session.refresh(family)
    return family

@pytest.fixture
def test_user(session, test_family):
    user = User(telegram_id=123, family_id=test_family.id)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user

def create_mock_transactions():
    t1 = DecryptedTransaction(
        id=uuid4(),
        family_id=uuid4(),
        user_id=uuid4(),
        timestamp=datetime.now(timezone.utc),
        amount=15.50,
        currency="USD",
        category="Food/Drink",
        concept="Coffee with friends"
    )
    t2 = DecryptedTransaction(
        id=uuid4(),
        family_id=uuid4(),
        user_id=uuid4(),
        timestamp=datetime.now(timezone.utc),
        amount=100.0,
        currency="EUR",
        category="Shopping",
        concept='Sneakers "Nike", cool'
    )
    return [t1, t2]

@pytest.mark.anyio
async def test_generate_csv(tmp_path, session):
    service = ExportService(engine_override=session.bind)
    file_path = str(tmp_path / "test.csv")
    transactions = create_mock_transactions()
    
    service.generate_csv(transactions, file_path)
    
    assert os.path.exists(file_path)
    with open(file_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)
        
    assert len(rows) == 3 # header + 2 records
    assert rows[0] == ["Timestamp (UTC)", "Amount", "Currency", "Category", "Concept"]
    assert rows[1][1] == "15.5"
    assert rows[1][2] == "USD"
    assert rows[1][4] == "Coffee with friends"
    assert rows[2][4] == 'Sneakers "Nike", cool' # quotes handling

@pytest.mark.anyio
async def test_generate_json(tmp_path, session):
    service = ExportService(engine_override=session.bind)
    file_path = str(tmp_path / "test.json")
    transactions = create_mock_transactions()
    family_id = uuid4()
    
    service.generate_json(transactions, family_id, file_path)
    
    assert os.path.exists(file_path)
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    assert data["family_id"] == str(family_id)
    assert "exported_at" in data
    assert data["total_count"] == 2
    assert len(data["transactions"]) == 2
    assert data["transactions"][0]["amount"] == 15.5
    assert data["transactions"][0]["currency"] == "USD"

@pytest.mark.anyio
async def test_export_data_isolation(session, encryption_service, test_family, test_user):
    # Setup test data in DB
    amount_encrypted = encryption_service.encrypt("10.0 USD")
    concept_encrypted = encryption_service.encrypt("Test")
    tx = Transaction(
        family_id=test_family.id,
        user_id=test_user.id,
        amount=amount_encrypted,
        concept=concept_encrypted,
        category="Other",
        timestamp=datetime.now(timezone.utc)
    )
    session.add(tx)
    session.commit()
    
    service = ExportService(engine_override=session.bind)
    file_path, count = await service.export_data(test_family.id, "json")
    
    assert count == 1
    assert os.path.exists(file_path)
    os.unlink(file_path) # Cleanup

@pytest.mark.anyio
async def test_export_and_send_cleanup(session, test_family):
    service = ExportService(engine_override=session.bind)
    # mock telegram_service
    from unittest.mock import AsyncMock
    service.telegram_service = AsyncMock()
    
    await service.export_and_send(test_family.id, 123, "csv")
    
    # Check that temp file is deleted (no file leaks)
    service.telegram_service.send_document.assert_called_once()
    file_path = service.telegram_service.send_document.call_args.kwargs["file_path"]
    assert not os.path.exists(file_path)

@pytest.mark.anyio
async def test_export_and_send_cleanup_on_exception(session, test_family, monkeypatch):
    service = ExportService(engine_override=session.bind)
    from unittest.mock import AsyncMock
    mock_send = AsyncMock(side_effect=Exception("Telegram Error"))
    service.telegram_service = AsyncMock()
    service.telegram_service.send_document = mock_send
    
    # Track temp file path
    temp_files = []
    original_mkstemp = __import__('tempfile').mkstemp
    def mock_mkstemp(*args, **kwargs):
        fd, path = original_mkstemp(*args, **kwargs)
        temp_files.append(path)
        return fd, path
    
    monkeypatch.setattr("tempfile.mkstemp", mock_mkstemp)
    
    await service.export_and_send(test_family.id, 123, "csv")
    
    assert len(temp_files) == 1
    assert not os.path.exists(temp_files[0])
