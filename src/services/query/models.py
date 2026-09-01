from datetime import datetime
from typing import Optional, List, Dict, Literal
from uuid import UUID
from pydantic import BaseModel, field_validator
from src.services.extraction.normalizers import normalize_category_value

class QueryProcessingError(Exception):
    """Custom exception raised when query processing fails."""
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
        "salary": ["salary", "paycheck", "wages", "wage", "payroll", "stipend", "base salary"],
        "bonus": ["bonus", "bonuses", "commission", "commissions", "tips", "tip", "reward", "incentive"],
        "freelance": ["freelance", "side gig", "side-gig", "consulting", "gig", "contract", "contractor", "client payment", "invoice", "invoices", "freelancing", "freelancer"],
        "investment": ["investment", "investments", "dividends", "dividend", "stocks", "stock", "crypto", "interest", "capital gains", "yield"],
        "gift": ["gift", "gifts", "presents", "present", "allowance", "monetary gift"],
        "sale": ["sale", "sales", "sold items", "sold item", "selling", "ebay", "vinted", "wallapop", "marketplace", "sold"],
        "other": ["other", "misc", "miscellaneous", "uncategorized", "fees", "bank fees", "donations"]
    }
    
    canonical_mapping = {
        "food/drink": "Food/Drink",
        "transport": "Transport",
        "rent/bills": "Rent/Bills",
        "shopping": "Shopping",
        "leisure": "Leisure",
        "salary": "Salary",
        "bonus": "Bonus",
        "freelance": "Freelance",
        "investment": "Investment",
        "gift": "Gift",
        "sale": "Sale",
        "other": "Other Income"
    }
    
    if cleaned in canonical_mapping:
        return canonical_mapping[cleaned]
        
    for canonical, alias_list in aliases.items():
        if cleaned in alias_list:
            return canonical_mapping[canonical]
            
    return "Other"

class ParsedQueryIntent(BaseModel):
    intent: Literal[
        "spending_summary", 
        "income_summary", 
        "net_cash_flow", 
        "net_balance", 
        "cash_flow_summary", 
        "query_comparison", 
        "export_data", 
        "delete_account", 
        "notion_manage", 
        "generate_invite", 
        "create_family", 
        "join_family", 
        "log_expense", 
        "query", 
        "query_spending", 
        "query_income",
        "earnings_summary",
        "family_info",
        "remove_member",
        "leave_family",
        "edit_last",
        "undo_last",
        "manage_currency",
        "upcoming_bills"
    ]
    timeframe: Optional[str] = "this_month"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    category: Optional[str] = None
    concept_keyword: Optional[str] = None
    export_format: Optional[str] = "csv"
    family_name: Optional[str] = None
    target_member: Optional[str] = None
    scope: Optional[str] = "family"
    member_filter: Optional[str] = None
    query_type: Optional[str] = None
    new_type: Optional[str] = None
    new_amount: Optional[float] = None
    new_currency: Optional[str] = None
    new_category: Optional[str] = None
    new_concept: Optional[str] = None
    target_amount: Optional[float] = None
    target_currency: Optional[str] = None
    target_concept: Optional[str] = None

    @field_validator('category', 'new_category')
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
    type: str = "expense"
    timestamp: datetime

class DecryptedScheduledBill(BaseModel):
    id: UUID
    family_id: UUID
    user_id: UUID
    user_name: Optional[str] = None
    user_handle: Optional[str] = None
    amount: float
    currency: str
    concept: str
    category: str
    due_date: datetime
    status: str = "pending"
    paid_transaction_id: Optional[UUID] = None
    created_at: datetime

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
    total_spent: float = 0.0
    total_earned: float = 0.0
    net_balance: float = 0.0

class MemberBreakdown(BaseModel):
    timeframe: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    total_spending: float
    primary_currency: str = "USD"
    members: Dict[str, MemberSpending]
    top_spender: Optional[str] = None
    top_spender_amount: Optional[float] = None
    top_earner: Optional[str] = None
    top_earner_amount: Optional[float] = None

class TimeAggregation(BaseModel):
    timeframe: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    total_amount: float = 0.0
    primary_currency: str = "USD"
    currency_totals: Dict[str, float] = {}
    transaction_count: int = 0
    average_per_transaction: float = 0.0
    daily_breakdown: Dict[str, float] = {}
    comparison: Optional[PeriodComparison] = None
    category_breakdown: Dict[str, float] = {}

    total_income: float = 0.0
    total_expenses: float = 0.0
    net_balance: float = 0.0
    savings_rate: Optional[float] = None
    income_currency_totals: Dict[str, float] = {}
    expense_currency_totals: Dict[str, float] = {}
    income_count: int = 0
    expense_count: int = 0
    income_category_breakdown: Dict[str, float] = {}
    expense_category_breakdown: Dict[str, float] = {}
    daily_income_breakdown: Dict[str, float] = {}
    daily_expense_breakdown: Dict[str, float] = {}

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
