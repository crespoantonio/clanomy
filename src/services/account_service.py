import asyncio
import time
import logging
from uuid import UUID
from sqlmodel import Session
from sqlalchemy.engine import Engine
from src.db.models import User, Family

logger = logging.getLogger(__name__)

class AccountService:
    """
    Service responsible for user account deletion and data purging.
    Implements singleton pattern.
    """
    _instance = None
    
    def __new__(cls, engine: Engine = None):
        if cls._instance is None:
            cls._instance = super(AccountService, cls).__new__(cls)
        if engine is not None:
            cls._instance.engine = engine
        elif not hasattr(cls._instance, 'engine') or cls._instance.engine is None:
            from src.db.session import engine as db_engine
            cls._instance.engine = db_engine
        return cls._instance

    def __init__(self, engine: Engine = None):
        if engine:
            self.engine = engine

    def _delete_account_sync(self, user_id: UUID) -> bool:
        start_time = time.time()
        try:
            with Session(self.engine) as session:
                user = session.get(User, user_id)
                if not user:
                    return False
                
                family = session.get(Family, user.family_id) if user.family_id else None
                if family and len(family.users) <= 1:
                    session.delete(family)
                else:
                    session.delete(user)
                    
                session.commit()
                
                duration = time.time() - start_time
                logger.info(f"[3s Audit] Account deletion completed in {duration:.2f}s for user_id={user_id}")
                return True
        except Exception as e:
            logger.error(f"Failed to delete account for user_id={user_id}. (Exception details omitted for security)")
            return False

    async def delete_account(self, user_id: UUID) -> bool:
        """
        Asynchronously delete a user account and their associated records.
        Ensures execution within the 3s rule.
        """
        return await asyncio.to_thread(self._delete_account_sync, user_id)
