from sqlmodel import Session, select
from sqlalchemy import or_, update
from datetime import datetime, timezone, timedelta
from src.db.database import engine
from src.db.models import User, Family, Transaction

def update_is_family_admin():
    with open('src/services/family_service.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Replace is_family_admin
    old_admin_func = '''    def is_family_admin(self, family_id: UUID, user_id: UUID) -> bool:
        \"\"\"
        Identifies the workspace admin (the original creator).
        Currently determined by the earliest created_at timestamp in the family.
        \"\"\"
        with Session(self.engine) as session:
            admin_user = session.exec(
                select(User).where(User.family_id == family_id).order_by(User.created_at.asc())
            ).first()
            if admin_user and admin_user.id == user_id:
                return True
            return False'''

    new_admin_func = '''    def is_family_admin(self, family_id: UUID, user_id: UUID) -> bool:
        \"\"\"
        Identifies the workspace admin.
        \"\"\"
        with Session(self.engine) as session:
            user = session.get(User, user_id)
            return bool(user and user.is_admin and user.family_id == family_id)'''

    if old_admin_func in content:
        content = content.replace(old_admin_func, new_admin_func)
    
    with open('src/services/family_service.py', 'w', encoding='utf-8') as f:
        f.write(content)

update_is_family_admin()
