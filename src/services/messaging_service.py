from typing import Dict, Any, Tuple
from sqlmodel import Session, select
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timezone, timedelta
from src.db.models import User, Family

class MessagingService:
    def __init__(self, session: Session):
        self.session = session

    def get_or_create_user_and_family(self, user_data: Dict[str, Any]) -> Tuple[User, Family]:
        """
        Retrieves an existing user by platform ID (telegram_id) or creates a new User and Family.
        Updates user info (username, full_name) if it has changed.
        Handles concurrent creation gracefully via IntegrityError rollback.
        """
        platform_id = user_data.get("id")
        if not platform_id:
            raise ValueError("User ID is required")

        username = user_data.get("username")
        first_name = user_data.get("first_name", "")
        last_name = user_data.get("last_name", "")
        full_name = f"{first_name} {last_name}".strip() or None

        # Check for existing user
        statement = select(User).where(User.telegram_id == platform_id)
        user = self.session.exec(statement).first()

        if user:
            # Update info if changed
            changed = False
            if user.username != username:
                user.username = username
                changed = True
            if user.full_name != full_name:
                user.full_name = full_name
                changed = True
            
            if changed:
                self.session.add(user)
                self.session.commit()
                self.session.refresh(user)
            
            # Fetch family
            family = self.session.get(Family, user.family_id)
            return user, family

        # Create new Family and User in one atomic operation
        # If user has not consumed a trial, provision 60-day Family Pro trial
        family_name = f"{full_name or username or 'User'}'s Family"
        plan_type = "trial"
        trial_ends_at = datetime.now(timezone.utc) + timedelta(days=60)

        family = Family(
            name=family_name,
            plan_type=plan_type,
            trial_ends_at=trial_ends_at
        )
        self.session.add(family)
        try:
            self.session.flush() # Get family.id without committing

            user = User(
                telegram_id=platform_id,
                username=username,
                full_name=full_name,
                family_id=family.id,
                has_used_trial=True,
                is_admin=True
            )
            self.session.add(user)
            self.session.commit() # Atomic commit for both
            
            self.session.refresh(family)
            self.session.refresh(user)

            return user, family
        except IntegrityError:
            self.session.rollback()
            # Concurrent creation handled: fetch the existing user created by parallel request
            user = self.session.exec(select(User).where(User.telegram_id == platform_id)).first()
            if user:
                family = self.session.get(Family, user.family_id)
                return user, family
            raise

