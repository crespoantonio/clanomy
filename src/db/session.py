import os
import logging
from sqlmodel import create_engine, Session, SQLModel
from alembic.config import Config
from alembic import command
from src.core.config import settings
from src.db.models import Family, User, Transaction, FamilyInvite  # Ensure models are registered

logger = logging.getLogger(__name__)

# Create engine with resilient cloud connection pooling
engine_kwargs = {
    "echo": False,
    "pool_pre_ping": True,
}

if not settings.DATABASE_URL.startswith("sqlite"):
    engine_kwargs.update({
        "pool_recycle": 1800,
        "pool_size": 10,
        "max_overflow": 5,
        "pool_timeout": 30.0,
    })
else:
    engine_kwargs.update({
        "connect_args": {"check_same_thread": False}
    })

engine = create_engine(settings.DATABASE_URL, **engine_kwargs)

def run_migrations():
    """
    Executes pending Alembic database migrations programmatically on application startup.
    Ensures Local, QA, and Production databases are automatically upgraded to 'head'.
    """
    try:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        alembic_ini_path = os.path.join(base_dir, "alembic.ini")
        
        if not os.path.exists(alembic_ini_path):
            raise FileNotFoundError(f"alembic.ini not found at {alembic_ini_path}")
            
        alembic_cfg = Config(alembic_ini_path)
        # Escape % as %% because Alembic uses Python configparser which interprets % as interpolation
        escaped_url = settings.DATABASE_URL.replace("%", "%%")
        alembic_cfg.set_main_option("sqlalchemy.url", escaped_url)
        logger.info("Running Alembic database migrations (upgrade head)...")
        command.upgrade(alembic_cfg, "head")
        logger.info("Alembic database migrations completed successfully.")
    except Exception as e:
        from src.core.security import sanitize_exception_message
        sanitized_msg = sanitize_exception_message(e, settings.DATABASE_URL)
        logger.critical(f"Alembic database migration failed: {sanitized_msg}")
        raise RuntimeError(f"Database migration failed: {sanitized_msg}") from None

def init_db():
    # Create all tables defined in models.py (fallback / test suites)
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
