import asyncio
import logging
import threading
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Tuple, Dict, Literal
from uuid import UUID

import ollama
from pydantic import BaseModel, field_validator
from sqlmodel import Session, select

from src.core.config import settings
from src.core.encryption import EncryptionService
from src.db.session import engine
from src.db.models import Transaction, User

logger = logging.getLogger(__name__)

class QueryProcessingError(Exception):
    pass

def resolve_category_alias(input_category: Optional[str]) -> Optional[str]:
    if not input_category or not isinstance(input_category, str) or not input_category.strip():
        return None
    
    raw_cleaned = input_category.strip().lower()
    cleaned = "/".join(part.strip() for part in raw_cleaned.split("/"))
    
    aliases = {
        "food/drink": ["groceries", "grocery", "food", "drink", "drinks", "dining", "restaurant", "restaurants", "coffee", "cafe", "supermarket", "lunch", "dinner", "breakfast", "snacks", "bar", "pub", "takeout", "delivery"],
        "transport": ["transport", "transportation", "uber", "taxi", "cab", "gas", "fuel", "petrol", "bus", "train", "subway", "metro", "transit", "parking", "toll", "flight", "flights", "airline"],
        "rent/bills": ["rent", "bills", "utilities", "utility", "electricity", "electric", "water", "gas bill", "power", "internet", "wifi", "phone", "mobile", "mortgage", "insurance", "subscription", "subscriptions"],
        "shopping": ["shopping", "clothes", "clothing", "apparel", "shoes", "electronics", "gadgets", "hardware", "tools", "amazon", "books", "home", "furniture"],
        "leisure": ["leisure", "entertainment", "movies", "cinema", "games", "gaming", "concerts", "hobby", "hobbies", "sports", "gym", "fitness", "vacation", "travel", "clubbing", "party"],
        "other": ["other", "misc", "miscellaneous", "uncategorized", "fees", "bank fees", "donations", "gifts"]
    }
    
    canonical_mapping = {
        "food/drink": "Food/Drink",
        "transport": "Transport",
        "rent/bills": "Rent/Bills",
        "shopping": "Shopping",
        "leisure": "Leisure",
        "other": "Other"
    }
    
    if cleaned in canonical_mapping:
        return canonical_mapping[cleaned]
        
    for canonical, alias_list in aliases.items():
        if cleaned in alias_list:
            return canonical_mapping[canonical]
            
    return "Other"


class ParsedQueryIntent(BaseModel):
    intent: Literal["spending_summary", "query_comparison", "export_data", "delete_account", "notion_manage", "generate_invite", "create_family", "join_family", "log_expense", "query", "query_spending", "family_info"]
    timeframe: Optional[str] = "this_month"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    category: Optional[str] = None
    concept_keyword: Optional[str] = None
    export_format: Optional[str] = "csv"
    family_name: Optional[str] = None
    scope: Optional[str] = "family"
    member_filter: Optional[str] = None

    @field_validator('category')
    @classmethod
    def normalize_category(cls, v: Optional[str]) -> Optional[str]:
        return resolve_category_alias(v)

class DecryptedTransaction(BaseModel):
    id: UUID
    family_id: UUID
    user_id: UUID
    user_name: Optional[str] = None
    user_handle: Optional[str] = None
    amount: float
    currency: str
    concept: str
    category: str
    timestamp: datetime

class PeriodComparison(BaseModel):
    previous_timeframe: str
    previous_start_time: Optional[datetime] = None
    previous_end_time: Optional[datetime] = None
    previous_total_amount: float
    previous_transaction_count: int
    difference_amount: float
    percentage_change: Optional[float] = None

class CategorySpending(BaseModel):
    category: str
    total_amount: float
    primary_currency: str = "USD"
    currency_totals: Dict[str, float]
    transaction_count: int
    percentage_of_total: Optional[float] = None
    average_per_transaction: float

class CategoryBreakdown(BaseModel):
    timeframe: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    total_spending: float
    primary_currency: str = "USD"
    categories: Dict[str, CategorySpending]
    top_category: Optional[str] = None
    top_category_amount: Optional[float] = None

class MemberSpending(BaseModel):
    user_id: UUID
    user_name: str
    user_handle: Optional[str] = None
    total_amount: float
    primary_currency: str = "USD"
    currency_totals: Dict[str, float]
    transaction_count: int
    percentage_of_total: Optional[float] = None
    average_per_transaction: float
    top_category: Optional[str] = None

class MemberBreakdown(BaseModel):
    timeframe: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    total_spending: float
    primary_currency: str = "USD"
    members: Dict[str, MemberSpending]
    top_spender: Optional[str] = None
    top_spender_amount: Optional[float] = None

class TimeAggregation(BaseModel):
    timeframe: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    total_amount: float
    primary_currency: str = "USD"
    currency_totals: Dict[str, float]
    transaction_count: int
    average_per_transaction: float
    daily_breakdown: Dict[str, float]
    comparison: Optional[PeriodComparison] = None
    category_breakdown: Dict[str, float] = {}

class QueryResult(BaseModel):
    intent: ParsedQueryIntent
    resolved_start_time: Optional[datetime] = None
    resolved_end_time: Optional[datetime] = None
    transactions: List[DecryptedTransaction] = []
    total_count: int = 0
    aggregation: Optional[TimeAggregation] = None
    category_breakdown: Optional[CategoryBreakdown] = None
    member_breakdown: Optional[MemberBreakdown] = None
    summary: Optional[str] = None

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

def aggregate_transactions(
    transactions: List[DecryptedTransaction],
    timeframe: str,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    primary_currency: str = "USD",
    calculate_daily: bool = True
) -> TimeAggregation:
    currency_totals: Dict[str, float] = {}
    
    for tx in transactions:
        currency_totals[tx.currency] = currency_totals.get(tx.currency, 0.0) + tx.amount

    effective_currency = primary_currency
    if primary_currency not in currency_totals and len(currency_totals) == 1:
        effective_currency = next(iter(currency_totals))

    daily_breakdown: Dict[str, float] = {}
    category_breakdown: Dict[str, float] = {}
    if calculate_daily:
        for tx in transactions:
            if tx.currency == effective_currency:
                date_str = tx.timestamp.strftime("%Y-%m-%d")
                daily_breakdown[date_str] = daily_breakdown.get(date_str, 0.0) + tx.amount
                
    for tx in transactions:
        if tx.currency == effective_currency:
            category_breakdown[tx.category] = category_breakdown.get(tx.category, 0.0) + tx.amount

    total_amount = currency_totals.get(effective_currency, 0.0)
    tx_count = len(transactions)
    avg = total_amount / tx_count if tx_count > 0 else 0.0

    return TimeAggregation(
        timeframe=timeframe,
        start_time=start_time,
        end_time=end_time,
        total_amount=round(total_amount, 2),
        primary_currency=effective_currency,
        currency_totals={k: round(v, 2) for k, v in currency_totals.items()},
        transaction_count=tx_count,
        average_per_transaction=round(avg, 2),
        daily_breakdown={k: round(v, 2) for k, v in daily_breakdown.items()},
        category_breakdown={k: round(v, 2) for k, v in category_breakdown.items()}
    )

def aggregate_by_category(
    transactions: List[DecryptedTransaction],
    timeframe: str = "all_time",
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    primary_currency: str = "USD",
    overall_total: Optional[float] = None
) -> CategoryBreakdown:
    categories_dict: Dict[str, CategorySpending] = {}
    
    currency_totals_all: Dict[str, float] = {}
    for tx in transactions:
        currency_totals_all[tx.currency] = currency_totals_all.get(tx.currency, 0.0) + tx.amount

    effective_currency = primary_currency
    if primary_currency not in currency_totals_all and len(currency_totals_all) == 1:
        effective_currency = next(iter(currency_totals_all))

    if overall_total is None:
        overall_total = sum(tx.amount for tx in transactions if tx.currency == effective_currency)
        
    for tx in transactions:
        cat = tx.category
        if cat not in categories_dict:
            categories_dict[cat] = CategorySpending(
                category=cat,
                total_amount=0.0,
                primary_currency=effective_currency,
                currency_totals={},
                transaction_count=0,
                percentage_of_total=None,
                average_per_transaction=0.0
            )
            
        c = categories_dict[cat]
        c.currency_totals[tx.currency] = c.currency_totals.get(tx.currency, 0.0) + tx.amount
        if tx.currency == effective_currency:
            c.total_amount += tx.amount
        c.transaction_count += 1
        
    for cat, c in categories_dict.items():
        if overall_total > 0:
            c.percentage_of_total = round((c.total_amount / overall_total) * 100, 2)
        else:
            c.percentage_of_total = None
            
        if c.transaction_count > 0:
            c.average_per_transaction = round(c.total_amount / c.transaction_count, 2)
        else:
            c.average_per_transaction = 0.0
            
        c.total_amount = round(c.total_amount, 2)
        c.currency_totals = {k: round(v, 2) for k, v in c.currency_totals.items()}
        
    sorted_categories = dict(sorted(categories_dict.items(), key=lambda item: item[1].total_amount, reverse=True))
    
    top_category = None
    top_category_amount = None
    
    if sorted_categories:
        top_cat_key = next(iter(sorted_categories))
        top_category = top_cat_key
        top_category_amount = sorted_categories[top_cat_key].total_amount
        
    return CategoryBreakdown(
        timeframe=timeframe,
        start_time=start_time,
        end_time=end_time,
        total_spending=round(overall_total, 2),
        primary_currency=effective_currency,
        categories=sorted_categories,
        top_category=top_category,
        top_category_amount=top_category_amount
    )

def aggregate_by_member(
    transactions: List[DecryptedTransaction],
    timeframe: str = "all_time",
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    primary_currency: str = "USD",
    overall_total: Optional[float] = None
) -> MemberBreakdown:
    members_by_id: Dict[UUID, MemberSpending] = {}
    
    currency_totals_all: Dict[str, float] = {}
    for tx in transactions:
        currency_totals_all[tx.currency] = currency_totals_all.get(tx.currency, 0.0) + tx.amount

    effective_currency = primary_currency
    if primary_currency not in currency_totals_all and len(currency_totals_all) == 1:
        effective_currency = next(iter(currency_totals_all))

    if overall_total is None:
        overall_total = sum(tx.amount for tx in transactions if tx.currency == effective_currency)
        
    category_totals_per_user_id: Dict[UUID, Dict[str, float]] = {}
    
    for tx in transactions:
        u_id = tx.user_id
        display_name = tx.user_name or "User"
        if u_id not in members_by_id:
            members_by_id[u_id] = MemberSpending(
                user_id=u_id,
                user_name=display_name,
                user_handle=tx.user_handle,
                total_amount=0.0,
                primary_currency=effective_currency,
                currency_totals={},
                transaction_count=0,
                percentage_of_total=None,
                average_per_transaction=0.0,
                top_category=None
            )
            
        m = members_by_id[u_id]
        m.currency_totals[tx.currency] = m.currency_totals.get(tx.currency, 0.0) + tx.amount
        if tx.currency == effective_currency:
            m.total_amount += tx.amount
        m.transaction_count += 1
        
        if u_id not in category_totals_per_user_id:
            category_totals_per_user_id[u_id] = {}
        if tx.currency == effective_currency:
            category_totals_per_user_id[u_id][tx.category] = category_totals_per_user_id[u_id].get(tx.category, 0.0) + tx.amount

    for u_id, m in members_by_id.items():
        if overall_total > 0:
            m.percentage_of_total = round((m.total_amount / overall_total) * 100, 2)
        else:
            m.percentage_of_total = None
            
        if m.transaction_count > 0:
            m.average_per_transaction = round(m.total_amount / m.transaction_count, 2)
        else:
            m.average_per_transaction = 0.0
            
        m.total_amount = round(m.total_amount, 2)
        m.currency_totals = {k: round(v, 2) for k, v in m.currency_totals.items()}
        
        cats = category_totals_per_user_id.get(u_id, {})
        if cats:
            m.top_category = max(cats.items(), key=lambda x: x[1])[0]

    members_dict: Dict[str, MemberSpending] = {}
    name_counts: Dict[str, int] = {}
    for m in members_by_id.values():
        name_counts[m.user_name] = name_counts.get(m.user_name, 0) + 1
        
    for m in sorted(members_by_id.values(), key=lambda item: item.total_amount, reverse=True):
        if name_counts[m.user_name] > 1:
            if m.user_handle:
                key_name = f"{m.user_name} ({m.user_handle})"
            else:
                key_name = f"{m.user_name} ({str(m.user_id)[:6]})"
        else:
            key_name = m.user_name
        members_dict[key_name] = m

    top_spender = None
    top_spender_amount = None
    
    if members_dict:
        top_spender_key = next(iter(members_dict))
        top_spender = top_spender_key
        top_spender_amount = members_dict[top_spender_key].total_amount
        
    return MemberBreakdown(
        timeframe=timeframe,
        start_time=start_time,
        end_time=end_time,
        total_spending=round(overall_total, 2),
        primary_currency=effective_currency,
        members=members_dict,
        top_spender=top_spender,
        top_spender_amount=top_spender_amount
    )

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

def compute_period_comparison(
    current_aggregation: TimeAggregation,
    previous_transactions: List[DecryptedTransaction],
    previous_timeframe: str,
    prev_start: Optional[datetime],
    prev_end: Optional[datetime]
) -> PeriodComparison:
    prev_total = sum(tx.amount for tx in previous_transactions if tx.currency == current_aggregation.primary_currency)
    prev_count = len(previous_transactions)
    
    diff = current_aggregation.total_amount - prev_total
    
    pct_change = None
    if prev_total > 0:
        pct_change = (diff / prev_total) * 100
        
    return PeriodComparison(
        previous_timeframe=previous_timeframe,
        previous_start_time=prev_start,
        previous_end_time=prev_end,
        previous_total_amount=round(prev_total, 2),
        previous_transaction_count=prev_count,
        difference_amount=round(diff, 2),
        percentage_change=round(pct_change, 2) if pct_change is not None else None
    )

def _build_summary_prompt_context(
    query_result: QueryResult, 
    user_name: Optional[str] = None,
    family_name: Optional[str] = None,
    member_names: Optional[List[str]] = None
) -> str:
    ctx = []
    if family_name:
        ctx.append(f"Family Group: {family_name}")
    if member_names:
        ctx.append(f"Family Members: {', '.join(member_names)}")
    elif user_name:
        ctx.append(f"User: {user_name}")
    ctx.append(f"Timeframe: {query_result.intent.timeframe}")
    if query_result.aggregation:
        agg = query_result.aggregation
        ctx.append(f"Total spending: {agg.total_amount:.2f} {agg.primary_currency}")
        if len(agg.currency_totals) > 1:
            multi_curr = ", ".join(f"{v:.2f} {k}" for k, v in agg.currency_totals.items())
            ctx.append(f"Currencies involved: {multi_curr}")
        ctx.append(f"Transaction count: {agg.transaction_count}")
        ctx.append(f"Average per transaction: {agg.average_per_transaction:.2f} {agg.primary_currency}")
        
        if agg.comparison:
            comp = agg.comparison
            ctx.append(f"Comparison vs {comp.previous_timeframe}:")
            ctx.append(f"- Previous total: {comp.previous_total_amount:.2f} {agg.primary_currency}")
            ctx.append(f"- Difference: {comp.difference_amount:.2f} {agg.primary_currency}")
            if comp.percentage_change is not None:
                dir_str = "increase" if comp.percentage_change > 0 else "decrease" if comp.percentage_change < 0 else "no change"
                ctx.append(f"- Change: {abs(comp.percentage_change):.2f}% {dir_str}")

    if query_result.category_breakdown and query_result.category_breakdown.top_category:
        cb = query_result.category_breakdown
        top_cat = cb.top_category
        top_amt = cb.top_category_amount
        pct = cb.categories[top_cat].percentage_of_total if top_cat in cb.categories else None
        pct_str = f" ({pct:.1f}% of total)" if pct is not None else ""
        ctx.append(f"Top spending category: {top_cat}: {top_amt:.2f} {cb.primary_currency}{pct_str}")

    if query_result.member_breakdown and len(query_result.member_breakdown.members) > 1:
        mb = query_result.member_breakdown
        ctx.append("Member Breakdown:")
        for name, m in mb.members.items():
            pct = f", {m.percentage_of_total:.1f}% of total" if m.percentage_of_total is not None else ""
            top = f", Top category: {m.top_category}" if m.top_category else ""
            ctx.append(f"- {name}: {m.total_amount:.2f} {m.primary_currency} ({m.transaction_count} transactions{pct}{top})")

    if query_result.transactions:
        samples = []
        for tx in query_result.transactions[:5]: # Take up to 5 concepts
            contributor = f" by {tx.user_name}" if tx.user_name else ""
            samples.append(f"{tx.concept} ({tx.amount:.2f} {tx.currency}{contributor})")
        ctx.append("Sample transactions: " + ", ".join(samples))
        
    return "\n".join(ctx)

def generate_fallback_summary(
    query_result: QueryResult, 
    user_name: Optional[str] = None,
    family_name: Optional[str] = None,
    member_names: Optional[List[str]] = None
) -> str:
    greeting = f"Hi {user_name}! " if user_name else ""
    tf = query_result.intent.timeframe.replace('_', ' ')
    
    is_family_query = (query_result.intent.scope == "family") or (family_name is not None) or (member_names is not None)
    
    if query_result.intent.member_filter:
        subject = query_result.intent.member_filter
        has_spent = "has"
        hasn_t = "hasn't"
    elif family_name:
        subject = f"Your family ({family_name})"
        has_spent = "has"
        hasn_t = "hasn't"
    elif is_family_query:
        subject = "Your family"
        has_spent = "has"
        hasn_t = "hasn't"
    else:
        subject = "You"
        has_spent = "have"
        hasn_t = "haven't"
    
    if query_result.total_count == 0:
        curr = query_result.aggregation.primary_currency if query_result.aggregation else "USD"
        return f"{greeting}{subject} {hasn_t} logged any expenses for {tf} yet (Total: 0.00 {curr})."
        
    if not query_result.aggregation:
        return f"{greeting}Here are your results for {tf}."
        
    agg = query_result.aggregation
    total_str = f"{agg.total_amount:.2f} {agg.primary_currency}"
    
    if len(agg.currency_totals) > 1:
        total_str += " (" + ", ".join(f"{v:.2f} {k}" for k, v in agg.currency_totals.items() if k != agg.primary_currency) + ")"
        
    top_cat_str = ""
    if query_result.category_breakdown and query_result.category_breakdown.top_category:
        cb = query_result.category_breakdown
        top_cat_str = f" (Top category: {cb.top_category} at {cb.top_category_amount:.2f} {cb.primary_currency})"
        
    comp_str = ""
    if agg.comparison:
        comp = agg.comparison
        if comp.difference_amount == 0.0:
            comp_str = f" That's the exact same total as {comp.previous_timeframe.replace('_', ' ')} ({comp.previous_total_amount:.2f} {agg.primary_currency})!"
        elif comp.percentage_change is not None:
            more_less = "more" if comp.difference_amount > 0 else "less"
            comp_str = f" That's {abs(comp.difference_amount):.2f} {agg.primary_currency} ({abs(comp.percentage_change):.2f}%) {more_less} than {comp.previous_timeframe.replace('_', ' ')} ({comp.previous_total_amount:.2f} {agg.primary_currency})!"
            
    member_str = ""
    if query_result.member_breakdown and len(query_result.member_breakdown.members) > 1 and not query_result.intent.member_filter:
        mb = query_result.member_breakdown
        member_parts = [f"{name}: {m.total_amount:.2f}" for name, m in mb.members.items()]
        member_str = f" ({'; '.join(member_parts)})"
            
    return f"{greeting}{subject} {has_spent} spent {total_str} across {agg.transaction_count} transactions this {tf}{member_str}{top_cat_str}.{comp_str}"

class QueryService:
    _instance: Optional['QueryService'] = None
    _lock = threading.Lock()

    def __new__(cls) -> 'QueryService':
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(QueryService, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.client = ollama.AsyncClient(host=settings.OLLAMA_BASE_URL)
        self.model = settings.OLLAMA_MODEL
        self.encryption_service = EncryptionService()
        self._initialized = True

    def _resolve_date_range(self, timeframe: str, start_date_str: Optional[str], end_date_str: Optional[str], reference_time: Optional[datetime] = None) -> tuple[Optional[datetime], Optional[datetime]]:
        ref_time = reference_time or datetime.now(timezone.utc)
        
        if timeframe == "today":
            start_time = ref_time.replace(hour=0, minute=0, second=0, microsecond=0)
            end_time = ref_time.replace(hour=23, minute=59, second=59, microsecond=999999)
            return start_time, end_time
        elif timeframe == "yesterday":
            yesterday = ref_time - timedelta(days=1)
            start_time = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
            end_time = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
            return start_time, end_time
        elif timeframe == "this_week":
            start_time = (ref_time - timedelta(days=ref_time.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
            end_time = ref_time.replace(hour=23, minute=59, second=59, microsecond=999999) # up to current day end
            return start_time, end_time
        elif timeframe == "last_week":
            start_of_this_week = (ref_time - timedelta(days=ref_time.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
            start_time = start_of_this_week - timedelta(days=7)
            end_time = start_of_this_week - timedelta(microseconds=1)
            return start_time, end_time
        elif timeframe == "this_month":
            start_time = ref_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end_time = ref_time.replace(hour=23, minute=59, second=59, microsecond=999999)
            return start_time, end_time
        elif timeframe == "last_month":
            first_of_this_month = ref_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end_time = first_of_this_month - timedelta(microseconds=1)
            start_time = end_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            return start_time, end_time
        elif timeframe == "custom":
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

    def _decrypt_transaction(self, tx: Transaction, user_name: Optional[str] = None, user_handle: Optional[str] = None) -> Optional[DecryptedTransaction]:
        amount_str = self.encryption_service.decrypt(tx.amount)
        if not amount_str:
            return None
        concept_str = self.encryption_service.decrypt(tx.concept)
        if not concept_str:
            return None
        
        amount, currency = _parse_amount_string(amount_str)
        return DecryptedTransaction(
            id=tx.id,
            family_id=tx.family_id,
            user_id=tx.user_id,
            user_name=user_name,
            user_handle=user_handle,
            amount=amount,
            currency=currency,
            concept=concept_str,
            category=tx.category,
            timestamp=tx.timestamp
        )

    def _fetch_and_decrypt_transactions(self, family_id: UUID, start_time: Optional[datetime], end_time: Optional[datetime], category: Optional[str], concept_keyword: Optional[str], member_filter: Optional[str] = None) -> List[DecryptedTransaction]:
        with Session(engine) as session:
            users = session.exec(select(User).where(User.family_id == family_id)).all()
            user_map = {u.id: (u.full_name or u.username or "User", f"@{u.username}" if u.username else None) for u in users}

            query = select(Transaction).where(Transaction.family_id == family_id)
            if start_time:
                query = query.where(Transaction.timestamp >= start_time)
            if end_time:
                query = query.where(Transaction.timestamp <= end_time)
            if category:
                query = query.where(Transaction.category == category)
            
            query = query.order_by(Transaction.timestamp.desc())
            db_transactions = session.exec(query).all()
            
            results = []
            for tx in db_transactions:
                u_name, u_handle = user_map.get(tx.user_id, ("User", None))
                decrypted = self._decrypt_transaction(tx, u_name, u_handle)
                if not decrypted:
                    continue
                if concept_keyword:
                    if concept_keyword.lower() not in decrypted.concept.lower():
                        continue
                if member_filter:
                    target = member_filter.strip().lower().lstrip("@")
                    name_match = (decrypted.user_name and target in decrypted.user_name.lower())
                    handle_match = (decrypted.user_handle and target in decrypted.user_handle.lower())
                    if not (name_match or handle_match):
                        continue
                results.append(decrypted)
            return results

    async def parse_intent(self, text: str, reference_time: Optional[datetime] = None) -> ParsedQueryIntent:
        if not text or not text.strip():
            raise ValueError("Query string cannot be empty")
        
        ref_time = reference_time or datetime.now(timezone.utc)
        current_date_str = ref_time.strftime("%Y-%m-%d %H:%M:%S UTC")
        
        system_prompt = f"""You are a financial query parser. Your task is to extract intent, timeframe, and filters from the user's plain English query.
Current Date: {current_date_str}

Intents:
- "export_data": If the user wants to export or download data (e.g., "export my data", "export to csv"). Set `export_format` to "csv" or "json" based on the query.
- "spending_summary": If the user is asking a question about their spending (e.g., "how much did I spend", "summary of last week", "family total", "how much did we spend?", "our expenses", "what did the family spend on groceries?"). Set `scope` to "family" if it's a family query. Extract target member names into `member_filter` for questions like "Who spent what this month?", "What did Maria spend this week?", "Who spent the most today?", "Show me Tony's expenses", "Breakdown by family member", "Who bought coffee?".
- "log_expense": If the user is logging a new expense or purchase (e.g., "15 for coffee", "I bought shoes for 50", "Uber 20 dollars"). For this intent, timeframe and category can be null.
- "delete_account": If the user wants to permanently delete their account and data (e.g., "delete my account", "remove my data", "delete all my transactions", "erase my account", "forget me").
- "create_family": If the user wants to create a new family group or rename theirs (e.g., "create family The Smiths", "/createfamily vacation"). Extract the name into `family_name`.
- "generate_invite": If the user wants to invite someone to their family group (e.g., "invite family member", "generate invite link").
- "family_info": If the user wants to see information about their family group (e.g., "my family", "family info").
- "notion_manage": If the user wants to connect, disconnect, or check the status of their Notion workspace (e.g., "connect notion", "notion status", "disconnect notion").

Allowed canonical categories: "Food/Drink", "Transport", "Rent/Bills", "Shopping", "Leisure", "Other".
Map synonyms (e.g. "groceries" -> "Food/Drink", "utilities" -> "Rent/Bills") to these canonical categories.
Standard timeframes: "today", "yesterday", "this_week", "last_week", "this_month", "last_month", "custom", "all_time".
Extract `concept_keyword` if the user asks about a specific place or item (e.g., "Starbucks", "Uber")."""

        try:
            response = await asyncio.wait_for(
                self.client.chat(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": text}
                    ],
                    format=ParsedQueryIntent.model_json_schema(),
                ),
                timeout=60.0
            )
            intent_json = response.message.content
            intent = ParsedQueryIntent.model_validate_json(intent_json)
            return intent
        except asyncio.TimeoutError as e:
            logger.error(f"Ollama query request timed out: {e}")
            raise QueryProcessingError(f"Ollama request timed out after 60.0 seconds: {e}")
        except Exception as e:
            logger.error(f"Error processing query with Ollama: {e}")
            raise QueryProcessingError(f"Failed to process query with Ollama: {e}")

    async def process_query(
        self, 
        text: str, 
        family_id: UUID, 
        user_name: Optional[str] = None, 
        generate_summary: bool = True, 
        reference_time: Optional[datetime] = None,
        family_name: Optional[str] = None,
        member_names: Optional[List[str]] = None
    ) -> QueryResult:
        ref_time = reference_time or datetime.now(timezone.utc)
        start_exec_time = time.time()
        
        intent = await self.parse_intent(text, reference_time)

        start_time, end_time = self._resolve_date_range(intent.timeframe, intent.start_date, intent.end_date, ref_time)
        
        try:
            transactions = await asyncio.to_thread(
                self._fetch_and_decrypt_transactions,
                family_id, start_time, end_time, intent.category, intent.concept_keyword, intent.member_filter
            )
        except Exception as e:
            logger.error(f"Database query error in process_query: {e}")
            raise QueryProcessingError(f"Database query failed: {e}")

        aggregation = aggregate_transactions(
            transactions=transactions,
            timeframe=intent.timeframe,
            start_time=start_time,
            end_time=end_time,
            primary_currency=settings.DEFAULT_CURRENCY,
            calculate_daily=True
        )

        prev_tf, prev_start, prev_end = _resolve_comparison_timeframe(intent.timeframe, ref_time)
        if prev_tf:
            prev_txs = await asyncio.to_thread(
                self._fetch_and_decrypt_transactions,
                family_id, prev_start, prev_end, intent.category, intent.concept_keyword
            )
            aggregation.comparison = compute_period_comparison(
                current_aggregation=aggregation,
                previous_transactions=prev_txs,
                previous_timeframe=prev_tf,
                prev_start=prev_start,
                prev_end=prev_end
            )

        category_breakdown = aggregate_by_category(
            transactions=transactions,
            timeframe=intent.timeframe,
            start_time=start_time,
            end_time=end_time,
            primary_currency=settings.DEFAULT_CURRENCY,
            overall_total=aggregation.total_amount
        )

        member_breakdown = aggregate_by_member(
            transactions=transactions,
            timeframe=intent.timeframe,
            start_time=start_time,
            end_time=end_time,
            primary_currency=settings.DEFAULT_CURRENCY,
            overall_total=aggregation.total_amount
        )

        elapsed = time.time() - start_exec_time
        logger.info(f"[3s Audit] Aggregation query took {elapsed:.2f} seconds (timeframe: {intent.timeframe}, family_id: {family_id})")
        logger.info(f"[3s Audit] Category query took {elapsed:.2f} seconds (category: {intent.category}, timeframe: {intent.timeframe}, family_id: {family_id})")

        result = QueryResult(
            intent=intent,
            resolved_start_time=start_time,
            resolved_end_time=end_time,
            transactions=transactions,
            total_count=len(transactions),
            aggregation=aggregation,
            category_breakdown=category_breakdown,
            member_breakdown=member_breakdown
        )
        
        if generate_summary:
            result.summary = await self.generate_summary(result, user_name=user_name, use_llm=True, family_name=family_name, member_names=member_names)
            
        return result

    async def generate_summary(
        self, 
        query_result: QueryResult, 
        user_name: Optional[str] = None, 
        use_llm: bool = True,
        family_name: Optional[str] = None,
        member_names: Optional[List[str]] = None
    ) -> str:
        if not use_llm:
            return generate_fallback_summary(query_result, user_name, family_name, member_names)
            
        start_exec_time = time.time()
        
        system_prompt = """You are a warm, supportive, empathetic, and encouraging personal financial assistant.
Your job is to generate a conversational summary of the user's spending based EXACTLY on the provided factual context.
Use appropriate, tasteful emojis (e.g., ☕ for food/drink, 🚗 for transport, 📉/📈 for comparison, 🎉 for under budget, 💡 for insights).
STRICT FACTUAL FIDELITY: You must strictly reflect ONLY the numbers, categories, dates, and concepts provided in the prompt context. NEVER invent dollar amounts, merchants, or comparison percentages.
Conciseness: Keep the summary between 2 and 4 sentences.
If total spending is 0, provide a friendly, reassuring message.
If summarizing family or group spending, frame the summary from a collective perspective (e.g. "The Smith Family has spent..." or "Together, you have spent..."). Provide empathetic, transparent per-member attribution when multiple contributors exist (e.g. "This month, your family spent $205.50 across 5 transactions. Tony contributed $120.00 (mostly on Shopping) and Maria spent $85.50 on Groceries.")."""

        context_data = _build_summary_prompt_context(query_result, user_name, family_name, member_names)
        user_prompt = f"Please summarize the following spending data:\n{context_data}"
        
        llm_used = False
        summary = ""
        
        try:
            response = await asyncio.wait_for(
                self.client.chat(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ]
                ),
                timeout=30.0
            )
            summary = response.message.content.strip() if response.message and response.message.content else ""
            if summary:
                llm_used = True
        except Exception as e:
            logger.warning(f"Ollama summary generation failed or timed out: {e}")
            
        if not summary:
            summary = generate_fallback_summary(query_result, user_name, family_name, member_names)
            
        elapsed = time.time() - start_exec_time
        logger.info(f"[3s Audit] Conversational summary generation took {elapsed:.2f} seconds (llm_used: {llm_used})")
        
        return summary
        
    async def get_spending_summary(
        self, 
        family_id: UUID, 
        timeframe: str = "this_month", 
        category: Optional[str] = None, 
        user_name: Optional[str] = None, 
        reference_time: Optional[datetime] = None,
        family_name: Optional[str] = None,
        member_names: Optional[List[str]] = None
    ) -> str:
        intent = ParsedQueryIntent(
            intent="spending_summary",
            timeframe=timeframe,
            category=category,
            scope="family" if family_name else "personal"
        )
        
        ref_time = reference_time or datetime.now(timezone.utc)
        start_time, end_time = self._resolve_date_range(intent.timeframe, intent.start_date, intent.end_date, ref_time)
        
        transactions = await asyncio.to_thread(
            self._fetch_and_decrypt_transactions,
            family_id, start_time, end_time, intent.category, intent.concept_keyword, None
        )
        
        aggregation = aggregate_transactions(
            transactions=transactions,
            timeframe=intent.timeframe,
            start_time=start_time,
            end_time=end_time,
            primary_currency=settings.DEFAULT_CURRENCY,
            calculate_daily=True
        )

        prev_tf, prev_start, prev_end = _resolve_comparison_timeframe(intent.timeframe, ref_time)
        if prev_tf:
            prev_txs = await asyncio.to_thread(
                self._fetch_and_decrypt_transactions,
                family_id, prev_start, prev_end, intent.category, intent.concept_keyword, None
            )
            aggregation.comparison = compute_period_comparison(
                current_aggregation=aggregation,
                previous_transactions=prev_txs,
                previous_timeframe=prev_tf,
                prev_start=prev_start,
                prev_end=prev_end
            )

        category_breakdown = aggregate_by_category(
            transactions=transactions,
            timeframe=intent.timeframe,
            start_time=start_time,
            end_time=end_time,
            primary_currency=settings.DEFAULT_CURRENCY,
            overall_total=aggregation.total_amount
        )
        
        member_breakdown = aggregate_by_member(
            transactions=transactions,
            overall_total=aggregation.total_amount
        )
        
        qr = QueryResult(
            intent=intent,
            resolved_start_time=start_time,
            resolved_end_time=end_time,
            transactions=transactions,
            total_count=len(transactions),
            aggregation=aggregation,
            category_breakdown=category_breakdown,
            member_breakdown=member_breakdown
        )
        
        return await self.generate_summary(qr, user_name=user_name, use_llm=True, family_name=family_name, member_names=member_names)

    async def get_time_aggregation(
        self, family_id: UUID, timeframe: str = "this_month", 
        primary_currency: Optional[str] = None, include_comparison: bool = False, 
        reference_time: Optional[datetime] = None
    ) -> TimeAggregation:
        ref_time = reference_time or datetime.now(timezone.utc)
        curr = primary_currency or settings.DEFAULT_CURRENCY
        start_time, end_time = self._resolve_date_range(timeframe, None, None, ref_time)
        
        transactions = await asyncio.to_thread(
            self._fetch_and_decrypt_transactions,
            family_id, start_time, end_time, None, None, None
        )
        
        aggregation = aggregate_transactions(
            transactions=transactions,
            timeframe=timeframe,
            start_time=start_time,
            end_time=end_time,
            primary_currency=curr,
            calculate_daily=True
        )
        
        if include_comparison:
            prev_tf, prev_start, prev_end = _resolve_comparison_timeframe(timeframe, ref_time)
            if prev_tf:
                prev_txs = await asyncio.to_thread(
                    self._fetch_and_decrypt_transactions,
                    family_id, prev_start, prev_end, None, None, None
                )
                aggregation.comparison = compute_period_comparison(
                    current_aggregation=aggregation,
                    previous_transactions=prev_txs,
                    previous_timeframe=prev_tf,
                    prev_start=prev_start,
                    prev_end=prev_end
                )
                
        return aggregation

    async def get_category_aggregation(
        self, family_id: UUID, category: Optional[str] = None, timeframe: str = "this_month", 
        primary_currency: Optional[str] = None, reference_time: Optional[datetime] = None
    ) -> CategoryBreakdown:
        start_exec_time = time.time()
        ref_time = reference_time or datetime.now(timezone.utc)
        curr = primary_currency or settings.DEFAULT_CURRENCY
        start_time, end_time = self._resolve_date_range(timeframe, None, None, ref_time)
        resolved_category = resolve_category_alias(category) if category else None
        
        transactions = await asyncio.to_thread(
            self._fetch_and_decrypt_transactions,
            family_id, start_time, end_time, resolved_category, None
        )
        
        breakdown = aggregate_by_category(
            transactions=transactions,
            timeframe=timeframe,
            start_time=start_time,
            end_time=end_time,
            primary_currency=curr
        )
        
        elapsed = time.time() - start_exec_time
        logger.info(f"[3s Audit] Category query took {elapsed:.2f} seconds (category: {resolved_category}, timeframe: {timeframe}, family_id: {family_id})")
        
        return breakdown
