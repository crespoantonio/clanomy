from sqlmodel import create_engine, Session, SQLModel
from src.core.config import settings
from src.db.models import Family, User, Transaction, FamilyInvite # Ensure models are registered

# Create engine
# Note: check_same_thread is only needed for SQLite
engine = create_engine(settings.DATABASE_URL, echo=True)

def init_db():
    # Create all tables defined in models.py
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
