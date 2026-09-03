import asyncio
import secrets
import time
import logging
import threading
from uuid import UUID
from typing import Tuple, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from sqlmodel import Session, select
from sqlalchemy import Engine

from src.db.session import engine as default_engine
from src.db.models import Family, User, FamilyInvite, Transaction
from src.core.config import settings
from src.templates.telegram_messages import (
    LEAVE_FAMILY_ADMIN_ACTIVE_PRO_BLOCKED,
    format_leave_family_admin_prompt,
    format_leave_family_member_prompt,
)

logger = logging.getLogger(__name__)

class PlanLimitExceededError(ValueError):
    pass

class FamilyService:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, engine: Engine = None):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(FamilyService, cls).__new__(cls)
                cls._instance._custom_engine = None
            if engine is not None:
                cls._instance._custom_engine = engine
            return cls._instance

    def __init__(self, engine: Engine = None):
        if engine is not None:
            self._custom_engine = engine

    @property
    def engine(self) -> Engine:
        if getattr(self, "_custom_engine", None) is not None:
            return self._custom_engine
        from src.db.session import engine as db_engine
        return db_engine

    @engine.setter
    def engine(self, val: Engine):
        self._custom_engine = val

    def _log_3s_audit(self, operation: str, start_time: float):
        elapsed = time.time() - start_time
        logger.info(f"[3s Audit] FamilyService.{operation} executed in {elapsed:.3f}s")
        if elapsed > 1.0:
            logger.warning(f"[3s Audit] FamilyService.{operation} exceeded 1.0s: {elapsed:.3f}s")

    def is_family_admin(self, family_id: UUID, user_id: UUID) -> bool:
        """
        Identifies the workspace admin. The admin is either explicitly marked with is_admin=True
        or is the earliest created member in the family workspace.
        """
        with Session(self.engine) as session:
            user = session.get(User, user_id)
            if not user or user.family_id != family_id:
                return False
            if user.is_admin:
                return True
            first_user = session.exec(
                select(User).where(User.family_id == family_id).order_by(User.created_at.asc())
            ).first()
            return bool(first_user and first_user.id == user_id)

    def create_family(self, user_id: UUID, name: str) -> Family:
        """
        Creates a new family and associates the user with it.
        Provisions 60-day trial if user hasn't consumed one, otherwise creates on free plan.
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
                
                # Sybil defense: check trial status
                if not user.has_used_trial:
                    plan_type = "trial"
                    trial_ends_at = datetime.now(timezone.utc) + timedelta(days=60)
                    user.has_used_trial = True
                else:
                    plan_type = "free"
                    trial_ends_at = None

                new_family = Family(
                    name=name,
                    plan_type=plan_type,
                    trial_ends_at=trial_ends_at
                )
                session.add(new_family)
                session.flush() # Get new_family.id without committing
                
                user.family_id = new_family.id
                user.is_admin = True
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

    def create_invite(self, family_id: UUID, user_id: UUID, bot_username: str = None, ttl_hours: Optional[int] = None) -> Tuple[FamilyInvite, str]:
        start_time = time.time()
        hours = ttl_hours if ttl_hours is not None else getattr(settings, "FAMILY_INVITE_TTL_HOURS", 1)
        
        with Session(self.engine, expire_on_commit=False) as session:
            family = session.get(Family, family_id)
            if not family:
                raise ValueError("Workspace not found")
            if family.plan_type == "solo_pro":
                raise PlanLimitExceededError("Solo Pro plan only supports 1 user. Please upgrade to Duo Pro or Family Pro using /upgrade to invite members.")
            if family.plan_type == "duo_pro":
                current_members = len(session.exec(select(User).where(User.family_id == family_id)).all())
                if current_members >= 2:
                    raise PlanLimitExceededError("Duo Pro plan only supports up to 2 partners. Please upgrade to Family Pro using /upgrade to invite more members.")
            if family.plan_type == "family_pro":
                current_members = len(session.exec(select(User).where(User.family_id == family_id)).all())
                if current_members >= 5:
                    raise PlanLimitExceededError("Family Pro plan has reached its limit of 5 members.")

            token = secrets.token_urlsafe(16)
            expires_at = datetime.now(timezone.utc) + timedelta(hours=hours)
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
                
                target_family = session.get(Family, invite.family_id)
                if not target_family:
                    self._log_3s_audit("join_family_via_invite", start_time)
                    return False, "Workspace not found.", None

                if target_family.plan_type == "solo_pro":
                    self._log_3s_audit("join_family_via_invite", start_time)
                    return False, "⚠️ This workspace is on a Solo Pro plan (1 user limit) and cannot accept new members. The admin must upgrade to Duo Pro or Family Pro.", None

                if target_family.plan_type == "duo_pro":
                    member_count = len(session.exec(select(User).where(User.family_id == target_family.id)).all())
                    if member_count >= 2:
                        self._log_3s_audit("join_family_via_invite", start_time)
                        return False, "⚠️ This workspace has reached the Duo Pro limit of 2 members. The admin must upgrade to Family Pro to invite more members.", None

                if target_family.plan_type == "family_pro":
                    member_count = len(session.exec(select(User).where(User.family_id == target_family.id)).all())
                    if member_count >= 5:
                        self._log_3s_audit("join_family_via_invite", start_time)
                        return False, "⚠️ This workspace has reached the Family Pro limit of 5 members.", None

                old_family_id = user.family_id
                old_family = session.get(Family, old_family_id) if old_family_id else None
                
                # Check if old family was single-member
                is_single_member = False
                if old_family:
                    users_in_old = session.exec(select(User).where(User.family_id == old_family_id)).all()
                    if len(users_in_old) == 1:
                        is_single_member = True
                
                # Reassign user family and mark is_admin=False as invited member
                user.family_id = invite.family_id
                user.is_admin = False
                session.add(user)

                # Invalidate invite so it is single-use
                invite.is_active = False
                session.add(invite)

                
                # Migrate transactions if old family was single-member
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
                
                msg = (
                    f"🎉 Welcome to <b>{target_family.name or 'your new family'}</b>, {user.full_name or user.username or 'User'}!\n\n"
                    "You have successfully joined the family ledger. All expenses and income you log will now be shared with your family.\n\n"
                    "💡 You can leave this family anytime to return to a personal workspace using /leavefamily."
                )
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
            users = session.exec(
                select(User).where(User.family_id == family.id).order_by(User.created_at.asc())
            ).all()
            txs_count = len(session.exec(select(Transaction).where(Transaction.family_id == family.id)).all())
            invites = session.exec(select(FamilyInvite).where(
                FamilyInvite.family_id == family.id, 
                FamilyInvite.is_active == True,
                FamilyInvite.expires_at > datetime.now(timezone.utc)
            )).all()
            
            admin_user = users[0] if users else None
            members = []
            for u in users:
                is_admin = bool(admin_user and u.id == admin_user.id)
                members.append({
                    "id": str(u.id),
                    "telegram_id": u.telegram_id,
                    "username": u.username,
                    "full_name": u.full_name,
                    "is_admin": is_admin
                })
                
            self._log_3s_audit("get_family_info", start_time)
            return {
                "id": family.id,
                "name": family.name,
                "plan_type": family.plan_type,
                "subscription_status": family.subscription_status,
                "monthly_tx_count": family.monthly_tx_count,
                "trial_ends_at": family.trial_ends_at,
                "admin_id": str(admin_user.id) if admin_user else None,
                "is_current_user_admin": bool(admin_user and user.id == admin_user.id),
                "members": members,
                "transactions_count": txs_count,
                "active_invites_count": len(invites)
            }

    def remove_member(
        self,
        admin_user_id: UUID,
        target_identifier: str
    ) -> Tuple[bool, str, Optional[User], Optional[Family]]:
        """
        Removes a member from the family workspace and migrates their transactions
        into a new personal workspace.
        Only the family admin/creator can execute this.
        """
        start_time = time.time()
        try:
            with Session(self.engine, expire_on_commit=False) as session:
                admin_user = session.get(User, admin_user_id)
                if not admin_user or not admin_user.family_id:
                    self._log_3s_audit("remove_member", start_time)
                    return False, "User not found or not in a family.", None, None

                family_id = admin_user.family_id
                if not self.is_family_admin(family_id, admin_user_id):
                    self._log_3s_audit("remove_member", start_time)
                    return False, "⚠️ Only the family admin can remove members.", None, None

                # Clean target identifier
                clean_target = target_identifier.strip().lstrip("@")
                if not clean_target:
                    self._log_3s_audit("remove_member", start_time)
                    return False, "⚠️ Please specify the username or ID of the member to remove. Example: /removemember @username", None, None

                # Find member in the family directly via DB
                if clean_target.lower() == "none":
                    self._log_3s_audit("remove_member", start_time)
                    return False, "⚠️ Please specify a valid username or ID.", None, None

                tid = None
                if clean_target.isdigit():
                    tid = int(clean_target)

                from sqlalchemy import or_
                target_user = session.exec(
                    select(User).where(User.family_id == family_id).where(
                        or_(
                            User.username.ilike(clean_target),
                            User.full_name.ilike(clean_target),
                            User.telegram_id == tid if tid is not None else False
                        )
                    )
                ).first()

                if not target_user:
                    self._log_3s_audit("remove_member", start_time)
                    return False, f"⚠️ Member '{target_identifier}' was not found in your family workspace.", None, None

                if target_user.id == admin_user_id:
                    self._log_3s_audit("remove_member", start_time)
                    return False, "⚠️ You cannot remove yourself as admin. Use /leavefamily to leave or transfer the workspace.", None, None

                current_family = session.get(Family, family_id)
                new_family_name = f"{target_user.full_name or target_user.username or 'User'}'s Family"
                plan_type = "free" if target_user.has_used_trial else "trial"
                trial_ends_at = None if target_user.has_used_trial else datetime.now(timezone.utc) + timedelta(days=60)
                default_curr = (current_family.default_currency if current_family else None) or "USD"
                
                new_family = Family(
                    name=new_family_name,
                    plan_type=plan_type,
                    trial_ends_at=trial_ends_at,
                    default_currency=default_curr
                )
                session.add(new_family)
                session.flush()

                target_user.family_id = new_family.id
                target_user.is_admin = True
                session.add(target_user)

                # Re-assign member's transactions to the new personal workspace
                member_txs = session.exec(select(Transaction).where(Transaction.user_id == target_user.id)).all()
                for tx in member_txs:
                    tx.family_id = new_family.id
                    session.add(tx)

                session.commit()
                session.refresh(target_user)
                session.refresh(new_family)
                self._log_3s_audit("remove_member", start_time)

                target_name = f"@{target_user.username}" if target_user.username else (target_user.full_name or "Member")
                msg = f"✅ Removed {target_name} from the family workspace. All their personal transactions have been migrated to their new personal workspace."
                return True, msg, target_user, new_family
        except Exception as e:
            logger.error(f"Failed to remove member {target_identifier} by admin {admin_user_id}: {e}")
            return False, f"An error occurred while removing the member: {e}", None, None

    def get_leave_family_preview(self, user_id: UUID) -> Dict[str, Any]:
        """
        Evaluates the user's role and workspace status to provide a role-aware explanation
        or block the leave action before execution.
        """
        with Session(self.engine) as session:
            user = session.get(User, user_id)
            if not user or not user.family_id:
                return {"allowed": False, "reason": "not_in_family", "message": "User not found or not in a family."}

            current_family = session.get(Family, user.family_id)
            if not current_family:
                return {"allowed": False, "reason": "family_not_found", "message": "Family workspace not found."}

            members = session.exec(
                select(User).where(User.family_id == current_family.id).order_by(User.created_at.asc())
            ).all()

            if len(members) <= 1:
                return {
                    "allowed": False,
                    "reason": "already_solo",
                    "message": "ℹ️ You are already in your own personal workspace. There is no family group to leave."
                }

            is_admin = self.is_family_admin(current_family.id, user.id)
            is_active_pro = (
                current_family.subscription_status in ("active", "on_trial")
                and current_family.plan_type in ("family_pro", "solo_pro")
            )

            if is_admin and is_active_pro:
                return {
                    "allowed": False,
                    "reason": "active_pro_admin",
                    "message": LEAVE_FAMILY_ADMIN_ACTIVE_PRO_BLOCKED
                }

            if is_admin:
                remaining = [m for m in members if m.id != user.id]
                new_admin = remaining[0] if remaining else None
                new_admin_name = f"@{new_admin.username}" if (new_admin and new_admin.username) else ((new_admin.full_name or "Member") if new_admin else "Next Member")
                prompt = format_leave_family_admin_prompt(current_family.name, new_admin_name)
                return {
                    "allowed": True,
                    "requires_confirmation": True,
                    "role": "admin",
                    "prompt": prompt,
                    "new_admin_name": new_admin_name
                }

            # Non-admin member
            admin_user = next((m for m in members if self.is_family_admin(current_family.id, m.id)), members[0])
            admin_name = f"@{admin_user.username}" if (admin_user and admin_user.username) else (admin_user.full_name or "Admin")
            prompt = format_leave_family_member_prompt(current_family.name, admin_name)
            return {
                "allowed": True,
                "requires_confirmation": True,
                "role": "member",
                "prompt": prompt,
                "admin_name": admin_name
            }

    def leave_family(self, user_id: UUID) -> Tuple[bool, str, Optional[Family]]:
        """
        Allows any member to leave their current family workspace with full personal transaction portability
        into a new personal workspace.
        Admins of active Pro plans are blocked and directed to /billing.
        Admins of Free plans transfer admin rights to the oldest remaining member.
        """
        start_time = time.time()
        try:
            with Session(self.engine, expire_on_commit=False) as session:
                user = session.get(User, user_id)
                if not user or not user.family_id:
                    self._log_3s_audit("leave_family", start_time)
                    return False, "User not found or not in a family.", None

                current_family = session.get(Family, user.family_id)
                if not current_family:
                    self._log_3s_audit("leave_family", start_time)
                    return False, "Family workspace not found.", None

                members = session.exec(select(User).where(User.family_id == current_family.id).order_by(User.created_at.asc())).all()
                if len(members) <= 1:
                    self._log_3s_audit("leave_family", start_time)
                    return False, "You are already in your own personal workspace.", current_family

                was_admin = self.is_family_admin(current_family.id, user.id)
                is_active_pro = (
                    current_family.subscription_status in ("active", "on_trial")
                    and current_family.plan_type in ("family_pro", "solo_pro")
                )

                if was_admin and is_active_pro:
                    self._log_3s_audit("leave_family", start_time)
                    return False, LEAVE_FAMILY_ADMIN_ACTIVE_PRO_BLOCKED, None

                # If leaving user was admin of a Free family, transfer leadership to the oldest remaining member
                if was_admin:
                    remaining_members = [m for m in members if m.id != user.id]
                    if remaining_members:
                        new_admin = remaining_members[0]
                        new_admin.is_admin = True
                        session.add(new_admin)

                # Create a fresh isolated personal workspace
                had_trial = user.has_used_trial
                user.has_used_trial = True

                new_family_name = f"{user.full_name or user.username or 'User'}'s Family"
                plan_type = "free" if had_trial else "trial"
                trial_ends_at = None if had_trial else datetime.now(timezone.utc) + timedelta(days=60)
                new_family = Family(
                    name=new_family_name,
                    plan_type=plan_type,
                    trial_ends_at=trial_ends_at,
                    default_currency=current_family.default_currency or "USD"
                )
                session.add(new_family)
                session.flush()

                user.family_id = new_family.id
                user.is_admin = True
                session.add(user)

                from sqlalchemy import update
                session.exec(
                    update(Transaction)
                    .where(Transaction.user_id == user.id)
                    .values(family_id=new_family.id)
                )

                session.commit()
                session.refresh(new_family)
                self._log_3s_audit("leave_family", start_time)

                msg = "👋 You have left the family group. You are now in your own personal workspace. All your personal logged transactions have been preserved and moved with you."
                if had_trial:
                    msg += " Your trial was already consumed, so this workspace starts on the Free plan."
                return True, msg, new_family
        except Exception as e:
            logger.error(f"Failed to leave family for user_id={user_id}: {e}")
            return False, f"An error occurred while leaving the family: {e}", None

    def split_family_on_downgrade(self, family_id: UUID) -> Tuple[Optional[Family], list]:
        """
        Splits a family workspace when the admin downgrades from Family Pro to Solo Pro.
        The Admin retains family_id on Solo Pro (max 1 user).
        All non-admin members are clustered into a new shared Family workspace on the Free tier,
        with the oldest non-admin appointed as the new Admin.
        All non-admin personal transactions are migrated to the new workspace.
        """
        start_time = time.time()
        try:
            with Session(self.engine, expire_on_commit=False) as session:
                family = session.get(Family, family_id)
                if not family:
                    return None, []

                members = session.exec(
                    select(User).where(User.family_id == family_id).order_by(User.created_at.asc())
                ).all()

                admin_user = next((u for u in members if self.is_family_admin(family_id, u.id)), members[0] if members else None)
                if not admin_user:
                    return None, []

                non_admins = [u for u in members if u.id != admin_user.id]
                if not non_admins:
                    return None, []

                new_admin = non_admins[0]  # oldest non-admin
                new_family_name = f"{new_admin.full_name or new_admin.username or 'Family'}'s Group"

                new_family = Family(
                    name=new_family_name,
                    plan_type="free",
                    default_currency=family.default_currency or "USD",
                    monthly_tx_count=0
                )
                session.add(new_family)
                session.flush()

                non_admin_ids = []
                for member in non_admins:
                    member.family_id = new_family.id
                    if member.id == new_admin.id:
                        member.is_admin = True
                    else:
                        member.is_admin = False
                    session.add(member)
                    non_admin_ids.append(member.id)

                from sqlalchemy import update
                session.exec(
                    update(Transaction)
                    .where(Transaction.user_id.in_(non_admin_ids))
                    .values(family_id=new_family.id)
                )

                session.commit()
                session.refresh(new_family)
                self._log_3s_audit("split_family_on_downgrade", start_time)
                return new_family, non_admins
        except Exception as e:
            logger.error(f"Failed to split family {family_id} on downgrade: {e}")
            return None, []

    def graduate_member_to_new_workspace(self, user_id: UUID, target_plan: str = "solo_pro") -> Family:
        """
        Graduates an existing family member (usually non-admin) into their own sovereign workspace
        when they upgrade to Solo Pro or Family Pro.
        Migrates ONLY this user's personal transactions to the new workspace.
        The host family remains completely intact.
        """
        start_time = time.time()
        try:
            with Session(self.engine, expire_on_commit=False) as session:
                user = session.get(User, user_id)
                if not user:
                    raise ValueError(f"User {user_id} not found")

                old_family = session.get(Family, user.family_id) if user.family_id else None
                default_currency = (old_family.default_currency if old_family else None) or "USD"

                new_family_name = f"{user.full_name or user.username or 'User'}'s Workspace"
                new_family = Family(
                    name=new_family_name,
                    plan_type=target_plan,
                    default_currency=default_currency,
                    monthly_tx_count=0
                )
                session.add(new_family)
                session.flush()

                user.family_id = new_family.id
                user.is_admin = True
                session.add(user)

                from sqlalchemy import update
                session.exec(
                    update(Transaction)
                    .where(Transaction.user_id == user.id)
                    .values(family_id=new_family.id)
                )

                session.commit()
                session.refresh(new_family)
                self._log_3s_audit("graduate_member_to_new_workspace", start_time)
                return new_family
        except Exception as e:
            logger.error(f"Failed to graduate member {user_id} to new workspace: {e}")
            raise

    def get_family_default_currency(self, family_id: UUID) -> str:
        """
        Fetches the default currency for a family workspace.
        Defaults to settings.DEFAULT_CURRENCY or USD if unset.
        """
        if not family_id:
            return (settings.DEFAULT_CURRENCY or "USD").upper()
        try:
            with Session(self.engine) as session:
                fam_uuid = family_id if isinstance(family_id, UUID) else UUID(str(family_id))
                family = session.get(Family, fam_uuid)
                if family and getattr(family, "default_currency", None):
                    return family.default_currency.upper()
        except Exception:
            pass
        return (settings.DEFAULT_CURRENCY or "USD").upper()

    def set_family_default_currency(self, family_id: UUID, currency: str) -> str:
        """
        Updates the default currency for a family workspace.
        Validates that currency is a valid 3-letter alphabetic ISO 4217 code or mapped alias.
        """
        start_time = time.time()
        mapping = {
            "dollar": "USD", "dollars": "USD", "usd": "USD", "$": "USD", "dolar": "USD", "dolares": "USD", "dólar": "USD", "dólares": "USD",
            "euro": "EUR", "euros": "EUR", "eur": "EUR", "€": "EUR",
            "pound": "GBP", "pounds": "GBP", "gbp": "GBP", "£": "GBP", "libra": "GBP", "libras": "GBP",
            "peso mexicano": "MXN", "pesos mexicanos": "MXN", "pesos mexicanas": "MXN", "mxn": "MXN",
            "peso argentino": "ARS", "pesos argentinos": "ARS", "pesos argentinas": "ARS", "ars": "ARS",
            "peso chileno": "CLP", "pesos chilenos": "CLP", "pesos chilenas": "CLP", "clp": "CLP",
            "peso colombiano": "COP", "pesos colombianos": "COP", "pesos colombianas": "COP", "cop": "COP",
            "peso uruguayo": "UYU", "pesos uruguayos": "UYU", "pesos uruguayas": "UYU", "uyu": "UYU",
            "real": "BRL", "reales": "BRL", "reais": "BRL", "brl": "BRL", "r$": "BRL",
            "sol": "PEN", "soles": "PEN", "pen": "PEN", "s/": "PEN"
        }
        cleaned = (currency or "").strip().lower()
        if cleaned in mapping:
            normalized = mapping[cleaned]
        elif len(cleaned) == 3 and cleaned.isalpha():
            normalized = cleaned.upper()
        else:
            raise ValueError(f"Invalid currency code '{currency}'. Please provide a valid 3-letter ISO code like USD, ARS, MXN, EUR, GBP, CLP, COP, etc.")

        with Session(self.engine) as session:
            family = session.get(Family, family_id)
            if not family:
                raise ValueError("Family workspace not found.")
            family.default_currency = normalized
            session.add(family)
            session.commit()
            session.refresh(family)
            self._log_3s_audit("set_family_default_currency", start_time)
            return normalized

    def get_family_timezone(self, family_id: UUID) -> str:
        """Fetches the default timezone for a family workspace."""
        if not family_id:
            return getattr(settings, "DEFAULT_TIMEZONE", "America/Argentina/Buenos_Aires")
        try:
            with Session(self.engine) as session:
                fam_uuid = family_id if isinstance(family_id, UUID) else UUID(str(family_id))
                family = session.get(Family, fam_uuid)
                if family and getattr(family, "timezone", None):
                    return family.timezone
        except Exception:
            pass
        return getattr(settings, "DEFAULT_TIMEZONE", "America/Argentina/Buenos_Aires")

    def set_family_timezone(self, family_id: UUID, tz_name: str) -> str:
        """Updates the default timezone for a family workspace."""
        from src.services.query.date_resolver import validate_and_normalize_timezone
        norm = validate_and_normalize_timezone(tz_name)
        if not norm:
            raise ValueError(f"Invalid timezone '{tz_name}'. Try a city like 'Buenos Aires', 'Madrid', or an offset like '-3'.")
        with Session(self.engine) as session:
            fam_uuid = family_id if isinstance(family_id, UUID) else UUID(str(family_id))
            family = session.get(Family, fam_uuid)
            if not family:
                raise ValueError("Family workspace not found.")
            family.timezone = norm
            session.add(family)
            session.commit()
            return norm

    def get_user_timezone(self, user_id: UUID) -> Optional[str]:
        """Fetches the personal timezone override for a user."""
        try:
            with Session(self.engine) as session:
                u_uuid = user_id if isinstance(user_id, UUID) else UUID(str(user_id))
                user = session.get(User, u_uuid)
                return getattr(user, "timezone", None) if user else None
        except Exception:
            return None

    def set_user_timezone(self, user_id: UUID, tz_name: str) -> str:
        """Sets or updates the personal timezone override for a user."""
        from src.services.query.date_resolver import validate_and_normalize_timezone
        norm = validate_and_normalize_timezone(tz_name)
        if not norm:
            raise ValueError(f"Invalid timezone '{tz_name}'. Try a city like 'Buenos Aires', 'Madrid', or an offset like '-3'.")
        with Session(self.engine) as session:
            u_uuid = user_id if isinstance(user_id, UUID) else UUID(str(user_id))
            user = session.get(User, u_uuid)
            if not user:
                raise ValueError("User not found.")
            user.timezone = norm
            session.add(user)
            session.commit()
            return norm


