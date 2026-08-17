import asyncio
import secrets
import time
import logging
from uuid import UUID
from typing import Tuple, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from sqlmodel import Session, select
from sqlalchemy import Engine

from src.db.session import engine as default_engine
from src.db.models import Family, User, FamilyInvite, Transaction
from src.core.config import settings

logger = logging.getLogger(__name__)

class FamilyService:
    _instance = None
    
    def __new__(cls, engine: Engine = None):
        if cls._instance is None:
            cls._instance = super(FamilyService, cls).__new__(cls)
        if engine is not None:
            cls._instance.engine = engine
        elif not hasattr(cls._instance, 'engine') or cls._instance.engine is None:
            from src.db.session import engine as db_engine
            cls._instance.engine = db_engine
        return cls._instance

    def __init__(self, engine: Engine = None):
        if engine:
            self.engine = engine

    def _log_3s_audit(self, operation: str, start_time: float):
        elapsed = time.time() - start_time
        logger.info(f"[3s Audit] FamilyService.{operation} executed in {elapsed:.3f}s")
        if elapsed > 1.0:
            logger.warning(f"[3s Audit] FamilyService.{operation} exceeded 1.0s: {elapsed:.3f}s")

    def create_family(self, user_id: UUID, name: str) -> Family:
        """
        Creates a new family and associates the user with it.
        If user is in an empty single-member family, deletes it.
        """
        start_time = time.time()
        try:
            with Session(self.engine, expire_on_commit=False) as session:
                user = session.get(User, user_id)
                if not user:
                    raise ValueError("User not found")
                
                old_family_id = user.family_id
                old_family = session.get(Family, old_family_id) if old_family_id else None
                
                # Check if old family is empty single-member
                if old_family:
                    users_in_old = session.exec(select(User).where(User.family_id == old_family_id)).all()
                    txs_in_old = session.exec(select(Transaction).where(Transaction.family_id == old_family_id)).all()
                    is_empty_single = len(users_in_old) == 1 and len(txs_in_old) == 0
                else:
                    is_empty_single = False
                
                new_family = Family(name=name)
                session.add(new_family)
                session.flush() # Get new_family.id without committing
                
                user.family_id = new_family.id
                session.add(user)
                
                if is_empty_single and old_family:
                    session.delete(old_family)
                    
                session.commit()
                session.refresh(new_family)
                self._log_3s_audit("create_family", start_time)
                return new_family
        except Exception as e:
            logger.error(f"Failed to create family for user_id={user_id}: {e}")
            raise

    def create_invite(self, family_id: UUID, user_id: UUID, bot_username: str = None, ttl_hours: int = 48) -> Tuple[FamilyInvite, str]:
        start_time = time.time()
        token = secrets.token_urlsafe(16)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)
        
        with Session(self.engine, expire_on_commit=False) as session:
            invite = FamilyInvite(
                family_id=family_id,
                created_by_user_id=user_id,
                token=token,
                expires_at=expires_at
            )
            session.add(invite)
            session.commit()
            session.refresh(invite)
            
            # Construct link using resolved username
            resolved_bot = bot_username or getattr(settings, 'TELEGRAM_BOT_USERNAME', 'BotName') or 'BotName'
            link = f"https://t.me/{resolved_bot}?start=join_{token}"
            
            self._log_3s_audit("create_invite", start_time)
            return invite, link

    def join_family_via_invite(self, token: str, user_id: UUID) -> Tuple[bool, str, Optional[Family]]:
        start_time = time.time()
        try:
            with Session(self.engine, expire_on_commit=False) as session:
                invite = session.exec(select(FamilyInvite).where(FamilyInvite.token == token)).first()
                
                if not invite:
                    self._log_3s_audit("join_family_via_invite", start_time)
                    return False, "⚠️ This family invite link is invalid or has expired. Please ask a family member to generate a new invite link.", None
                    
                if not invite.is_active:
                    self._log_3s_audit("join_family_via_invite", start_time)
                    return False, "⚠️ This family invite link is invalid or has expired. Please ask a family member to generate a new invite link.", None
                    
                expires_at = invite.expires_at.replace(tzinfo=timezone.utc) if invite.expires_at.tzinfo is None else invite.expires_at
                if expires_at <= datetime.now(timezone.utc):
                    self._log_3s_audit("join_family_via_invite", start_time)
                    return False, "⚠️ This family invite link is invalid or has expired. Please ask a family member to generate a new invite link.", None
                    
                user = session.get(User, user_id)
                if not user:
                    self._log_3s_audit("join_family_via_invite", start_time)
                    return False, "User not found.", None
                    
                if user.family_id == invite.family_id:
                    self._log_3s_audit("join_family_via_invite", start_time)
                    return True, "You are already a member of this family!", session.get(Family, invite.family_id)
                    
                old_family_id = user.family_id
                old_family = session.get(Family, old_family_id) if old_family_id else None
                
                # Check if old family was single-member
                is_single_member = False
                if old_family:
                    users_in_old = session.exec(select(User).where(User.family_id == old_family_id)).all()
                    if len(users_in_old) == 1:
                        is_single_member = True
                
                # Reassign user family
                user.family_id = invite.family_id
                session.add(user)
                
                # Option 1: Migrate transactions if old family was single-member
                if is_single_member:
                    txs = session.exec(select(Transaction).where(Transaction.family_id == old_family_id)).all()
                    for tx in txs:
                        tx.family_id = invite.family_id
                        session.add(tx)
                
                # If old family was single-member, delete it since it is now empty
                if is_single_member and old_family:
                    session.delete(old_family)
                    
                session.commit()
                target_family = session.get(Family, invite.family_id)
                self._log_3s_audit("join_family_via_invite", start_time)
                
                msg = f"🎉 Welcome to <b>{target_family.name or 'your new family'}</b>, {user.full_name or user.username or 'User'}!\n\nYou have successfully joined the family ledger. All expenses you log will now be shared with your family."
                return True, msg, target_family
        except Exception as e:
            logger.error(f"Failed to join family via invite token={token} for user_id={user_id}: {e}")
            return False, "An unexpected error occurred while joining the family.", None

    def get_family_info(self, user_id: UUID) -> Dict[str, Any]:
        start_time = time.time()
        with Session(self.engine, expire_on_commit=False) as session:
            user = session.get(User, user_id)
            if not user or not user.family_id:
                raise ValueError("User not in a family")
                
            family = session.get(Family, user.family_id)
            users = session.exec(select(User).where(User.family_id == family.id)).all()
            txs_count = len(session.exec(select(Transaction).where(Transaction.family_id == family.id)).all())
            invites = session.exec(select(FamilyInvite).where(
                FamilyInvite.family_id == family.id, 
                FamilyInvite.is_active == True,
                FamilyInvite.expires_at > datetime.now(timezone.utc)
            )).all()
            
            members = []
            for u in users:
                members.append({
                    "username": u.username,
                    "full_name": u.full_name
                })
                
            self._log_3s_audit("get_family_info", start_time)
            return {
                "id": family.id,
                "name": family.name,
                "members": members,
                "transactions_count": txs_count,
                "active_invites_count": len(invites)
            }
