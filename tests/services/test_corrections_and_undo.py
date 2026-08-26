import pytest
from uuid import uuid4
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock
from sqlmodel import Session, SQLModel, create_engine, select
from sqlalchemy.pool import StaticPool

from src.db.models import Family, User, Transaction
from src.core.encryption import EncryptionService
from src.services.ai_orchestrator import AIOrchestrator
from src.services.query_service import ParsedQueryIntent
from src.services.notion_service import NotionService

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

def test_handle_transaction_undo_success(db_setup):
    orchestrator = AIOrchestrator()
    user_id = db_setup["user_id"]
    family_id = db_setup["family_id"]
    encryption = db_setup["encryption"]
    test_engine = db_setup["engine"]
    
    # Create an initial transaction
    with Session(test_engine) as session:
        tx = Transaction(
            id=uuid4(),
            user_id=user_id,
            family_id=family_id,
            amount=encryption.encrypt("45.00 USD"),
            concept=encryption.encrypt("Lunch with team"),
            category="Food/Drink",
            type="expense",
            timestamp=datetime.now(timezone.utc)
        )
        session.add(tx)
        session.commit()
        tx_id = tx.id
        
    # Execute undo
    result = orchestrator._handle_transaction_undo(user_id)
    
    assert "Removed latest transaction:" in result
    assert "Lunch with team" in result
    assert "45.00" in result
    
    # Verify deleted from DB
    with Session(test_engine) as session:
        deleted_tx = session.get(Transaction, tx_id)
        assert deleted_tx is None

def test_handle_transaction_undo_empty(db_setup):
    orchestrator = AIOrchestrator()
    fresh_user_id = uuid4()
    
    result = orchestrator._handle_transaction_undo(fresh_user_id)
    assert "You don't have any recent transactions to undo" in result

def test_handle_transaction_correction_type_toggle(db_setup):
    orchestrator = AIOrchestrator()
    user_id = db_setup["user_id"]
    family_id = db_setup["family_id"]
    encryption = db_setup["encryption"]
    test_engine = db_setup["engine"]
    
    # Create an expense transaction
    with Session(test_engine) as session:
        tx = Transaction(
            id=uuid4(),
            user_id=user_id,
            family_id=family_id,
            amount=encryption.encrypt("3500.00 USD"),
            concept=encryption.encrypt("Acme Corp Salary"),
            category="Other",
            type="expense",
            timestamp=datetime.now(timezone.utc)
        )
        session.add(tx)
        session.commit()
        tx_id = tx.id
        
    # Apply correction: switch to income
    parsed_edit = ParsedQueryIntent(intent="edit_last", new_type="income", new_category="Salary")
    result = orchestrator._handle_transaction_correction(user_id, parsed_edit)
    
    assert "Updated latest transaction:" in result
    assert "Switched from Expense 💸 to Income 💰" in result
    assert "+$3,500.00" in result
    assert "Salary" in result
    
    # Verify in DB
    with Session(test_engine) as session:
        updated_tx = session.get(Transaction, tx_id)
        assert updated_tx.type == "income"
        assert updated_tx.tx_type == "income"
        assert updated_tx.category == "Salary"

def test_handle_transaction_correction_amount_and_concept(db_setup):
    orchestrator = AIOrchestrator()
    user_id = db_setup["user_id"]
    family_id = db_setup["family_id"]
    encryption = db_setup["encryption"]
    test_engine = db_setup["engine"]
    
    with Session(test_engine) as session:
        tx = Transaction(
            id=uuid4(),
            user_id=user_id,
            family_id=family_id,
            amount=encryption.encrypt("50.00 USD"),
            concept=encryption.encrypt("Old Concept"),
            category="Shopping",
            type="expense",
            timestamp=datetime.now(timezone.utc)
        )
        session.add(tx)
        session.commit()
        tx_id = tx.id
        
    parsed_edit = ParsedQueryIntent(intent="edit_last", new_amount=75.50, new_concept="New Concept", new_category="Leisure")
    result = orchestrator._handle_transaction_correction(user_id, parsed_edit)
    
    assert "Updated latest transaction:" in result
    assert "75.50" in result
    assert "New Concept" in result
    assert "Leisure" in result
    
    with Session(test_engine) as session:
        updated_tx = session.get(Transaction, tx_id)
        assert encryption.decrypt(updated_tx.amount) == "75.50 USD"
        assert encryption.decrypt(updated_tx.concept) == "New Concept"
        assert updated_tx.category == "Leisure"

def test_handle_transaction_correction_empty(db_setup):
    orchestrator = AIOrchestrator()
    fresh_user_id = uuid4()
    
    parsed_edit = ParsedQueryIntent(intent="edit_last", new_type="income")
    result = orchestrator._handle_transaction_correction(fresh_user_id, parsed_edit)
    assert "You don't have any recent transactions to update" in result

@pytest.mark.anyio
async def test_orchestrate_undo_fast_regex(db_setup):
    orchestrator = AIOrchestrator()
    user_id = db_setup["user_id"]
    family_id = db_setup["family_id"]
    encryption = db_setup["encryption"]
    test_engine = db_setup["engine"]
    
    with Session(test_engine) as session:
        tx = Transaction(
            id=uuid4(),
            user_id=user_id,
            family_id=family_id,
            amount=encryption.encrypt("20.00 USD"),
            concept=encryption.encrypt("Coffee and bagel"),
            category="Food/Drink",
            type="expense",
            timestamp=datetime.now(timezone.utc)
        )
        session.add(tx)
        session.commit()
        tx_id = tx.id
        
    with patch("src.services.telegram_service.TelegramService.send_message", new_callable=AsyncMock) as mock_send:
        await orchestrator.orchestrate(
            user_id=str(user_id),
            text="undo last",
            audio_file_id=None,
            chat_id=12345
        )
        
        mock_send.assert_called_once()
        call_args = mock_send.call_args[1]
        assert "Removed latest transaction" in call_args["text"]
        
    with Session(test_engine) as session:
        assert session.get(Transaction, tx_id) is None

@pytest.mark.anyio
async def test_orchestrate_edit_fast_regex(db_setup):
    orchestrator = AIOrchestrator()
    user_id = db_setup["user_id"]
    family_id = db_setup["family_id"]
    encryption = db_setup["encryption"]
    test_engine = db_setup["engine"]
    
    with Session(test_engine) as session:
        tx = Transaction(
            id=uuid4(),
            user_id=user_id,
            family_id=family_id,
            amount=encryption.encrypt("1500.00 USD"),
            concept=encryption.encrypt("Freelance Web Project"),
            category="Other",
            type="expense",
            timestamp=datetime.now(timezone.utc)
        )
        session.add(tx)
        session.commit()
        tx_id = tx.id
        
    with patch("src.services.telegram_service.TelegramService.send_message", new_callable=AsyncMock) as mock_send:
        await orchestrator.orchestrate(
            user_id=str(user_id),
            text="change last one to income",
            audio_file_id=None,
            chat_id=12345
        )
        
        mock_send.assert_called_once()
        call_args = mock_send.call_args[1]
        assert "Updated latest transaction" in call_args["text"]
        assert "Switched from Expense 💸 to Income 💰" in call_args["text"]

@pytest.mark.anyio
async def test_notion_update_and_archive_methods(db_setup):
    encryption = db_setup["encryption"]
    family_id = uuid4()
    test_engine = db_setup["engine"]
    
    with Session(test_engine) as session:
        family = Family(
            id=family_id,
            name="Notion Family",
            notion_api_key=encryption.encrypt("secret_test_token"),
            notion_database_id="db_12345"
        )
        session.add(family)
        session.commit()
        
        notion_service = NotionService(session)
        
        with patch("src.services.notion_service.AsyncClient") as MockNotionClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.pages.update = AsyncMock(return_value={"id": "page_999"})
            MockNotionClient.return_value.__aenter__.return_value = mock_client_instance
            
            with patch.object(notion_service, "get_database_details", new_callable=AsyncMock) as mock_details:
                mock_details.return_value = {"properties_schema": {"Name": {"type": "title"}}}
                
                # Test update
                success_update = await notion_service.update_transaction_page(
                    family_id=family_id,
                    page_id="page_999",
                    amount=120.0,
                    currency="USD",
                    concept="Updated Concept",
                    category="Shopping",
                    timestamp=datetime.now(timezone.utc),
                    user_name="Tester",
                    tx_type="expense"
                )
                assert success_update is True
                mock_client_instance.pages.update.assert_called()
                
                # Test archive
                success_archive = await notion_service.archive_transaction_page(
                    family_id=family_id,
                    page_id="page_999"
                )
                assert success_archive is True
                mock_client_instance.pages.update.assert_called_with(page_id="page_999", archived=True)
