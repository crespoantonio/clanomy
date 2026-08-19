import argparse
import sys
from sqlmodel import Session, select
from src.db.models import Family, User
from src.db.session import engine

def grant_lifetime_pro(telegram_id: int):
    """
    Grants lifetime_pro status to the family associated with the given Telegram ID.
    This is an administrative script meant to be run directly on the server.
    """
    with Session(engine) as session:
        # Find the user by Telegram ID
        user = session.exec(select(User).where(User.telegram_id == telegram_id)).first()
        if not user:
            print(f"Error: No user found with Telegram ID {telegram_id}.")
            sys.exit(1)
            
        # Get the associated family
        family = session.exec(select(Family).where(Family.id == user.family_id)).first()
        if not family:
            print(f"Error: User {telegram_id} is not associated with any family.")
            sys.exit(1)
            
        print(f"Found User: {user.full_name or user.username or user.telegram_id} (Family ID: {family.id})")
        print(f"Current Plan: {family.plan_type} (Status: {family.subscription_status})")
        
        # Update to lifetime_pro
        family.plan_type = "lifetime_pro"
        family.subscription_status = "active"
        family.current_period_end = None
        
        session.add(family)
        session.commit()
        session.refresh(family)
        
        print("\nSuccess! Family has been upgraded to lifetime_pro.")
        print(f"New Plan: {family.plan_type} (Status: {family.subscription_status})")
        print("All members of this family now have unlimited access with no expiration.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Grant lifetime_pro (VIP) status to a user's family.")
    parser.add_argument(
        "--telegram-id", 
        type=int, 
        required=True, 
        help="The Telegram ID of the user whose family should be upgraded."
    )
    
    args = parser.parse_args()
    grant_lifetime_pro(args.telegram_id)
