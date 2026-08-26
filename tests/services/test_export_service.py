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
        user_name="user1",
        timestamp=datetime.now(timezone.utc),
        amount=15.50,
        currency="USD",
        category="Food/Drink",
        concept="Coffee with friends",
        type="expense"
    )
    t2 = DecryptedTransaction(
        id=uuid4(),
        family_id=uuid4(),
        user_id=uuid4(),
        user_name="user2",
        timestamp=datetime.now(timezone.utc),
        amount=100.0,
        currency="EUR",
        category="Shopping",
        concept='Sneakers "Nike", cool',
        type="expense"
    )
    t3 = DecryptedTransaction(
        id=uuid4(),
        family_id=uuid4(),
        user_id=uuid4(),
        user_name="user2",
        timestamp=datetime.now(timezone.utc),
        amount=3500.0,
        currency="EUR",
        category="Salary",
        concept='Monthly "Acme" Paycheck',
        type="income"
    )
    return [t1, t2, t3]

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
        
    assert len(rows) == 4 # header + 3 records
    assert rows[0] == ["Date", "Type", "Amount", "Currency", "Concept", "Category"]
    assert rows[1][1] == "expense"
    assert rows[1][2] == "15.5"
    assert rows[1][3] == "USD"
    assert rows[1][4] == "Coffee with friends"
    assert rows[1][5] == "Food/Drink"
    assert rows[2][1] == "expense"
    assert rows[2][2] == "100.0"
    assert rows[2][3] == "EUR"
    assert rows[2][4] == 'Sneakers "Nike", cool'
    assert rows[2][5] == "Shopping"
    assert rows[3][1] == "income"
    assert rows[3][2] == "3500.0"
    assert rows[3][3] == "EUR"
    assert rows[3][4] == 'Monthly "Acme" Paycheck'
    assert rows[3][5] == "Salary"

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
    assert "transactions" in data
    assert len(data["transactions"]) == 3
    assert data["transactions"][0]["type"] == "expense"
    assert data["transactions"][0]["amount"] == 15.5
    assert data["transactions"][0]["concept"] == "Coffee with friends"
    assert data["transactions"][0]["logged_by"] == "user1"
    assert "user_id" in data["transactions"][0]
    assert data["transactions"][1]["type"] == "expense"
    assert data["transactions"][1]["amount"] == 100.0
    assert data["transactions"][2]["type"] == "income"
    assert data["transactions"][2]["amount"] == 3500.0
    assert data["transactions"][2]["category"] == "Salary"

def test_decrypt_transaction_with_type(session, encryption_service, test_family, test_user):
    service = ExportService(engine_override=session.bind)
    
    tx_exp = Transaction(
        family_id=test_family.id,
        user_id=test_user.id,
        amount=encryption_service.encrypt("50.0 USD"),
        concept=encryption_service.encrypt("Dinner"),
        category="Dining",
        tx_type="expense",
        timestamp=datetime.now(timezone.utc)
    )
    tx_inc = Transaction(
        family_id=test_family.id,
        user_id=test_user.id,
        amount=encryption_service.encrypt("2500.0 USD"),
        concept=encryption_service.encrypt("Consulting Fee"),
        category="Consulting",
        tx_type="income",
        timestamp=datetime.now(timezone.utc)
    )
    session.add_all([tx_exp, tx_inc])
    session.commit()
    session.refresh(tx_exp)
    session.refresh(tx_inc)
    
    fetched_exp = session.get(Transaction, tx_exp.id)
    fetched_inc = session.get(Transaction, tx_inc.id)
    
    dtx_exp = service._decrypt_transaction(fetched_exp, "Alice")
    dtx_inc = service._decrypt_transaction(fetched_inc, "Alice")
    
    assert dtx_exp is not None
    assert dtx_exp.type == "expense"
    assert dtx_exp.amount == 50.0
    assert dtx_exp.concept == "Dinner"
    
    assert dtx_inc is not None
    assert dtx_inc.type == "income"
    assert dtx_inc.amount == 2500.0
    assert dtx_inc.concept == "Consulting Fee"

@pytest.mark.anyio
async def test_export_data_mixed_transactions(session, encryption_service, test_family, test_user):
    tx_exp = Transaction(
        family_id=test_family.id,
        user_id=test_user.id,
        amount=encryption_service.encrypt("20.0 USD"),
        concept=encryption_service.encrypt("Snacks"),
        category="Food",
        tx_type="expense",
        timestamp=datetime.now(timezone.utc)
    )
    tx_inc = Transaction(
        family_id=test_family.id,
        user_id=test_user.id,
        amount=encryption_service.encrypt("1000.0 USD"),
        concept=encryption_service.encrypt("Bonus"),
        category="Bonus",
        tx_type="income",
        timestamp=datetime.now(timezone.utc)
    )
    session.add_all([tx_exp, tx_inc])
    session.commit()
    
    service = ExportService(engine_override=session.bind)
    file_path, count = await service.export_data(test_family.id, "csv")
    
    assert count == 2
    assert os.path.exists(file_path)
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    os.unlink(file_path)
    
    assert "Date,Type,Amount,Currency,Concept,Category" in content
    assert "expense" in content
    assert "income" in content

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
