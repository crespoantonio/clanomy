from datetime import datetime
from typing import Optional, List, Dict
from uuid import UUID
from src.services.query.models import (
    DecryptedTransaction,
    TimeAggregation,
    CategorySpending,
    CategoryBreakdown,
    MemberSpending,
    MemberBreakdown,
    PeriodComparison
)

def aggregate_transactions(
    transactions: List[DecryptedTransaction],
    timeframe: str,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    primary_currency: str = "USD",
    calculate_daily: bool = True
) -> TimeAggregation:
    currency_totals: Dict[str, float] = {}
    income_currency_totals: Dict[str, float] = {}
    expense_currency_totals: Dict[str, float] = {}
    exchange_sold_totals: Dict[str, float] = {}
    exchange_received_totals: Dict[str, float] = {}
    all_currencies = set()
    
    has_non_exchange = any((getattr(t, "category", "") or "").strip().lower() != "exchange" for t in transactions)
    exchange_count = 0

    for tx in transactions:
        all_currencies.add(tx.currency)
        tx_type = getattr(tx, "type", "expense") or "expense"
        is_exchange = (getattr(tx, "category", "") or "").strip().lower() == "exchange"
        
        if is_exchange:
            exchange_count += 1
            if tx_type == "expense":
                exchange_sold_totals[tx.currency] = exchange_sold_totals.get(tx.currency, 0.0) + tx.amount
            else:
                exchange_received_totals[tx.currency] = exchange_received_totals.get(tx.currency, 0.0) + tx.amount

            if not has_non_exchange:
                currency_totals[tx.currency] = currency_totals.get(tx.currency, 0.0) + tx.amount
        else:
            currency_totals[tx.currency] = currency_totals.get(tx.currency, 0.0) + tx.amount
            if tx_type == "income":
                income_currency_totals[tx.currency] = income_currency_totals.get(tx.currency, 0.0) + tx.amount
            else:
                expense_currency_totals[tx.currency] = expense_currency_totals.get(tx.currency, 0.0) + tx.amount

    effective_currency = primary_currency
    if primary_currency not in currency_totals and len(currency_totals) == 1:
        effective_currency = next(iter(currency_totals))

    daily_breakdown: Dict[str, float] = {}
    daily_income_breakdown: Dict[str, float] = {}
    daily_expense_breakdown: Dict[str, float] = {}
    category_breakdown: Dict[str, float] = {}
    income_category_breakdown: Dict[str, float] = {}
    expense_category_breakdown: Dict[str, float] = {}

    income_count = 0
    expense_count = 0

    if calculate_daily:
        for tx in transactions:
            if tx.currency == effective_currency:
                is_exchange = (getattr(tx, "category", "") or "").strip().lower() == "exchange"
                date_str = tx.timestamp.strftime("%Y-%m-%d")
                tx_type = getattr(tx, "type", "expense") or "expense"
                if not is_exchange or not has_non_exchange:
                    daily_breakdown[date_str] = daily_breakdown.get(date_str, 0.0) + tx.amount
                if not is_exchange:
                    if tx_type == "income":
                        daily_income_breakdown[date_str] = daily_income_breakdown.get(date_str, 0.0) + tx.amount
                    else:
                        daily_expense_breakdown[date_str] = daily_expense_breakdown.get(date_str, 0.0) + tx.amount
                
    for tx in transactions:
        tx_type = getattr(tx, "type", "expense") or "expense"
        is_exchange = (getattr(tx, "category", "") or "").strip().lower() == "exchange"
        if not is_exchange:
            if tx_type == "income":
                income_count += 1
            else:
                expense_count += 1

        if tx.currency == effective_currency:
            if not is_exchange or not has_non_exchange:
                category_breakdown[tx.category] = category_breakdown.get(tx.category, 0.0) + tx.amount
            if not is_exchange:
                if tx_type == "income":
                    income_category_breakdown[tx.category] = income_category_breakdown.get(tx.category, 0.0) + tx.amount
                else:
                    expense_category_breakdown[tx.category] = expense_category_breakdown.get(tx.category, 0.0) + tx.amount

    total_income = income_currency_totals.get(effective_currency, 0.0)
    total_expenses = expense_currency_totals.get(effective_currency, 0.0)
    net_balance = total_income - total_expenses
    
    if total_income > 0:
        savings_rate = round((net_balance / total_income) * 100, 2)
    else:
        savings_rate = 0.0 if total_expenses == 0 else None

    net_currency_positions: Dict[str, float] = {}
    for curr_code in all_currencies:
        inc = income_currency_totals.get(curr_code, 0.0)
        exp = expense_currency_totals.get(curr_code, 0.0)
        sold = exchange_sold_totals.get(curr_code, 0.0)
        recv = exchange_received_totals.get(curr_code, 0.0)
        net_currency_positions[curr_code] = round(inc - exp - sold + recv, 2)

    if has_non_exchange:
        total_amount = sum(tx.amount for tx in transactions if tx.currency == effective_currency and (getattr(tx, "category", "") or "").strip().lower() != "exchange")
    else:
        total_amount = sum(tx.amount for tx in transactions if tx.currency == effective_currency)

    tx_count = len(transactions)
    avg = (total_amount / tx_count) if tx_count > 0 else 0.0

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
        category_breakdown={k: round(v, 2) for k, v in category_breakdown.items()},
        total_income=round(total_income, 2),
        total_expenses=round(total_expenses, 2),
        net_balance=round(net_balance, 2),
        savings_rate=savings_rate,
        income_currency_totals={k: round(v, 2) for k, v in income_currency_totals.items()},
        expense_currency_totals={k: round(v, 2) for k, v in expense_currency_totals.items()},
        income_count=income_count,
        expense_count=expense_count,
        income_category_breakdown={k: round(v, 2) for k, v in income_category_breakdown.items()},
        expense_category_breakdown={k: round(v, 2) for k, v in expense_category_breakdown.items()},
        daily_income_breakdown={k: round(v, 2) for k, v in daily_income_breakdown.items()},
        daily_expense_breakdown={k: round(v, 2) for k, v in daily_expense_breakdown.items()},
        exchange_count=exchange_count,
        exchange_sold_totals={k: round(v, 2) for k, v in exchange_sold_totals.items()},
        exchange_received_totals={k: round(v, 2) for k, v in exchange_received_totals.items()},
        net_currency_positions=net_currency_positions
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
    has_non_exchange = any((getattr(t, "category", "") or "").strip().lower() != "exchange" for t in transactions)
    
    currency_totals_all: Dict[str, float] = {}
    for tx in transactions:
        is_exchange = (getattr(tx, "category", "") or "").strip().lower() == "exchange"
        if not is_exchange or not has_non_exchange:
            currency_totals_all[tx.currency] = currency_totals_all.get(tx.currency, 0.0) + tx.amount

    effective_currency = primary_currency
    if primary_currency not in currency_totals_all and len(currency_totals_all) == 1:
        effective_currency = next(iter(currency_totals_all))

    if overall_total is None:
        if has_non_exchange:
            overall_total = sum(tx.amount for tx in transactions if tx.currency == effective_currency and (getattr(tx, "category", "") or "").strip().lower() != "exchange")
        else:
            overall_total = sum(tx.amount for tx in transactions if tx.currency == effective_currency)
        
    for tx in transactions:
        cat = tx.category
        is_exchange = (cat or "").strip().lower() == "exchange"
        if is_exchange and has_non_exchange:
            continue

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
        if overall_total and overall_total > 0:
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
    has_non_exchange = any((getattr(t, "category", "") or "").strip().lower() != "exchange" for t in transactions)
    
    currency_totals_all: Dict[str, float] = {}
    for tx in transactions:
        is_exchange = (getattr(tx, "category", "") or "").strip().lower() == "exchange"
        if not is_exchange or not has_non_exchange:
            currency_totals_all[tx.currency] = currency_totals_all.get(tx.currency, 0.0) + tx.amount

    effective_currency = primary_currency
    if primary_currency not in currency_totals_all and len(currency_totals_all) == 1:
        effective_currency = next(iter(currency_totals_all))

    if overall_total is None:
        if has_non_exchange:
            overall_total = sum(tx.amount for tx in transactions if tx.currency == effective_currency and (getattr(tx, "category", "") or "").strip().lower() != "exchange")
        else:
            overall_total = sum(tx.amount for tx in transactions if tx.currency == effective_currency)
        
    category_totals_per_user_id: Dict[UUID, Dict[str, float]] = {}
    
    for tx in transactions:
        u_id = tx.user_id
        display_name = tx.user_name or "User"
        is_exchange = (getattr(tx, "category", "") or "").strip().lower() == "exchange"
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
        if not is_exchange or not has_non_exchange:
            m.currency_totals[tx.currency] = m.currency_totals.get(tx.currency, 0.0) + tx.amount

        tx_type = getattr(tx, "type", "expense") or "expense"
        if is_exchange:
            if tx_type == "expense":
                m.exchange_sold_totals[tx.currency] = m.exchange_sold_totals.get(tx.currency, 0.0) + tx.amount
            else:
                m.exchange_received_totals[tx.currency] = m.exchange_received_totals.get(tx.currency, 0.0) + tx.amount
        else:
            if tx_type == "income":
                m.income_currency_totals[tx.currency] = m.income_currency_totals.get(tx.currency, 0.0) + tx.amount
                if tx.currency == effective_currency:
                    m.total_earned += tx.amount
            else:
                m.expense_currency_totals[tx.currency] = m.expense_currency_totals.get(tx.currency, 0.0) + tx.amount
                if tx.currency == effective_currency:
                    m.total_spent += tx.amount

            if tx.currency == effective_currency:
                m.total_amount += tx.amount
        if not has_non_exchange and tx.currency == effective_currency and is_exchange:
            m.total_amount += tx.amount

        m.net_balance = m.total_earned - m.total_spent
        m.transaction_count += 1
        
        if u_id not in category_totals_per_user_id:
            category_totals_per_user_id[u_id] = {}
        if tx.currency == effective_currency and (not is_exchange or not has_non_exchange):
            category_totals_per_user_id[u_id][tx.category] = category_totals_per_user_id[u_id].get(tx.category, 0.0) + tx.amount

    for u_id, m in members_by_id.items():
        if overall_total and overall_total > 0:
            m.percentage_of_total = round((m.total_spent / overall_total) * 100, 2)
        else:
            m.percentage_of_total = None
            
        if m.transaction_count > 0:
            m.average_per_transaction = round(m.total_amount / m.transaction_count, 2)
        else:
            m.average_per_transaction = 0.0
            
        m.total_amount = round(m.total_amount, 2)
        m.currency_totals = {k: round(v, 2) for k, v in m.currency_totals.items()}
        m.income_currency_totals = {k: round(v, 2) for k, v in m.income_currency_totals.items()}
        m.expense_currency_totals = {k: round(v, 2) for k, v in m.expense_currency_totals.items()}
        m.exchange_sold_totals = {k: round(v, 2) for k, v in m.exchange_sold_totals.items()}
        m.exchange_received_totals = {k: round(v, 2) for k, v in m.exchange_received_totals.items()}

        member_currencies = set(m.income_currency_totals.keys()) | set(m.expense_currency_totals.keys()) | set(m.exchange_sold_totals.keys()) | set(m.exchange_received_totals.keys())
        for c in member_currencies:
            inc = m.income_currency_totals.get(c, 0.0)
            exp = m.expense_currency_totals.get(c, 0.0)
            sold = m.exchange_sold_totals.get(c, 0.0)
            recv = m.exchange_received_totals.get(c, 0.0)
            m.net_currency_positions[c] = round(inc - exp - sold + recv, 2)
        
        cats = category_totals_per_user_id.get(u_id, {})
        m.category_totals = {k: round(v, 2) for k, v in cats.items()}
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
