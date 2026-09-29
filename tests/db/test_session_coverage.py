import pytest
from unittest.mock import patch
from src.db.session import init_db, run_migrations, get_session

def test_init_db():
    with patch("sqlmodel.SQLModel.metadata.create_all") as mock_create:
        init_db()
        assert mock_create.call_count == 1

def test_run_migrations_file_not_found():
    with patch("os.path.exists", return_value=False), \
         pytest.raises(RuntimeError, match="Database migration failed"):
        run_migrations()

def test_run_migrations_general_failure():
    with patch("alembic.command.upgrade", side_effect=Exception("Migration crash")), \
         pytest.raises(RuntimeError, match="Database migration failed"):
        run_migrations()

def test_get_session():
    gen = get_session()
    sess = next(gen)
    assert sess is not None
    try:
        next(gen)
    except StopIteration:
        pass
