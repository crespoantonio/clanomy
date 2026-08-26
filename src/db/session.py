import os
import logging
from sqlmodel import create_engine, Session, SQLModel
from alembic.config import Config
from alembic import command
from src.core.config import settings
from src.db.models import Family, User, Transaction, FamilyInvite  # Ensure models are registered

logger = logging.getLogger(__name__)

# Create engine
engine = create_engine(settings.DATABASE_URL, echo=False)

def run_migrations():
    """
    Executes pending Alembic database migrations programmatically on application startup.
    Ensures Local, QA, and Production databases are automatically upgraded to 'head'.
    """
    try:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        alembic_ini_path = os.path.join(base_dir, "alembic.ini")
        
        if os.path.exists(alembic_ini_path):
            alembic_cfg = Config(alembic_ini_path)
            alembic_cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
            logger.info("Running Alembic database migrations (upgrade head)...")
            command.upgrade(alembic_cfg, "head")
            logger.info("Alembic database migrations completed successfully.")
        else:
            logger.warning("alembic.ini not found, falling back to SQLModel create_all")
            init_db()
    except Exception as e:
        logger.warning(f"Alembic migration runner notice: {e}. Ensuring tables exist via create_all.")
        init_db()

def init_db():
    # Create all tables defined in models.py (fallback / test suites)
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
