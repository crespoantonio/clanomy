import pytest
from sqlmodel import Session, SQLModel, create_engine, select
from src.db.models import Family, User, Transaction
import uuid
from datetime import datetime, timezone

# Setup in-memory SQLite for testing models
@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session

def test_create_family(session: Session):
    family = Family(name="Test Family")
    session.add(family)
    session.commit()
    session.refresh(family)
    
    assert family.id is not None
    assert isinstance(family.id, uuid.UUID)
    assert family.name == "Test Family"

def test_family_notion_fields(session: Session):
    family = Family(
        name="Notion Family",
        notion_api_key="encrypted_key",
        notion_database_id="db_id_123",
        notion_database_name="Budget DB",
        notion_connected_at=datetime.now(timezone.utc)
    )
    session.add(family)
    session.commit()
    session.refresh(family)

    assert family.notion_api_key == "encrypted_key"
    assert family.notion_database_id == "db_id_123"
    assert family.notion_database_name == "Budget DB"
    assert family.notion_connected_at is not None

def test_create_user_in_family(session: Session):
    family = Family(name="Smiths")
    session.add(family)
    session.commit()
    
    user = User(
        telegram_id=123456789,
        username="john_smith",
        family_id=family.id
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    
    assert user.id is not None
    assert user.family_id == family.id
    assert user.family.name == "Smiths"
    assert len(family.users) == 1

def test_create_transaction(session: Session):
    family = Family(name="Budget Family")
    session.add(family)
    session.commit()
    
    user = User(telegram_id=999, family_id=family.id)
    session.add(user)
    session.commit()
    
    # Ciphertext strings (simulating EncryptionService output)
    encrypted_amount = "gAAAAABm..."
    encrypted_concept = "gAAAAABn..."
    
    transaction = Transaction(
        family_id=family.id,
        user_id=user.id,
        amount=encrypted_amount,
        concept=encrypted_concept,
        category="Food",
        timestamp=datetime.now(timezone.utc)
    )
    session.add(transaction)
    session.commit()
    session.refresh(transaction)
    
    assert transaction.id is not None
    assert transaction.amount == encrypted_amount
    assert transaction.family_id == family.id
    assert transaction.user_id == user.id

def test_transaction_notion_fields(session: Session):
    family = Family(name="Notion Sync Family")
    session.add(family)
    session.commit()

    user = User(telegram_id=888, family_id=family.id)
    session.add(user)
    session.commit()

    synced_time = datetime.now(timezone.utc)
    transaction = Transaction(
        family_id=family.id,
        user_id=user.id,
        amount="enc_amount",
        concept="enc_concept",
        category="Transport",
        notion_page_id="page_12345",
        notion_synced_at=synced_time
    )
    session.add(transaction)
    session.commit()
    session.refresh(transaction)

    assert transaction.notion_page_id == "page_12345"
    assert transaction.notion_synced_at.replace(tzinfo=timezone.utc) == synced_time

def test_family_transaction_relationship(session: Session):
    family = Family(name="Relation Family")
    session.add(family)
    session.commit()
    
    user = User(telegram_id=1, family_id=family.id)
    session.add(user)
    
    t1 = Transaction(family_id=family.id, user_id=user.id, amount="10", concept="A", category="X")
    t2 = Transaction(family_id=family.id, user_id=user.id, amount="20", concept="B", category="Y")
    session.add(t1)
    session.add(t2)
    session.commit()
    
    session.refresh(family)
    assert len(family.transactions) == 2

def test_transaction_requires_family(session: Session):
    # This should fail if family_id is mandatory and no family is provided
    # Note: SQLModel/SQLAlchemy only enforces this on commit/flush if nullable=False
    with pytest.raises(Exception):
        t = Transaction(amount="10", concept="A", category="X")
        session.add(t)
        session.commit()

def test_cascade_delete_family(session: Session):
    family = Family(name="Cascade Family")
    session.add(family)
    session.commit()
    
    user1 = User(telegram_id=101, family_id=family.id)
    user2 = User(telegram_id=102, family_id=family.id)
    session.add(user1)
    session.add(user2)
    session.commit()
    
    t1 = Transaction(family_id=family.id, user_id=user1.id, amount="10", concept="A", category="X")
    t2 = Transaction(family_id=family.id, user_id=user2.id, amount="20", concept="B", category="Y")
    session.add(t1)
    session.add(t2)
    session.commit()
    
    # Verify records exist
    assert len(session.exec(select(User).where(User.family_id == family.id)).all()) == 2
    assert len(session.exec(select(Transaction).where(Transaction.family_id == family.id)).all()) == 2
    
    # Delete the family
    session.delete(family)
    session.commit()
    
    # Verify users and transactions are deleted due to relationship cascades
    assert len(session.exec(select(User).where(User.family_id == family.id)).all()) == 0
    assert len(session.exec(select(Transaction).where(Transaction.family_id == family.id)).all()) == 0

def test_cascade_delete_user(session: Session):
    family = Family(name="Cascade User Family")
    session.add(family)
    session.commit()
    
    user = User(telegram_id=201, family_id=family.id)
    session.add(user)
    session.commit()
    
    t1 = Transaction(family_id=family.id, user_id=user.id, amount="10", concept="A", category="X")
    t2 = Transaction(family_id=family.id, user_id=user.id, amount="20", concept="B", category="Y")
    session.add(t1)
    session.add(t2)
    session.commit()
    
    # Delete the user
    session.delete(user)
    session.commit()
    
    # Verify transactions for this user are deleted
    assert len(session.exec(select(Transaction).where(Transaction.user_id == user.id)).all()) == 0

def test_create_family_invite(session: Session):
    family = Family(name="Invite Family")
    session.add(family)
    session.commit()
    
    user = User(telegram_id=301, family_id=family.id)
    session.add(user)
    session.commit()
    
    from src.db.models import FamilyInvite
    invite = FamilyInvite(
        family_id=family.id,
        created_by_user_id=user.id,
        token="test_token_123",
        expires_at=datetime.now(timezone.utc)
    )
    session.add(invite)
    session.commit()
    session.refresh(invite)
    
    assert invite.id is not None
    assert invite.token == "test_token_123"
    assert invite.family_id == family.id
    assert invite.created_by_user_id == user.id

def test_cascade_delete_family_invites(session: Session):
    family = Family(name="Invite Cascade Family")
    session.add(family)
    session.commit()
    
    user = User(telegram_id=302, family_id=family.id)
    session.add(user)
    session.commit()
    
    from src.db.models import FamilyInvite
    invite = FamilyInvite(
        family_id=family.id,
        created_by_user_id=user.id,
        token="test_token_cascade",
        expires_at=datetime.now(timezone.utc)
    )
    session.add(invite)
    session.commit()
    
    # Delete the family
    session.delete(family)
    session.commit()
    
    # Verify invite is deleted
    assert len(session.exec(select(FamilyInvite).where(FamilyInvite.family_id == family.id)).all()) == 0

def test_transaction_default_type_is_expense(session: Session):
    family = Family(name="Default Type Family")
    session.add(family)
    session.commit()

    user = User(telegram_id=401, family_id=family.id)
    session.add(user)
    session.commit()

    tx = Transaction(
        family_id=family.id,
        user_id=user.id,
        amount="enc_100",
        concept="enc_groceries",
        category="Food",
    )
    session.add(tx)
    session.commit()
    session.refresh(tx)

    assert tx.type == "expense"

def test_transaction_explicit_income_type(session: Session):
    family = Family(name="Income Type Family")
    session.add(family)
    session.commit()

    user = User(telegram_id=402, family_id=family.id)
    session.add(user)
    session.commit()

    tx = Transaction(
        family_id=family.id,
        user_id=user.id,
        amount="enc_3000",
        concept="enc_salary",
        category="Income",
        tx_type="income"
    )
    session.add(tx)
    session.commit()
    session.refresh(tx)

    assert tx.type == "income"

def test_transaction_query_by_type(session: Session):
    family = Family(name="Filter Type Family")
    session.add(family)
    session.commit()

    user = User(telegram_id=403, family_id=family.id)
    session.add(user)
    session.commit()

    t_exp1 = Transaction(family_id=family.id, user_id=user.id, amount="enc_10", concept="enc_Lunch", category="Food", tx_type="expense")
    t_exp2 = Transaction(family_id=family.id, user_id=user.id, amount="enc_20", concept="enc_Uber", category="Transport", tx_type="expense")
    t_inc1 = Transaction(family_id=family.id, user_id=user.id, amount="enc_1000", concept="enc_Bonus", category="Income", tx_type="income")
    t_inc2 = Transaction(family_id=family.id, user_id=user.id, amount="enc_2500", concept="enc_Salary", category="Income", tx_type="income")

    session.add_all([t_exp1, t_exp2, t_inc1, t_inc2])
    session.commit()

    expenses = session.exec(select(Transaction).where(Transaction.family_id == family.id, Transaction.type == "expense")).all()
    incomes = session.exec(select(Transaction).where(Transaction.family_id == family.id, Transaction.type == "income")).all()

    assert len(expenses) == 2
    assert {t.concept for t in expenses} == {"enc_Lunch", "enc_Uber"}
    assert len(incomes) == 2
    assert {t.concept for t in incomes} == {"enc_Bonus", "enc_Salary"}

def test_transaction_type_with_encryption(session: Session):
    from src.core.encryption import EncryptionService
    enc = EncryptionService()

    family = Family(name="Encrypted Type Family")
    session.add(family)
    session.commit()

    user = User(telegram_id=404, family_id=family.id)
    session.add(user)
    session.commit()

    expense_tx = Transaction(
        family_id=family.id,
        user_id=user.id,
        amount=enc.encrypt("45.50"),
        concept=enc.encrypt("Dinner with friends"),
        category="Dining",
        tx_type="expense"
    )
    income_tx = Transaction(
        family_id=family.id,
        user_id=user.id,
        amount=enc.encrypt("5000.00"),
        concept=enc.encrypt("Monthly Consulting"),
        category="Consulting",
        tx_type="income"
    )
    session.add_all([expense_tx, income_tx])
    session.commit()

    # Query back and verify decryption
    saved_expense = session.exec(select(Transaction).where(Transaction.id == expense_tx.id)).first()
    saved_income = session.exec(select(Transaction).where(Transaction.id == income_tx.id)).first()

    assert saved_expense is not None
    assert saved_expense.type == "expense"
    assert enc.decrypt(saved_expense.amount) == "45.50"
    assert enc.decrypt(saved_expense.concept) == "Dinner with friends"

    assert saved_income is not None
    assert saved_income.type == "income"
    assert enc.decrypt(saved_income.amount) == "5000.00"
    assert enc.decrypt(saved_income.concept) == "Monthly Consulting"

def test_cascade_delete_income_and_expense_transactions(session: Session):
    family = Family(name="Cascade Both Types Family")
    session.add(family)
    session.commit()

    user = User(telegram_id=405, family_id=family.id)
    session.add(user)
    session.commit()

    t_exp = Transaction(family_id=family.id, user_id=user.id, amount="50", concept="Groceries", category="Food", tx_type="expense")
    t_inc = Transaction(family_id=family.id, user_id=user.id, amount="1500", concept="Freelance", category="Income", tx_type="income")
    session.add_all([t_exp, t_inc])
    session.commit()

    assert len(session.exec(select(Transaction).where(Transaction.family_id == family.id)).all()) == 2

    # Delete family, should cascade delete both
    session.delete(family)
    session.commit()

    assert len(session.exec(select(Transaction).where(Transaction.family_id == family.id)).all()) == 0



def test_cascade_delete_user_income_and_expense_transactions(session: Session):
    family = Family(name="Cascade User Both Types Family")
    session.add(family)
    session.commit()

    user = User(telegram_id=406, family_id=family.id)
    session.add(user)
    session.commit()

    t_exp = Transaction(family_id=family.id, user_id=user.id, amount="enc_50", concept="enc_Groceries", category="Food", tx_type="expense")
    t_inc = Transaction(family_id=family.id, user_id=user.id, amount="enc_1500", concept="enc_Freelance", category="Income", tx_type="income")
    session.add_all([t_exp, t_inc])
    session.commit()

    assert len(session.exec(select(Transaction).where(Transaction.user_id == user.id)).all()) == 2

    session.delete(user)
    session.commit()

    assert len(session.exec(select(Transaction).where(Transaction.user_id == user.id)).all()) == 0


def test_family_subscription_fields_persistence(session: Session):
    trial_end = datetime(2026, 10, 25, 12, 0, 0, tzinfo=timezone.utc)
    family = Family(
        name="Subscription Family",
        plan_type="trial",
        subscription_status="active",
        monthly_tx_count=12,
        last_reset_month="2026-08",
        max_members=5,
        trial_ends_at=trial_end,
        telegram_payment_charge_id="ch_12345",
        notified_day_50=True,
        notified_day_60=False,
    )
    session.add(family)
    session.commit()
    session.refresh(family)

    assert family.plan_type == "trial"
    assert family.subscription_status == "active"
    assert family.monthly_tx_count == 12
    assert family.last_reset_month == "2026-08"
    assert family.max_members == 5
    assert family.trial_ends_at is not None
    assert family.telegram_payment_charge_id == "ch_12345"
    assert family.notified_day_50 is True
    assert family.notified_day_60 is False


def test_user_has_used_trial_persistence(session: Session):
    family = Family(name="Trial User Family")
    session.add(family)
    session.commit()

    user = User(
        telegram_id=501,
        username="trial_user",
        family_id=family.id,
        has_used_trial=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    assert user.has_used_trial is True

