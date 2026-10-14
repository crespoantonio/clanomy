import logging
from typing import Optional, Literal, List, Dict, Any
from uuid import UUID
from datetime import datetime, timezone
from pydantic import BaseModel, Field

from src.core.config import settings
from src.services.query.service import QueryService
from src.services.query.models import ParsedQueryIntent, QueryResult, DecryptedTransaction
from src.services.query.aggregator import aggregate_transactions

logger = logging.getLogger(__name__)


# ---------------------------------------------------------
# Tool Input Schemas
# ---------------------------------------------------------

class QuerySavingsParams(BaseModel):
    currency: Optional[str] = Field(
        default=None,
        description="Optional 3-letter currency code to check specific balance for, e.g. 'USD', 'ARS', 'EUR'."
    )
    scope: Literal["family", "personal"] = Field(
        default="family",
        description="Whether to query the whole family/household or only the caller's personal balance."
    )


class QueryCashFlowParams(BaseModel):
    timeframe: str = Field(
        default="this_month",
        description="Timeframe for the query: 'today', 'yesterday', 'this_week', 'last_week', 'this_month', 'last_month', or 'all_time'."
    )
    category: Optional[str] = Field(
        default=None,
        description="Optional expense or income category filter, e.g. 'Food/Drink', 'Transport', 'Rent/Bills'."
    )
    currency: Optional[str] = Field(
        default=None,
        description="Optional 3-letter currency code filter."
    )
    scope: Literal["family", "personal"] = Field(
        default="family",
        description="Whether to query household activity or only caller's personal transactions."
    )


class QueryBillsParams(BaseModel):
    timeframe: str = Field(
        default="this_month",
        description="Timeframe for upcoming bills: 'this_month', 'next_month', 'this_week', or 'all'."
    )
    status: Literal["pending", "paid", "all"] = Field(
        default="pending",
        description="Status of bills to query."
    )


class QueryHistoryParams(BaseModel):
    months: int = Field(
        default=3,
        ge=1,
        le=12,
        description="Number of trailing months to compare (default 3)."
    )
    scope: Literal["family", "personal"] = Field(
        default="family",
        description="Scope of the comparison."
    )


class TransactionItemInput(BaseModel):
    amount: float = Field(..., gt=0, description="Amount of the transaction.")
    concept: str = Field(..., description="Clean merchant, concept, or description without filler verbs.")
    category: str = Field(default="Other", description="Standard financial category.")
    currency: Optional[str] = Field(default=None, description="3-letter currency code.")
    type: Literal["expense", "income"] = Field(default="expense", description="'expense' or 'income'.")
    due_date: Optional[str] = Field(default=None, description="YYYY-MM-DD date if scheduled future bill.")
    is_scheduled_bill: bool = Field(default=False, description="True if bill with future due date.")


class LogTransactionsParams(BaseModel):
    items: List[TransactionItemInput] = Field(..., min_length=1, description="List of 1 or more transactions to log.")
    is_exchange: bool = Field(default=False, description="True if this operation is a currency exchange.")


# ---------------------------------------------------------
# Declarative Gemini Tool Specifications
# ---------------------------------------------------------

CLANOMY_TOOLS_DECLARATIONS = [
    {
        "name": "query_savings",
        "description": "Query all-time cumulative savings, total net balance, or specific currency balances since inception. Call this whenever the user asks 'cuánto tengo en total', 'cuántos USD tengo', 'what is my total balance', or asks about overall accumulated money or savings.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "currency": {
                    "type": "STRING",
                    "description": "Optional 3-letter currency code, e.g. 'USD', 'ARS', 'EUR'."
                },
                "scope": {
                    "type": "STRING",
                    "enum": ["family", "personal"],
                    "description": "'family' for entire household, 'personal' for only caller's activity."
                }
            }
        }
    },
    {
        "name": "query_cash_flow",
        "description": "Query spending, incomes, net cash flow, or savings rate for a specific calendar timeframe (today, yesterday, this_week, this_month, last_month). Use when the user asks how much was spent, earned, or what the monthly/weekly balance is.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "timeframe": {
                    "type": "STRING",
                    "enum": ["today", "yesterday", "this_week", "last_week", "this_month", "last_month", "all_time"],
                    "description": "Calendar period to query."
                },
                "category": {
                    "type": "STRING",
                    "description": "Optional category filter, e.g. 'Food/Drink', 'Transport', 'Rent/Bills'."
                },
                "currency": {
                    "type": "STRING",
                    "description": "Optional 3-letter currency filter."
                },
                "scope": {
                    "type": "STRING",
                    "enum": ["family", "personal"],
                    "description": "'family' or 'personal'."
                }
            }
        }
    },
    {
        "name": "query_bills",
        "description": "Query upcoming, pending, or overdue scheduled bills and fixed expenses (e.g. rent, electricity, credit cards, subscriptions).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "timeframe": {
                    "type": "STRING",
                    "enum": ["this_month", "next_month", "this_week", "all"],
                    "description": "Timeframe of upcoming bills."
                },
                "status": {
                    "type": "STRING",
                    "enum": ["pending", "paid", "all"],
                    "description": "Status filter: 'pending', 'paid', or 'all'."
                }
            }
        }
    },
    {
        "name": "query_history",
        "description": "Query multi-month trailing history comparison (incomes, expenses, and net savings for the last 3 months). Use for questions asking for a monthly comparison, quarterly trend, or recent history.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "months": {
                    "type": "INTEGER",
                    "description": "Number of trailing months to compare (typically 3)."
                },
                "scope": {
                    "type": "STRING",
                    "enum": ["family", "personal"],
                    "description": "'family' or 'personal'."
                }
            }
        }
    }
]


# ---------------------------------------------------------
# Tool Executor Engine
# ---------------------------------------------------------

class AgentContext(BaseModel):
    user_id: UUID
    family_id: UUID
    user_name: Optional[str] = "You"
    family_name: Optional[str] = "Family"
    default_currency: str = "USD"
    timezone_name: str = "America/Argentina/Buenos_Aires"
    is_spanish: bool = False


async def execute_agent_tool(
    tool_name: str,
    args: Dict[str, Any],
    context: AgentContext,
    query_service: Optional[QueryService] = None
) -> Dict[str, Any]:
    """
    Executes a verified tool against Clanomy domain services in-memory,
    decrypting AES-GCM records securely and returning typed data.
    """
    qs = query_service or QueryService()
    effective_curr = context.default_currency or settings.DEFAULT_CURRENCY or "USD"

    try:
        if tool_name == "query_savings":
            params = QuerySavingsParams(**args)
            target_curr = (params.currency or "").upper().strip() or None
            is_personal = params.scope == "personal"

            all_txs = await qs._fetch_and_decrypt_transactions(
                context.family_id, None, None, None, None, None
            )
            if is_personal:
                all_txs = [t for t in all_txs if t.user_id == context.user_id]

            agg = aggregate_transactions(
                transactions=all_txs,
                timeframe="all_time",
                primary_currency=effective_curr,
                calculate_daily=False
            )

            positions = agg.net_currency_positions or {}
            single_curr_balance = agg.net_balance

            # If user asked for a specific currency (e.g. USD)
            specific_balance = None
            if target_curr:
                if target_curr in positions:
                    specific_balance = positions[target_curr]
                elif agg.primary_currency == target_curr and len(positions) <= 1:
                    specific_balance = single_curr_balance
                else:
                    specific_balance = 0.0

            return {
                "status": "success",
                "tool": "query_savings",
                "scope": params.scope,
                "requested_currency": target_curr,
                "specific_currency_balance": specific_balance,
                "primary_currency": agg.primary_currency,
                "net_balance_primary": single_curr_balance,
                "lifetime_incomes": agg.income_currency_totals,
                "lifetime_expenses": agg.expense_currency_totals,
                "currency_positions": positions,
                "total_transactions": agg.transaction_count
            }

        elif tool_name == "query_cash_flow":
            params = QueryCashFlowParams(**args)
            tf = params.timeframe
            is_personal = params.scope == "personal"

            ref_time = datetime.now(timezone.utc)
            start_t, end_t = qs._resolve_date_range(tf, None, None, ref_time, tz_name=context.timezone_name)

            all_txs = await qs._fetch_and_decrypt_transactions(
                context.family_id, start_t, end_t, params.category, None, None
            )
            if is_personal:
                all_txs = [t for t in all_txs if t.user_id == context.user_id]

            agg = aggregate_transactions(
                transactions=all_txs,
                timeframe=tf,
                start_time=start_t,
                end_time=end_t,
                primary_currency=effective_curr,
                calculate_daily=False
            )

            return {
                "status": "success",
                "tool": "query_cash_flow",
                "timeframe": tf,
                "scope": params.scope,
                "primary_currency": agg.primary_currency,
                "total_income": agg.total_income,
                "total_expenses": agg.total_expenses,
                "net_balance": agg.net_balance,
                "savings_rate_pct": agg.savings_rate,
                "income_by_currency": agg.income_currency_totals,
                "expense_by_currency": agg.expense_currency_totals,
                "top_expense_categories": agg.expense_category_breakdown,
                "transaction_count": agg.transaction_count
            }

        elif tool_name == "query_bills":
            params = QueryBillsParams(**args)
            ref_time = datetime.now(timezone.utc)
            start_t, end_t = qs._resolve_date_range(params.timeframe, None, None, ref_time, tz_name=context.timezone_name, future_inclusive=True)

            status_filter = None if params.status == "all" else params.status
            bills = await qs._fetch_and_decrypt_scheduled_bills(
                context.family_id, start_t, end_t, status_filter
            )

            bills_data = [
                {
                    "concept": b.concept,
                    "amount": b.amount,
                    "currency": b.currency,
                    "due_date": b.due_date.strftime("%Y-%m-%d") if b.due_date else None,
                    "status": b.status,
                    "category": b.category
                }
                for b in bills
            ]

            total_pending = sum(b.amount for b in bills if b.status == "pending" and b.currency == effective_curr)

            return {
                "status": "success",
                "tool": "query_bills",
                "timeframe": params.timeframe,
                "status_filter": params.status,
                "count": len(bills),
                "total_pending_primary": round(total_pending, 2),
                "primary_currency": effective_curr,
                "bills": bills_data
            }

        elif tool_name == "query_history":
            params = QueryHistoryParams(**args)
            from src.services.query.date_resolver import resolve_trailing_months
            ref_time = datetime.now(timezone.utc)
            trailing = resolve_trailing_months(n=params.months, reference_time=ref_time, tz_name=context.timezone_name)

            overall_start = trailing[0][2]
            overall_end = trailing[-1][3]

            all_txs = await qs._fetch_and_decrypt_transactions(
                context.family_id, overall_start, overall_end, None, None, None
            )
            if params.scope == "personal":
                all_txs = [t for t in all_txs if t.user_id == context.user_id]

            months_summary = []
            for y, m, s_utc, e_utc in trailing:
                m_txs = [
                    t for t in all_txs
                    if s_utc <= (t.timestamp if t.timestamp.tzinfo else t.timestamp.replace(tzinfo=timezone.utc)) <= e_utc
                ]
                m_agg = aggregate_transactions(m_txs, timeframe=f"{y}_{m:02d}", primary_currency=effective_curr, calculate_daily=False)
                months_summary.append({
                    "year": y,
                    "month": m,
                    "income": m_agg.total_income,
                    "expenses": m_agg.total_expenses,
                    "net": m_agg.net_balance,
                    "savings_rate_pct": m_agg.savings_rate,
                    "currency": effective_curr
                })

            overall_agg = aggregate_transactions(all_txs, timeframe="overall_trailing", primary_currency=effective_curr, calculate_daily=False)

            return {
                "status": "success",
                "tool": "query_history",
                "months_count": params.months,
                "months": months_summary,
                "overall_trailing_incomes": overall_agg.total_income,
                "overall_trailing_expenses": overall_agg.total_expenses,
                "overall_trailing_net": overall_agg.net_balance,
                "overall_savings_rate_pct": overall_agg.savings_rate,
                "primary_currency": effective_curr
            }

        else:
            return {"status": "error", "message": f"Unknown tool: {tool_name}"}

    except Exception as e:
        logger.error(f"Error executing agent tool '{tool_name}': {e}", exc_info=True)
        return {"status": "error", "message": str(e), "tool": tool_name}
