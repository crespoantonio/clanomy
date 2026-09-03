import os
import pytest
from alembic.config import Config
from alembic import command
from sqlmodel import create_engine, text, Session
from src.db.session import run_migrations
from src.core.config import settings

def test_alembic_ini_exists():
    """Verify that alembic.ini is present in the repository root."""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    alembic_ini = os.path.join(base_dir, "alembic.ini")
    assert os.path.exists(alembic_ini), f"alembic.ini not found at {alembic_ini}"

def test_alembic_script_location():
    """Verify Alembic config recognizes the alembic directory."""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    alembic_ini = os.path.join(base_dir, "alembic.ini")
    cfg = Config(alembic_ini)
    assert cfg.get_main_option("script_location") == "alembic"

def test_run_migrations_sqlite_isolated(tmp_path):
    """Verify programmatic migration execution against an isolated SQLite database."""
    test_db_path = tmp_path / "test_migration.db"
    test_db_url = f"sqlite:///{test_db_path}"
    
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    alembic_ini = os.path.join(base_dir, "alembic.ini")
    
    cfg = Config(alembic_ini)
    cfg.set_main_option("sqlalchemy.url", test_db_url)
    
    # Run upgrade head
    command.upgrade(cfg, "head")
    
    # Connect and verify alembic_version and tables exist
    test_engine = create_engine(test_db_url)
    with Session(test_engine) as session:
        # Check alembic_version table
        version_result = session.exec(text("SELECT version_num FROM alembic_version")).one()
        assert version_result[0] == "0010_add_family_daily_tx_count"
        
        # Check family table
        family_cols = session.exec(text("PRAGMA table_info(family)")).all()
        col_names = [col[1] for col in family_cols]
        assert "id" in col_names
        assert "plan_type" in col_names
        assert "subscription_status" in col_names
        assert "monthly_tx_count" in col_names
        assert "daily_tx_count" in col_names
        assert "last_reset_month" in col_names
        assert "max_members" in col_names
        assert "trial_ends_at" in col_names
        assert "notified_day_50" in col_names
        assert "notified_day_60" in col_names
        assert "notion_database_id" in col_names
        assert "default_currency" in col_names
        assert "timezone" in col_names
        assert "lemonsqueezy_customer_id" in col_names
        assert "lemonsqueezy_subscription_id" in col_names
        assert "customer_portal_url" in col_names
        
        # Check user table
        user_cols = session.exec(text("PRAGMA table_info(user)")).all()
        user_col_names = [col[1] for col in user_cols]
        assert "telegram_id" in user_col_names
        assert "family_id" in user_col_names
        assert "has_used_trial" in user_col_names
        assert "is_admin" in user_col_names
        assert "timezone" in user_col_names
        
        # Check transaction table (quote 'transaction' for SQLite keyword safety)
        tx_cols = session.exec(text("PRAGMA table_info('transaction')")).all()
        tx_col_names = [col[1] for col in tx_cols]
        assert "type" in tx_col_names
        assert "category" in tx_col_names
        assert "amount" in tx_col_names

def test_run_migrations_helper_isolated(monkeypatch, tmp_path):
    """Verify run_migrations() helper executes cleanly with dynamic settings."""
    test_db_path = tmp_path / "test_helper.db"
    test_db_url = f"sqlite:///{test_db_path}"
    
    monkeypatch.setattr(settings, "DATABASE_URL", test_db_url)
    
    # Run helper function
    run_migrations()
    
    # Verify migration ran and created tables
    test_engine = create_engine(test_db_url)
    with Session(test_engine) as session:
        version_result = session.exec(text("SELECT version_num FROM alembic_version")).one()
        assert version_result[0] == "0010_add_family_daily_tx_count"

def test_run_migrations_with_percent_encoded_url(monkeypatch, tmp_path):
    """Verify run_migrations() handles database URLs with % encoding (e.g. passwords)."""
    test_db_path = tmp_path / "test_percent%40test.db"
    test_db_url = f"sqlite:///{test_db_path}"
    
    monkeypatch.setattr(settings, "DATABASE_URL", test_db_url)
    
    # Run helper function - should not raise configparser interpolation error
    run_migrations()
    
    test_engine = create_engine(test_db_url)
    with Session(test_engine) as session:
        version_result = session.exec(text("SELECT version_num FROM alembic_version")).one()
        assert version_result[0] == "0010_add_family_daily_tx_count"


