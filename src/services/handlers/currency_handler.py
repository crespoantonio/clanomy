import asyncio
from uuid import UUID
from src.services.family_service import FamilyService

async def handle_manage_currency(user_uuid: UUID, family_id: UUID, raw_text: str) -> str:
    family_service = FamilyService()
    parts = raw_text.split()
    target_curr = None
    if len(parts) >= 2 and parts[1].lower() not in ["help", "info", "a", "to", "es"]:
        target_curr = parts[-1].strip().upper()
    elif len(parts) >= 3 and parts[1].lower() in ["a", "to", "es"]:
        target_curr = parts[2].strip().upper()
    elif len(parts) == 1 and parts[0].startswith("/currency") and len(parts[0]) > 9:
        target_curr = parts[0][9:].strip().upper()
        
    if target_curr:
        try:
            new_curr = await asyncio.to_thread(family_service.set_family_default_currency, family_id, target_curr)
            return (
                f"✅ <b>Default Currency Updated to {new_curr}!</b>\n\n"
                f"Any future expenses or income logged without specifying a currency (e.g. <i>\"spent 500 on lunch\"</i> or <i>\"300 pesos\"</i>) "
                f"will now automatically default to <b>{new_curr}</b>."
            )
        except ValueError as ve:
            return f"⚠️ {ve}"
    else:
        curr = await asyncio.to_thread(family_service.get_family_default_currency, family_id)
        return (
            f"💵 <b>Household Default Currency:</b> <code>{curr}</code>\n\n"
            "To update your household default currency, reply with:\n"
            "• <code>/currency USD</code> (US Dollar)\n"
            "• <code>/currency ARS</code> (Argentine Peso)\n"
            "• <code>/currency MXN</code> (Mexican Peso)\n"
            "• <code>/currency EUR</code> (Euro)\n"
            "• <code>/currency CLP</code> (Chilean Peso)\n"
            "• <code>/currency COP</code> (Colombian Peso)\n"
            "• <code>/currency &lt;ISO_CODE&gt;</code> (Any 3-letter currency)"
        )
