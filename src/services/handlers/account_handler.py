from uuid import UUID
from src.services.account_service import AccountService

async def handle_delete_account(user_uuid: UUID, raw_text: str) -> str:
    if raw_text.strip() == "CONFIRM DELETE":
        account_service = AccountService()
        success = await account_service.delete_account(user_uuid)
        if success:
            return "✅ Your account and all associated transaction records have been permanently deleted from our database. Thank you for using Clanomy! If you ever wish to return, simply send /start."
        return "Failed to delete account. Please try again later."
    
    return "⚠️ Are you sure you want to permanently delete your account and all associated financial records? This action is irreversible.\n\nTo confirm, please reply with: <b>CONFIRM DELETE</b>"
