import re
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
import zoneinfo

from src.core.config import settings

logger = logging.getLogger(__name__)

# Common user-friendly timezone aliases
TIMEZONE_ALIASES = {
    "buenos aires": "America/Argentina/Buenos_Aires",
    "buenosaires": "America/Argentina/Buenos_Aires",
    "argentina": "America/Argentina/Buenos_Aires",
    "art": "America/Argentina/Buenos_Aires",
    "cordoba": "America/Argentina/Cordoba",
    "mendoza": "America/Argentina/Mendoza",
    "madrid": "Europe/Madrid",
    "spain": "Europe/Madrid",
    "espana": "Europe/Madrid",
    "españa": "Europe/Madrid",
    "barcelona": "Europe/Madrid",
    "mexico": "America/Mexico_City",
    "mexico city": "America/Mexico_City",
    "cdmx": "America/Mexico_City",
    "bogota": "America/Bogota",
    "colombia": "America/Bogota",
    "santiago": "America/Santiago",
    "chile": "America/Santiago",
    "lima": "America/Lima",
    "peru": "America/Lima",
    "montevideo": "America/Montevideo",
    "uruguay": "America/Montevideo",
    "sao paulo": "America/Sao_Paulo",
    "brazil": "America/Sao_Paulo",
    "brasil": "America/Sao_Paulo",
    "new york": "America/New_York",
    "nyc": "America/New_York",
    "miami": "America/New_York",
    "los angeles": "America/Los_Angeles",
    "chicago": "America/Chicago",
    "london": "Europe/London",
    "uk": "Europe/London",
    "paris": "Europe/Paris",
    "berlin": "Europe/Berlin",
    "rome": "Europe/Rome",
    "tokyo": "Asia/Tokyo",
    "sydney": "Australia/Sydney",
}

OFFSET_ALIASES = {
    "-3": "America/Argentina/Buenos_Aires",
    "-03": "America/Argentina/Buenos_Aires",
    "-03:00": "America/Argentina/Buenos_Aires",
    "utc-3": "America/Argentina/Buenos_Aires",
    "gmt-3": "America/Argentina/Buenos_Aires",
    "-4": "America/Santiago",
    "-04": "America/Santiago",
    "utc-4": "America/Santiago",
    "-5": "America/Bogota",
    "-05": "America/Bogota",
    "utc-5": "America/Bogota",
    "-6": "America/Mexico_City",
    "-06": "America/Mexico_City",
    "utc-6": "America/Mexico_City",
    "0": "UTC",
    "+0": "UTC",
    "utc": "UTC",
    "gmt": "UTC",
    "+1": "Europe/Madrid",
    "+01": "Europe/Madrid",
    "utc+1": "Europe/Madrid",
    "+2": "Europe/Athens",
    "+02": "Europe/Athens",
    "utc+2": "Europe/Athens",
}

def validate_and_normalize_timezone(tz_input: Optional[str]) -> Optional[str]:
    """
    Validates and normalizes user-provided timezone string into a valid IANA timezone name.
    Accepts IANA names ('America/Argentina/Buenos_Aires'), common cities ('Buenos Aires', 'Madrid'),
    or UTC offsets ('-3', 'UTC-3', '+1').
    Returns valid IANA key string or None if invalid.
    """
    if not tz_input:
        return None
    raw = tz_input.strip()
    clean_lower = raw.lower()

    if clean_lower in TIMEZONE_ALIASES:
        return TIMEZONE_ALIASES[clean_lower]
    if clean_lower in OFFSET_ALIASES:
        return OFFSET_ALIASES[clean_lower]

    # Try standard IANA name directly
    try:
        zoneinfo.ZoneInfo(raw)
        return raw
    except Exception:
        pass

    # Try title-cased if user typed e.g. "america/buenos_aires"
    try:
        parts = [p.capitalize() for p in raw.split("/")]
        candidate = "/".join(parts)
        zoneinfo.ZoneInfo(candidate)
        return candidate
    except Exception:
        pass

    return None

def _get_zone_info(tz_name: Optional[str] = None, reference_time: Optional[datetime] = None) -> zoneinfo.ZoneInfo:
    """Helper to get ZoneInfo with priority: tz_name -> reference_time.tzinfo -> settings.DEFAULT_TIMEZONE -> UTC."""
    if tz_name:
        try:
            return zoneinfo.ZoneInfo(tz_name)
        except Exception as e:
            logger.warning(f"Could not load timezone '{tz_name}', falling back: {e}")
    
    if reference_time and reference_time.tzinfo is not None:
        if isinstance(reference_time.tzinfo, zoneinfo.ZoneInfo):
            return reference_time.tzinfo
        # If timezone-aware with datetime.timezone, try to honor it
        return reference_time.tzinfo
    
    fallback = getattr(settings, "DEFAULT_TIMEZONE", "America/Argentina/Buenos_Aires")
    try:
        return zoneinfo.ZoneInfo(fallback)
    except Exception:
        return zoneinfo.ZoneInfo("UTC")

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

def _resolve_comparison_timeframe(
    timeframe: str,
    reference_time: Optional[datetime] = None,
    tz_name: Optional[str] = None
) -> tuple[Optional[str], Optional[datetime], Optional[datetime]]:
    tz = _get_zone_info(tz_name, reference_time)
    if reference_time:
        ref_local = reference_time.astimezone(tz) if reference_time.tzinfo else reference_time.replace(tzinfo=timezone.utc).astimezone(tz)
    else:
        ref_local = datetime.now(tz)
    
    if timeframe == "this_week":
        start_of_this_week = (ref_local - timedelta(days=ref_local.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        start_local = start_of_this_week - timedelta(days=7)
        end_local = start_of_this_week - timedelta(microseconds=1)
        return "last_week", start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)
        
    elif timeframe == "this_month":
        if ref_local.month == 1:
            prev_month = 12
            prev_year = ref_local.year - 1
        else:
            prev_month = ref_local.month - 1
            prev_year = ref_local.year
            
        start_local = ref_local.replace(year=prev_year, month=prev_month, day=1, hour=0, minute=0, second=0, microsecond=0)
        first_of_this_month = ref_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_local = first_of_this_month - timedelta(microseconds=1)
        return "last_month", start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)
        
    elif timeframe == "today":
        yesterday_local = ref_local - timedelta(days=1)
        start_local = yesterday_local.replace(hour=0, minute=0, second=0, microsecond=0)
        end_local = yesterday_local.replace(hour=23, minute=59, second=59, microsecond=999999)
        return "yesterday", start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)
        
    return None, None, None

def resolve_date_range(
    timeframe: str,
    start_date_str: Optional[str] = None,
    end_date_str: Optional[str] = None,
    reference_time: Optional[datetime] = None,
    tz_name: Optional[str] = None
) -> tuple[Optional[datetime], Optional[datetime]]:
    tz = _get_zone_info(tz_name, reference_time)
    if reference_time:
        ref_local = reference_time.astimezone(tz) if reference_time.tzinfo else reference_time.replace(tzinfo=timezone.utc).astimezone(tz)
    else:
        ref_local = datetime.now(tz)
    
    tf_str = (timeframe or "").lower().strip()

    # 1. Dynamic regex day patterns: e.g. last_15_days, ultimos_15_dias, past_30_days, 15_days, 15_dias
    days_match = re.match(r'^(?:last|past|ultimos|ultimas)?_?(\d+)_(?:days|dias)$', tf_str)
    if days_match:
        n_days = int(days_match.group(1))
        start_local = (ref_local - timedelta(days=n_days)).replace(hour=0, minute=0, second=0, microsecond=0)
        end_local = ref_local.replace(hour=23, minute=59, second=59, microsecond=999999)
        return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)

    months_match = re.match(r'^(?:last|past|ultimos)?_?(\d+)_(?:months|meses)$', tf_str)
    if months_match:
        n_months = int(months_match.group(1))
        start_local = (ref_local - timedelta(days=n_months * 30)).replace(hour=0, minute=0, second=0, microsecond=0)
        end_local = ref_local.replace(hour=23, minute=59, second=59, microsecond=999999)
        return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)

    if tf_str in ["today", "hoy"]:
        start_local = ref_local.replace(hour=0, minute=0, second=0, microsecond=0)
        end_local = ref_local.replace(hour=23, minute=59, second=59, microsecond=999999)
        return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)

    elif tf_str in ["yesterday", "ayer"]:
        yesterday_local = ref_local - timedelta(days=1)
        start_local = yesterday_local.replace(hour=0, minute=0, second=0, microsecond=0)
        end_local = yesterday_local.replace(hour=23, minute=59, second=59, microsecond=999999)
        return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)

    elif tf_str in ["this_week", "esta_semana"]:
        start_local = (ref_local - timedelta(days=ref_local.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        end_local = (start_local + timedelta(days=6)).replace(hour=23, minute=59, second=59, microsecond=999999)
        return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)

    elif tf_str in ["last_week", "la_semana_pasada", "semana_pasada"]:
        start_of_this_week = (ref_local - timedelta(days=ref_local.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        start_local = start_of_this_week - timedelta(days=7)
        end_local = start_of_this_week - timedelta(microseconds=1)
        return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)

    elif tf_str in ["this_month", "este_mes"]:
        start_local = ref_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_local = ref_local.replace(hour=23, minute=59, second=59, microsecond=999999)
        return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


    elif tf_str in ["last_month", "el_mes_pasado", "mes_pasado"]:
        first_of_this_month = ref_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_local = first_of_this_month - timedelta(microseconds=1)
        start_local = end_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)

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

