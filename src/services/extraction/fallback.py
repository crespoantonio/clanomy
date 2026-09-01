import re
import logging
from datetime import datetime
from typing import Optional
from src.core.config import settings
from src.services.extraction.models import ExtractionResult, UnifiedResult, ExtractionError, ParsedItem

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
    elif re.search(r'\bpesos?\s+mexican[oa]s?\b|\bmxn\b', text_lower):
        currency = "MXN"
    elif re.search(r'\bd[oó]lar(?:es)?\b|\busd\b|\bus\$\b|\bu\$s\b|\bbucks\b', text_lower):
        currency = "USD"
    elif '$' in text_lower:
        currency = effective_default_currency
        
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

def _parse_curr_token(token: Optional[str], default_curr: str) -> str:
    if not token:
        return default_curr
    t = token.lower().strip()
    if "dolar" in t or "usd" in t or t == "u$s" or t == "us$":
        return "USD"
    if "eur" in t or "euro" in t or "€" in t:
        return "EUR"
    if "gbp" in t or "pound" in t or "libra" in t or "£" in t:
        return "GBP"
    if "peso" in t or "ars" in t:
        return "ARS"
    if "mxn" in t:
        return "MXN"
    if "clp" in t:
        return "CLP"
    if "cop" in t:
        return "COP"
    if t == "$":
        return default_curr
    if len(t) == 3 and t.isalpha():
        return t.upper()
    return default_curr

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
    undo_match = (
        any(re.search(rf'\b{re.escape(w)}\b', text_lower) for w in ["undo", "deshacer"]) or
        re.search(r'\b(?:delete|remove|elimina|eliminar|borra|borrar)\s+(?:the\s+)?(?:last|latest|esos\s+ultimos|el\s+último|el\s+ultimo|último|ultimo)\b', text_lower) or
        re.search(r'\b(?:delete|remove|elimina|eliminar|borra|borrar)\s+(?:el\s+ingreso|el\s+gasto|la\s+transacci[oó]n|el\s+sueldo|the\s+income|the\s+expense)\b', text_lower)
    )
    if undo_match:
        target_amt_match = re.search(r'\b(\d+(?:[.,]\d+)?)\b', text.replace(',', ''))
        target_amt = float(target_amt_match.group(1)) if target_amt_match else None
        target_curr = None
        if re.search(r'\b(?:d[oó]lar(?:es)?|usd)\b', text_lower):
            target_curr = "USD"
        elif re.search(r'\b(?:pesos?|ars)\b', text_lower):
            target_curr = "ARS"
        return UnifiedResult(action="undo_last", target_amount=target_amt, target_currency=target_curr)

    # 3. Currency correction heuristics: e.g. "el salario de 1606932 es ARS", "era en pesos", "era en ARS", "es en dolares"
    curr_corr_match = re.search(r'\b(?:el|la)?\s*(?:salario|sueldo|gasto|ingreso|monto|pago)?\s*(?:de\s+)?(\d+(?:[.,]\d+)?)?\s*(?:es|era|fue|en\s+realidad\s+era)\s*(?:en\s+)?(ars|usd|eur|pesos?|d[oó]lares?)\b', text_lower)
    if curr_corr_match:
        raw_amt = curr_corr_match.group(1)
        raw_curr = curr_corr_match.group(2).lower()
        target_amt = float(raw_amt.replace(',', '')) if raw_amt else None
        new_curr = "USD" if "dolar" in raw_curr or raw_curr == "usd" else ("EUR" if raw_curr == "eur" else (effective_default_currency if "peso" in raw_curr else raw_curr.upper()))
        return UnifiedResult(
            action="edit_last",
            target_amount=target_amt,
            new_currency=new_curr
        )

    # 4. Currency Exchange (FX) heuristics: e.g. "Cambie 200 dolares por 300000 pesos", "I change 200 USD for 300000 ARS", "Cambie 200 dolares a 1500"
    fx_amount_match = re.search(
        r'\b(cambi[eé]|swapped|exchanged|compr[eé]|vend[ií]|change|swap|exchange|bought|sold)\s+[$€£]?\s*(\d+(?:[.,]\d+)?)\s*([a-zA-Z$€£]*)\s*(?:por|for|to|con|en)\s*[$€£]?\s*(\d+(?:[.,]\d+)?)\s*([a-zA-Z$€£]*)',
        text_lower
    )
    fx_rate_match = re.search(
        r'\b(cambi[eé]|vend[ií]|change|swap|sold)\s+[$€£]?\s*(\d+(?:[.,]\d+)?)\s*(d[oó]lar(?:es)?|usd|\$)\s*(?:a|at|cotizado\s+a|al\s+cambio\s+de)\s*[$€£]?\s*(\d+(?:[.,]\d+)?)',
        text_lower
    )

    if fx_amount_match:
        verb = fx_amount_match.group(1).lower()
        amt1 = float(fx_amount_match.group(2).replace(',', ''))
        curr1 = _parse_curr_token(fx_amount_match.group(3), "USD" if "dolar" in fx_amount_match.group(3).lower() else effective_default_currency)
        amt2 = float(fx_amount_match.group(4).replace(',', ''))
        curr2 = _parse_curr_token(fx_amount_match.group(5), effective_default_currency if curr1 == "USD" else "USD")

        is_buy = any(b in verb for b in ["compr", "bought", "buy"])
        if is_buy:
            sold_amt, sold_curr = amt2, curr2
            recv_amt, recv_curr = amt1, curr1
        else:
            sold_amt, sold_curr = amt1, curr1
            recv_amt, recv_curr = amt2, curr2

        rate = round(recv_amt / sold_amt, 4) if sold_amt > 0 else None

        item_sold = ParsedItem(
            type="expense",
            amount=sold_amt,
            category="Exchange",
            concept=f"Currency Exchange ({sold_amt:g} {sold_curr} -> {recv_amt:g} {recv_curr})",
            currency=sold_curr
        )
        item_recv = ParsedItem(
            type="income",
            amount=recv_amt,
            category="Exchange",
            concept=f"Currency Exchange ({sold_amt:g} {sold_curr} -> {recv_amt:g} {recv_curr})",
            currency=recv_curr
        )
        return UnifiedResult(
            action="log_transaction",
            items=[item_sold, item_recv],
            is_exchange=True,
            exchange_rate=rate
        )

    elif fx_rate_match:
        amt1 = float(fx_rate_match.group(2).replace(',', ''))
        curr1 = "USD"
        rate = float(fx_rate_match.group(4).replace(',', ''))
        amt2 = round(amt1 * rate, 2)
        curr2 = effective_default_currency

        item_sold = ParsedItem(
            type="expense",
            amount=amt1,
            category="Exchange",
            concept=f"Currency Exchange ({amt1:g} {curr1} -> {amt2:g} {curr2})",
            currency=curr1
        )
        item_recv = ParsedItem(
            type="income",
            amount=amt2,
            category="Exchange",
            concept=f"Currency Exchange ({amt1:g} {curr1} -> {amt2:g} {curr2})",
            currency=curr2
        )
        return UnifiedResult(
            action="log_transaction",
            items=[item_sold, item_recv],
            is_exchange=True,
            exchange_rate=rate
        )

    # 5. General Edit / Update heuristics
    is_edit = any(re.search(rf'\b{re.escape(w)}\b', text_lower) for w in ["actualizar", "actualiza", "actualizarlo", "actualízalo", "cambiar", "cambia", "cambialo", "cámbiarlo", "corregir", "corrige", "corregilo", "modificar", "modifica", "update", "correct", "fix"]) or \
              re.search(r'\b(?:el\s+último|el\s+ultimo|the\s+last|the\s+latest)\s+(?:importe|monto|cost|amount|costo)?\s*(?:necesito\s+actualizarlo|actualizar|cambiar|fue|es|was|to|a)\b', text_lower)

    if is_edit:
        target_curr = None
        if re.search(r'\b(?:en\s+)?(?:d[oó]lar(?:es)?|usd)\b', text_lower):
            target_curr = "USD"
        elif re.search(r'\b(?:en\s+)?(?:pesos?|ars)\b', text_lower):
            target_curr = "ARS"

        amount_match = re.search(r'\b(\d+(?:[.,]\d{1,2})?)\b', text.replace(',', ''))
        if not amount_match:
            amount_match = re.search(r'[$€£](\d+(?:[.,]\d{1,2})?)', text.replace(',', ''))
        new_amt = float(amount_match.group(1).replace(',', '')) if amount_match else None
        
        new_type = None
        if "income" in text_lower or "ingreso" in text_lower or "sueldo" in text_lower:
            new_type = "income"
        elif "expense" in text_lower or "gasto" in text_lower:
            new_type = "expense"

        new_curr = None
        if re.search(r'\bd[oó]lar(?:es)?\b|\busd\b', text_lower):
            new_curr = "USD"
        elif re.search(r'\bpesos?\b|\bars\b', text_lower):
            new_curr = "ARS"

        return UnifiedResult(
            action="edit_last",
            new_amount=new_amt,
            new_type=new_type,
            new_currency=new_curr,
            target_currency=target_curr
        )

    # 4. Fallback to transaction extraction (supporting single or multi-line items)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    header_regex = r'^(?:los\s+gastos\s+fijos|gastos\s+fijos|fixed\s+expenses|fixed\s+bills|facturas\s+por\s+pagar|bills\s+due)'
    if len(lines) > 1 and re.search(header_regex, lines[0].lower()):
        candidate_lines = lines[1:]
    else:
        candidate_lines = lines

    extracted_items = []
    for line in candidate_lines:
        try:
            # Check for due date in line: "con vencimiento el 18/09", "con vencimento el 18/09", "vence el 04/09", "due on 09/18"
            due_match = re.search(r'(?:(?:con\s+)?(?:vencim(?:iento|ento)|vence|vto\.?|venc\.?)\s+(?:el\s+)?|due\s+(?:on\s+|date\s*:?\s*)?)(\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?)', line, re.IGNORECASE)
            is_bill = False
            due_date_str = None
            if due_match:
                is_bill = True
                raw_date = due_match.group(1)
                parts = re.split(r'[/-]', raw_date)
                curr_year = datetime.now().year
                if len(parts) == 2:
                    d, m = int(parts[0]), int(parts[1])
                    if d > 12 >= m:
                        due_date_str = f"{curr_year:04d}-{m:02d}-{d:02d}"
                    elif m > 12 >= d:
                        due_date_str = f"{curr_year:04d}-{d:02d}-{m:02d}"
                    else:
                        due_date_str = f"{curr_year:04d}-{m:02d}-{d:02d}"
                elif len(parts) == 3:
                    d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
                    y = y if y > 100 else 2000 + y
                    due_date_str = f"{y:04d}-{m:02d}-{d:02d}"

            item_ex = fallback_regex_extract(line, default_currency=effective_default_currency)
            clean_concept = re.sub(r'(?:\.\s*)?(?:con\s+)?(?:vencim(?:iento|ento)|vence|vto\.?|venc\.?|due\s+(?:on|date)).*$', '', item_ex.concept, flags=re.IGNORECASE).strip()
            clean_concept = re.sub(r'[\$€£]?\s*\b\d+(?:[.,]\d+)?\b(?:\s*[a-zA-Z]{3})?', '', clean_concept).strip()
            clean_concept = clean_concept.strip(" .:-")
            extracted_items.append(ParsedItem(
                type=item_ex.type,
                amount=item_ex.amount,
                category=item_ex.category,
                concept=clean_concept or item_ex.concept,
                currency=item_ex.currency,
                transaction_date=item_ex.transaction_date,
                due_date=due_date_str,
                is_scheduled_bill=is_bill
            ))
        except Exception:
            continue

    if extracted_items:
        return UnifiedResult(
            action="log_transaction",
            items=extracted_items
        )

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
