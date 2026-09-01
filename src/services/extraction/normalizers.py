import logging
from typing import Optional
from src.core.config import settings

logger = logging.getLogger(__name__)

CATEGORY_MAP = {
    "food/drink": "Food/Drink",
    "food": "Food/Drink",
    "drink": "Food/Drink",
    "drinks": "Food/Drink",
    "groceries": "Food/Drink",
    "grocery": "Food/Drink",
    "supermarket": "Food/Drink",
    "restaurant": "Food/Drink",
    "coffee": "Food/Drink",
    "lunch": "Food/Drink",
    "dinner": "Food/Drink",
    "comida": "Food/Drink",
    "almuerzo": "Food/Drink",
    "cena": "Food/Drink",
    "super": "Food/Drink",
    "supermercado": "Food/Drink",
    "helado": "Food/Drink",
    "transport": "Transport",
    "transportation": "Transport",
    "uber": "Transport",
    "taxi": "Transport",
    "gas": "Transport",
    "petrol": "Transport",
    "fuel": "Transport",
    "nafta": "Transport",
    "combustible": "Transport",
    "subway": "Transport",
    "bus": "Transport",
    "subte": "Transport",
    "colectivo": "Transport",
    "rent/bills": "Rent/Bills",
    "rent": "Rent/Bills",
    "bills": "Rent/Bills",
    "utilities": "Rent/Bills",
    "internet": "Rent/Bills",
    "wifi": "Rent/Bills",
    "phone": "Rent/Bills",
    "electricity": "Rent/Bills",
    "water": "Rent/Bills",
    "luz": "Rent/Bills",
    "agua": "Rent/Bills",
    "gas bill": "Rent/Bills",
    "alquiler": "Rent/Bills",
    "servicios": "Rent/Bills",
    "expensas": "Rent/Bills",
    "shopping": "Shopping",
    "clothes": "Shopping",
    "clothing": "Shopping",
    "shoes": "Shopping",
    "electronics": "Shopping",
    "amazon": "Shopping",
    "ropa": "Shopping",
    "compras": "Shopping",
    "leisure": "Leisure",
    "entertainment": "Leisure",
    "movies": "Leisure",
    "cinema": "Leisure",
    "games": "Leisure",
    "gaming": "Leisure",
    "gym": "Leisure",
    "travel": "Leisure",
    "vacation": "Leisure",
    "cine": "Leisure",
    "salidas": "Leisure",
    "vacaciones": "Leisure",
    "salary": "Salary",
    "sueldo": "Salary",
    "salario": "Salary",
    "wage": "Salary",
    "wages": "Salary",
    "payroll": "Salary",
    "bonus": "Bonus",
    "bono": "Bonus",
    "freelance": "Freelance",
    "freelance payment": "Freelance",
    "consulting": "Freelance",
    "investment": "Investment",
    "dividend": "Investment",
    "dividends": "Investment",
    "inversión": "Investment",
    "inversion": "Investment",
    "gift": "Gift",
    "regalo": "Gift",
    "sale": "Sale",
    "sales": "Sale",
    "venta": "Sale",
    "vendí": "Sale",
    "other": "Other",
    "otro": "Other",
    "otros": "Other",
}

def normalize_category_value(v: Optional[str]) -> Optional[str]:
    if not v:
        return None
    cleaned = v.strip().lower()
    if cleaned in CATEGORY_MAP:
        return CATEGORY_MAP[cleaned]
    return "Other"

def normalize_currency_value(v: Optional[str], default_currency: Optional[str] = None) -> Optional[str]:
    if not v:
        return None
    default_curr = (default_currency or settings.DEFAULT_CURRENCY or "USD").upper()
    mapping = {
        "dollar": "USD", "dollars": "USD", "usd": "USD", "$": "USD", "dolar": "USD", "dolares": "USD", "dólar": "USD", "dólares": "USD",
        "euro": "EUR", "euros": "EUR", "eur": "EUR", "€": "EUR",
        "pound": "GBP", "pounds": "GBP", "gbp": "GBP", "£": "GBP", "libra": "GBP", "libras": "GBP",
        "peso mexicano": "MXN", "pesos mexicanos": "MXN", "pesos mexicanas": "MXN", "mxn": "MXN", "mexican pesos": "MXN",
        "peso argentino": "ARS", "pesos argentinos": "ARS", "pesos argentinas": "ARS", "ars": "ARS", "argentine pesos": "ARS",
        "peso chileno": "CLP", "pesos chilenos": "CLP", "pesos chilenas": "CLP", "clp": "CLP", "chilean pesos": "CLP",
        "peso colombiano": "COP", "pesos colombianos": "COP", "pesos colombianas": "COP", "cop": "COP", "colombian pesos": "COP",
        "peso uruguayo": "UYU", "pesos uruguayos": "UYU", "pesos uruguayas": "UYU", "uyu": "UYU", "uruguayan pesos": "UYU",
        "real": "BRL", "reales": "BRL", "reais": "BRL", "brl": "BRL", "r$": "BRL",
        "sol": "PEN", "soles": "PEN", "pen": "PEN", "s/": "PEN",
        "peso": default_curr, "pesos": default_curr, "bucks": default_curr, "mangos": default_curr, "lucas": default_curr, "plata": default_curr
    }
    cleaned = v.strip().lower()
    if cleaned in mapping:
        return mapping[cleaned]
    if len(cleaned) == 3 and cleaned.isalpha():
        return cleaned.upper()
    return default_curr
