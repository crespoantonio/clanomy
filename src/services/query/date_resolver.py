import re
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple

def _sanitize_concept_for_prompt(text: str, max_len: int = 50) -> str:
    """Sanitize user-provided transaction concepts to prevent indirect prompt injection."""
    if not text:
        return ""
    cleaned = re.sub(r'[^\w\s\-\.\,\'\"/]', '', text)
    return cleaned.strip()[:max_len]

def _parse_amount_string(decrypted_str: str) -> tuple[float, str]:
    parts = decrypted_str.strip().split()
    if not parts:
        return 0.0, "USD"
    try:
        amount = float(parts[0])
    except ValueError:
        amount = 0.0
    currency = parts[1].upper() if len(parts) > 1 else "USD"
    return amount, currency

def _resolve_comparison_timeframe(timeframe: str, reference_time: Optional[datetime] = None) -> tuple[Optional[str], Optional[datetime], Optional[datetime]]:
    ref_time = reference_time or datetime.now(timezone.utc)
    
    if timeframe == "this_week":
        start_of_this_week = (ref_time - timedelta(days=ref_time.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        start_time = start_of_this_week - timedelta(days=7)
        end_time = start_of_this_week - timedelta(microseconds=1)
        return "last_week", start_time, end_time
        
    elif timeframe == "this_month":
        if ref_time.month == 1:
            prev_month = 12
            prev_year = ref_time.year - 1
        else:
            prev_month = ref_time.month - 1
            prev_year = ref_time.year
            
        start_time = ref_time.replace(year=prev_year, month=prev_month, day=1, hour=0, minute=0, second=0, microsecond=0)
        first_of_this_month = ref_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_time = first_of_this_month - timedelta(microseconds=1)
        return "last_month", start_time, end_time
        
    elif timeframe == "today":
        yesterday = ref_time - timedelta(days=1)
        start_time = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
        return "yesterday", start_time, end_time
        
    return None, None, None

def resolve_date_range(timeframe: str, start_date_str: Optional[str], end_date_str: Optional[str], reference_time: Optional[datetime] = None) -> tuple[Optional[datetime], Optional[datetime]]:
    ref_time = reference_time or datetime.now(timezone.utc)
    
    # 1. Dynamic regex day patterns: e.g. last_15_days, ultimos_15_dias, past_30_days, 15_days, 15_dias
    tf_str = (timeframe or "").lower().strip()
    days_match = re.match(r'^(?:last|past|ultimos|ultimas)?_?(\d+)_(?:days|dias)$', tf_str)
    if days_match:
        n_days = int(days_match.group(1))
        start_time = (ref_time - timedelta(days=n_days)).replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = ref_time.replace(hour=23, minute=59, second=59, microsecond=999999)
        return start_time, end_time

    months_match = re.match(r'^(?:last|past|ultimos)?_?(\d+)_(?:months|meses)$', tf_str)
    if months_match:
        n_months = int(months_match.group(1))
        start_time = (ref_time - timedelta(days=n_months * 30)).replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = ref_time.replace(hour=23, minute=59, second=59, microsecond=999999)
        return start_time, end_time

    if tf_str in ["today", "hoy"]:
        start_time = ref_time.replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = ref_time.replace(hour=23, minute=59, second=59, microsecond=999999)
        return start_time, end_time
    elif tf_str in ["yesterday", "ayer"]:
        yesterday = ref_time - timedelta(days=1)
        start_time = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
        return start_time, end_time
    elif tf_str in ["this_week", "esta_semana"]:
        start_time = (ref_time - timedelta(days=ref_time.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = ref_time.replace(hour=23, minute=59, second=59, microsecond=999999)
        return start_time, end_time
    elif tf_str in ["last_week", "la_semana_pasada", "semana_pasada"]:
        start_of_this_week = (ref_time - timedelta(days=ref_time.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        start_time = start_of_this_week - timedelta(days=7)
        end_time = start_of_this_week - timedelta(microseconds=1)
        return start_time, end_time
    elif tf_str in ["this_month", "este_mes"]:
        start_time = ref_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_time = ref_time.replace(hour=23, minute=59, second=59, microsecond=999999)
        return start_time, end_time
    elif tf_str in ["last_month", "el_mes_pasado", "mes_pasado"]:
        first_of_this_month = ref_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_time = first_of_this_month - timedelta(microseconds=1)
        start_time = end_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return start_time, end_time
    elif tf_str in ["custom", "personalizado"] or (start_date_str and end_date_str):
        start_time = None
        end_time = None
        if start_date_str and isinstance(start_date_str, str):
            try:
                start_time = datetime.strptime(start_date_str.strip(), "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except (ValueError, AttributeError):
                pass
        if end_date_str and isinstance(end_date_str, str):
            try:
                end_time = datetime.strptime(end_date_str.strip(), "%Y-%m-%d").replace(tzinfo=timezone.utc, hour=23, minute=59, second=59, microsecond=999999)
            except (ValueError, AttributeError):
                pass
        return start_time, end_time
    
    return None, None
