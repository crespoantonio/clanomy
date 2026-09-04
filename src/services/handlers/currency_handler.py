import asyncio
from typing import Tuple, Optional, Dict, Any, List
from uuid import UUID
from src.services.family_service import FamilyService

# Curated catalog of 18 top currencies organized in two 3x3 pages
CURRENCY_PAGES: List[List[Tuple[str, str, str]]] = [
    # Page 1: Americas & Global Core
    [
        ("USD", "🇺🇸 USD", "US Dollar"),
        ("EUR", "🇪🇺 EUR", "Euro"),
        ("GBP", "🇬🇧 GBP", "British Pound"),
        ("ARS", "🇦🇷 ARS", "Argentine Peso"),
        ("MXN", "🇲🇽 MXN", "Mexican Peso"),
        ("CLP", "🇨🇱 CLP", "Chilean Peso"),
        ("COP", "🇨🇴 COP", "Colombian Peso"),
        ("BRL", "🇧🇷 BRL", "Brazilian Real"),
        ("PEN", "🇵🇪 PEN", "Peruvian Sol"),
    ],
    # Page 2: Other Major & Regional
    [
        ("UYU", "🇺🇾 UYU", "Uruguayan Peso"),
        ("CAD", "🇨🇦 CAD", "Canadian Dollar"),
        ("AUD", "🇦🇺 AUD", "Australian Dollar"),
        ("JPY", "🇯🇵 JPY", "Japanese Yen"),
        ("CHF", "🇨🇭 CHF", "Swiss Franc"),
        ("CNY", "🇨🇳 CNY", "Chinese Yuan"),
        ("INR", "🇮🇳 INR", "Indian Rupee"),
        ("NZD", "🇳🇿 NZD", "New Zealand Dollar"),
        ("SEK", "🇸🇪 SEK", "Swedish Krona"),
    ]
]


def build_currency_keyboard(page: int = 1, active_currency: str = "USD") -> Dict[str, Any]:
    """
    Builds a 3x3 Telegram inline keyboard for the given page,
    marking the active currency with a checkmark and adding pagination controls.
    """
    total_pages = len(CURRENCY_PAGES)
    page_idx = max(0, min(page - 1, total_pages - 1))
    currencies = CURRENCY_PAGES[page_idx]

    inline_keyboard: List[List[Dict[str, str]]] = []
    row: List[Dict[str, str]] = []

    for code, label, _ in currencies:
        btn_text = f"✓ {label}" if code == (active_currency or "").upper() else label
        row.append({
            "text": btn_text,
            "callback_data": f"curr_set:{code}"
        })
        if len(row) == 3:
            inline_keyboard.append(row)
            row = []
    if row:
        inline_keyboard.append(row)

    current_page_num = page_idx + 1
    prev_page = total_pages if current_page_num == 1 else current_page_num - 1
    next_page = 1 if current_page_num == total_pages else current_page_num + 1

    nav_row = [
        {"text": "◀️ Prev", "callback_data": f"curr_p:{prev_page}"},
        {"text": f"Page {current_page_num}/{total_pages}", "callback_data": "noop"},
        {"text": "Next ▶️", "callback_data": f"curr_p:{next_page}"}
    ]
    inline_keyboard.append(nav_row)

    return {"inline_keyboard": inline_keyboard}


def format_currency_menu_text(active_currency: str) -> str:
    """Returns introduction text for the interactive currency selector."""
    return (
        "💵 <b>Select Household Default Currency</b>\n\n"
        f"Currently active: <b>{active_currency}</b>\n\n"
        "Tap a currency below to set it as your household default. "
        "Any future expenses or income logged without a currency symbol will automatically default to your choice."
    )


def format_currency_success_text(new_currency: str) -> str:
    """Returns confirmation text when a new currency is selected."""
    return (
        f"✅ <b>Default Currency Updated to {new_currency}!</b>\n\n"
        f"All future expenses & income logged without a currency symbol will automatically record as <b>{new_currency}</b>.\n\n"
        "You can change this anytime with /currency."
    )


async def handle_manage_currency(user_uuid: UUID, family_id: UUID, raw_text: str = "") -> Tuple[str, Dict[str, Any]]:
    """
    Handles the /currency command:
    - If a target currency argument is supplied (e.g. "/currency ARS" or "ARS"), updates the default currency directly and returns confirmation text with updated keyboard.
    - If called bare (e.g. "/currency"), returns the interactive selection menu and Page 1 inline keyboard.
    """
    family_service = FamilyService()
    target_curr = None
    if raw_text:
        parts = raw_text.split()
        if len(parts) >= 2 and parts[1].lower() not in ["help", "info", "a", "to", "es"]:
            target_curr = parts[-1].strip().upper()
        elif len(parts) >= 3 and parts[1].lower() in ["a", "to", "es"]:
            target_curr = parts[2].strip().upper()
        elif len(parts) == 1 and parts[0].startswith("/currency") and len(parts[0]) > 9:
            target_curr = parts[0][9:].strip().upper()
        elif len(parts) == 1 and len(parts[0]) == 3 and parts[0].isalpha():
            target_curr = parts[0].strip().upper()

    if target_curr:
        try:
            new_curr = await asyncio.to_thread(family_service.set_family_default_currency, family_id, target_curr)
            target_page = 1
            for idx, p_list in enumerate(CURRENCY_PAGES):
                if any(c[0] == new_curr for c in p_list):
                    target_page = idx + 1
                    break
            keyboard = build_currency_keyboard(page=target_page, active_currency=new_curr)
            return format_currency_success_text(new_curr), keyboard
        except ValueError as ve:
            active_curr = await asyncio.to_thread(family_service.get_family_default_currency, family_id)
            keyboard = build_currency_keyboard(page=1, active_currency=active_curr)
            return f"⚠️ {ve}", keyboard

    active_curr = await asyncio.to_thread(family_service.get_family_default_currency, family_id)
    text = format_currency_menu_text(active_curr)
    keyboard = build_currency_keyboard(page=1, active_currency=active_curr)
    return text, keyboard
