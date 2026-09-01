import re
import logging
from typing import Optional
from src.core.config import settings
from src.services.extraction.models import ExtractionResult, UnifiedResult, ExtractionError

logger = logging.getLogger(__name__)

def fallback_regex_extract(text: str, default_currency: Optional[str] = None) -> ExtractionResult:
    """Attempt to extract amount, type, category, and concept via regex and keyword heuristics as a last resort."""
    amount_match = re.search(r'\b(\d+(?:[.,]\d{1,2})?)\b', text.replace(',', ''))
    if not amount_match:
        amount_match = re.search(r'[$€£](\d+(?:[.,]\d{1,2})?)', text.replace(',', ''))
        if not amount_match:
            raise ExtractionError("Fallback failed: No amount found in text.")
    
    amount = float(amount_match.group(1).replace(',', ''))
    
    effective_default_currency = (default_currency or settings.DEFAULT_CURRENCY or "USD").upper()
    currency = effective_default_currency
    text_lower = text.lower()
    if re.search(r'\beuro?s?\b|€', text_lower):
        currency = "EUR"
    elif re.search(r'\bgbp\b|\bpounds?\b|£|\blibras?\b', text_lower):
        currency = "GBP"
    elif re.search(r'\bpesos?\s+mexican[oa]s?\b|\bmxn\b', text_lower):
        currency = "MXN"
    elif re.search(r'\bpesos?\s+argentin[oa]s?\b|\bars\b', text_lower):
        currency = "ARS"
    elif re.search(r'\bpesos?\s+chilen[oa]s?\b|\bclp\b', text_lower):
        currency = "CLP"
    elif re.search(r'\bpesos?\s+colombian[oa]s?\b|\bcop\b', text_lower):
        currency = "COP"
    elif re.search(r'\bd[oó]lar(?:es)?\b|\busd\b', text_lower) or ('$' in text_lower and effective_default_currency == "USD"):
        currency = "USD"
        
    # Classify intent (income vs expense)
    income_keywords = [
        "salary", "earned", "got paid", "sold", "bonus",
        "freelance payment", "freelance", "dividend", "dividends", "invoice paid", "received",
        "sueldo", "gané", "gane", "cobré", "cobre", "vendí", "vendi", "ingreso", "pago recibido"
    ]
    expense_keywords = [
        "spent", "bought", "paid for", "coffee", "lunch", "rent",
        "gasté", "gaste", "compré", "compre", "pagué", "pague", "alquiler", "comida", "helado", "cena"
    ]
    
    tx_type = "expense"
    category = "Other"
    
    has_income = any(re.search(rf'\b{re.escape(kw)}\b', text_lower) for kw in income_keywords)
    has_expense = any(re.search(rf'\b{re.escape(kw)}\b', text_lower) for kw in expense_keywords)
    
    if has_income and not has_expense:
        tx_type = "income"
        if any(re.search(rf'\b{re.escape(kw)}\b', text_lower) for kw in ["salary", "got paid", "wage", "wages", "sueldo"]):
            category = "Salary"
        elif re.search(r'\b(?:bonus|bono)\b', text_lower):
            category = "Bonus"
        elif any(re.search(rf'\b{re.escape(kw)}\b', text_lower) for kw in ["sold", "sale", "sales", "vendí", "vendi", "venta"]):
            category = "Sale"
        elif any(re.search(rf'\b{re.escape(kw)}\b', text_lower) for kw in ["freelance", "freelance payment", "invoice paid", "consulting"]):
            category = "Freelance"
        elif any(re.search(rf'\b{re.escape(kw)}\b', text_lower) for kw in ["dividend", "dividends", "investment", "interest", "dividendo", "inversión"]):
            category = "Investment"
        elif re.search(r'\b(?:gift|regalo)\b', text_lower):
            category = "Gift"

    concept = text.strip()
    
    return ExtractionResult(
        amount=amount,
        type=tx_type,
        category=category,
        concept=concept,
        currency=currency,
        transaction_date=None
    )

def fallback_regex_classify(text: str, default_currency: Optional[str] = None) -> UnifiedResult:
    """Attempt to classify intent and extract details via regex/keywords when AI engine is unavailable."""
    text_lower = text.lower().strip()
    effective_default_currency = (default_currency or settings.DEFAULT_CURRENCY or "USD").upper()

    # 1. Query / Account / Family / Settings heuristics
    if "delete account" in text_lower or "confirm delete" in text_lower or "create family" in text_lower or "family info" in text_lower or "my family" in text_lower or "invite" in text_lower or "leave family" in text_lower or "remove member" in text_lower:
        return UnifiedResult(action="query")

    query_words = ["how much", "what did", "cuánto", "cuanto", "resumen", "summary", "breakdown", "export", "exportar", "balance", "cash flow", "flujo de caja", "familia", "family", "notion", "moneda", "currency"]
    if any(w in text_lower for w in query_words) and not re.search(r'\b(?:gasté|gaste|compré|compre|pagué|pague|spent|bought|paid)\b', text_lower):
        return UnifiedResult(action="query")

    # 2. Undo / Delete heuristics
    if any(re.search(rf'\b{re.escape(w)}\b', text_lower) for w in ["undo", "deshacer"]) or \
       re.search(r'\b(?:delete|remove|elimina|eliminar|borra|borrar)\s+(?:the\s+)?(?:last|latest|esos\s+ultimos|el\s+último|el\s+ultimo|último|ultimo)\b', text_lower) or \
       re.search(r'\b(?:delete|elimina|borra)\s+latest\b', text_lower):
        return UnifiedResult(action="undo_last")

    # 3. Edit / Update heuristics
    is_edit = any(re.search(rf'\b{re.escape(w)}\b', text_lower) for w in ["actualizar", "actualiza", "actualizarlo", "actualízalo", "cambiar", "cambia", "cambialo", "cámbiarlo", "corregir", "corrige", "corregilo", "modificar", "modifica", "update", "correct", "fix"]) or \
              re.search(r'\b(?:el\s+último|el\s+ultimo|the\s+last|the\s+latest)\s+(?:importe|monto|cost|amount|costo)?\s*(?:necesito\s+actualizarlo|actualizar|cambiar|fue|es|was|to|a)\b', text_lower)

    if is_edit:
        amount_match = re.search(r'\b(\d+(?:[.,]\d{1,2})?)\b', text.replace(',', ''))
        if not amount_match:
            amount_match = re.search(r'[$€£](\d+(?:[.,]\d{1,2})?)', text.replace(',', ''))
        new_amt = float(amount_match.group(1).replace(',', '')) if amount_match else None
        
        new_type = None
        if "income" in text_lower or "ingreso" in text_lower or "sueldo" in text_lower:
            new_type = "income"
        elif "expense" in text_lower or "gasto" in text_lower:
            new_type = "expense"

        return UnifiedResult(
            action="edit_last",
            new_amount=new_amt,
            new_type=new_type,
            new_currency=effective_default_currency if new_amt is not None else None
        )

    # 4. Fallback to transaction extraction
    try:
        ex = fallback_regex_extract(text, default_currency=effective_default_currency)
        return UnifiedResult(
            action="log_transaction",
            type=ex.type,
            amount=ex.amount,
            category=ex.category,
            concept=ex.concept,
            currency=ex.currency,
            transaction_date=ex.transaction_date
        )
    except Exception:
        return UnifiedResult(action="query")
