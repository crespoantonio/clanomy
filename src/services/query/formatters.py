from typing import Optional, List
from src.core.config import settings
from src.services.query.models import QueryResult
from src.services.query.date_resolver import _sanitize_concept_for_prompt

def build_summary_prompt_context(
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
    ctx.append(f"Query Intent: {query_result.intent.intent}")
    
    if query_result.aggregation:
        agg = query_result.aggregation
        has_multi_curr = len(agg.currency_totals) > 1 or len(agg.income_currency_totals) > 1 or len(agg.expense_currency_totals) > 1
        
        if has_multi_curr:
            ctx.append("⚠️ MULTI-CURRENCY LEDGER: Transactions are recorded in multiple distinct currencies. DO NOT combine them into a single total or single net cash flow figure. Report each currency amount separately with its 3-letter ISO code.")
            if agg.expense_currency_totals:
                exp_list = ", ".join(f"{v:,.2f} {k}" for k, v in agg.expense_currency_totals.items())
                ctx.append(f"Total spending (expenses) by currency: {exp_list} across {agg.expense_count} transaction(s)")
            else:
                ctx.append(f"Total spending (expenses): 0.00 {agg.primary_currency}")
                
            if agg.income_currency_totals:
                inc_list = ", ".join(f"{v:,.2f} {k}" for k, v in agg.income_currency_totals.items())
                ctx.append(f"Total income (earnings) by currency: {inc_list} across {agg.income_count} transaction(s)")
            else:
                ctx.append(f"Total income (earnings): 0.00 {agg.primary_currency}")
        else:
            ctx.append(f"Total spending (expenses): {agg.total_expenses:,.2f} {agg.primary_currency} ({agg.expense_count} transactions)")
            ctx.append(f"Total income (earnings): {agg.total_income:,.2f} {agg.primary_currency} ({agg.income_count} transactions)")
            ctx.append(f"Net cash flow balance: {agg.net_balance:,.2f} {agg.primary_currency}")
            if agg.savings_rate is not None:
                ctx.append(f"Savings rate: {agg.savings_rate:.1f}%")

        ctx.append(f"Total transactions: {agg.transaction_count}")
        ctx.append(f"Average per transaction: {agg.average_per_transaction:,.2f} {agg.primary_currency}")

        if agg.income_category_breakdown:
            inc_cats = ", ".join(f"{k}: {v:,.2f} {agg.primary_currency}" for k, v in agg.income_category_breakdown.items())
            ctx.append(f"Income categories: {inc_cats}")
        if agg.expense_category_breakdown:
            exp_cats = ", ".join(f"{k}: {v:,.2f} {agg.primary_currency}" for k, v in agg.expense_category_breakdown.items())
            ctx.append(f"Expense categories: {exp_cats}")
        
        if agg.comparison:
            comp = agg.comparison
            ctx.append(f"Comparison vs {comp.previous_timeframe}:")
            ctx.append(f"- Previous total: {comp.previous_total_amount:,.2f} {agg.primary_currency}")
            ctx.append(f"- Difference: {comp.difference_amount:,.2f} {agg.primary_currency}")
            if comp.percentage_change is not None:
                dir_str = "increase" if comp.percentage_change > 0 else "decrease" if comp.percentage_change < 0 else "no change"
                ctx.append(f"- Change: {abs(comp.percentage_change):,.2f}% {dir_str}")

    if query_result.category_breakdown and query_result.category_breakdown.top_category:
        cb = query_result.category_breakdown
        top_cat = cb.top_category
        top_amt = cb.top_category_amount
        pct = cb.categories[top_cat].percentage_of_total if top_cat in cb.categories else None
        pct_str = f" ({pct:.1f}% of total)" if pct is not None else ""
        ctx.append(f"Top category: {top_cat}: {top_amt:,.2f} {cb.primary_currency}{pct_str}")

    if query_result.member_breakdown and len(query_result.member_breakdown.members) > 1:
        mb = query_result.member_breakdown
        ctx.append("Member Breakdown:")
        for name, m in mb.members.items():
            pct = f", {m.percentage_of_total:.1f}% of total" if m.percentage_of_total is not None else ""
            top = f", Top category: {m.top_category}" if m.top_category else ""
            ctx.append(f"- {name}: {m.total_amount:,.2f} {m.primary_currency} ({m.transaction_count} transactions{pct}{top})")

    if query_result.transactions:
        samples = []
        for tx in query_result.transactions[:5]:
            contributor = f" by {tx.user_name}" if tx.user_name else ""
            concept_sanitized = _sanitize_concept_for_prompt(tx.concept)
            samples.append(f"{concept_sanitized} ({tx.amount:,.2f} {tx.currency}{contributor})")
        ctx.append("Sample transactions: " + ", ".join(samples))
        
    return "\n".join(ctx)

_build_summary_prompt_context = build_summary_prompt_context

def generate_fallback_summary(
    query_result: QueryResult, 
    user_name: Optional[str] = None, 
    family_name: Optional[str] = None,
    member_names: Optional[List[str]] = None
) -> str:
    greeting = f"Hi {user_name}! " if user_name else ""
    tf_clean = (query_result.intent.timeframe or "").replace('_', ' ')
    if tf_clean.startswith("this ") or tf_clean.startswith("last "):
        tf_period = tf_clean
        tf_cap = tf_clean.capitalize()
    elif tf_clean in ["today", "yesterday", "all time"]:
        tf_period = tf_clean
        tf_cap = tf_clean.capitalize()
    else:
        tf_period = tf_clean
        tf_cap = tf_clean.capitalize()

    intent_type = query_result.intent.intent
    
    is_family_query = (query_result.intent.scope == "family") or (family_name is not None) or (member_names is not None)
    
    if query_result.intent.member_filter:
        subject = query_result.intent.member_filter
        has_verb = "has"
        hasn_t_verb = "hasn't"
    elif family_name:
        subject = f"Your family ({family_name})"
        has_verb = "has"
        hasn_t_verb = "hasn't"
    elif is_family_query:
        subject = "Your family"
        has_verb = "has"
        hasn_t_verb = "hasn't"
    else:
        subject = "You"
        has_verb = "have"
        hasn_t_verb = "haven't"
    
    agg = query_result.aggregation
    curr = agg.primary_currency if agg else (settings.DEFAULT_CURRENCY or "USD")

    # 1. Zero data states
    if query_result.total_count == 0:
        if intent_type in ["income_summary", "query_income", "earnings_summary"]:
            return f"{greeting}{subject} {hasn_t_verb} logged any income for {tf_period} yet (Total: 0.00 {curr})."
        elif intent_type in ["net_cash_flow", "net_balance", "cash_flow_summary"]:
            return f"{greeting}{subject} {hasn_t_verb} logged any income or expenses for {tf_period} yet (Net Balance: 0.00 {curr})."
        else:
            return f"{greeting}{subject} {hasn_t_verb} logged any expenses for {tf_period} yet (Total: 0.00 {curr})."
        
    if not agg:
        return f"{greeting}Here are your results for {tf_period}."

    has_multi_curr = len(agg.currency_totals) > 1 or len(agg.income_currency_totals) > 1 or len(agg.expense_currency_totals) > 1

    # 2. Income query fallback
    if intent_type in ["income_summary", "query_income", "earnings_summary"]:
        if has_multi_curr and agg.income_currency_totals:
            inc_str = ", ".join(f"{v:,.2f} {k}" for k, v in agg.income_currency_totals.items())
        else:
            inc_str = f"{agg.total_income:,.2f} {agg.primary_currency}"

        top_inc_cat_str = ""
        if agg.income_category_breakdown:
            top_inc_name = max(agg.income_category_breakdown.items(), key=lambda x: x[1])[0]
            top_inc_val = agg.income_category_breakdown[top_inc_name]
            top_inc_cat_str = f" (Top source: {top_inc_name} at {top_inc_val:,.2f} {agg.primary_currency})"

        cat_breakdown_str = ""
        if len(agg.income_category_breakdown) > 1:
            cat_breakdown_str = " (" + "; ".join(f"{k}: {v:,.2f}" for k, v in agg.income_category_breakdown.items()) + ")"

        return f"{greeting}{subject} {has_verb} earned {inc_str} across {agg.income_count} income transaction(s) {tf_period}{cat_breakdown_str or top_inc_cat_str}."

    # 3. Net cash flow / Net balance query fallback
    if intent_type in ["net_cash_flow", "net_balance", "cash_flow_summary"]:
        if has_multi_curr:
            inc_list = [f"{v:,.2f} {k}" for k, v in agg.income_currency_totals.items()] or [f"0.00 {agg.primary_currency}"]
            exp_list = [f"{v:,.2f} {k}" for k, v in agg.expense_currency_totals.items()] or [f"0.00 {agg.primary_currency}"]
            inc_formatted = ", ".join(inc_list)
            exp_formatted = ", ".join(exp_list)
            subj_str = subject.lower() if subject == "You" else subject
            return f"{greeting}{tf_cap}, {subj_str} earned {inc_formatted} and spent {exp_formatted} across {agg.transaction_count} transaction(s)."
            
        inc_formatted = f"{agg.total_income:,.2f} {agg.primary_currency}"
        exp_formatted = f"{agg.total_expenses:,.2f} {agg.primary_currency}"
        
        sign = "+" if agg.net_balance > 0 else ""
        net_formatted = f"{sign}{agg.net_balance:,.2f} {agg.primary_currency}"
        
        savings_rate_str = f" ({agg.savings_rate:.1f}% savings rate)" if agg.savings_rate is not None else ""
        
        if agg.net_balance >= 0:
            status_desc = f"leaving a net savings of {net_formatted}{savings_rate_str}"
        else:
            status_desc = f"resulting in a net deficit of {net_formatted}{savings_rate_str}"
            
        subj_str = subject.lower() if subject == "You" else subject
        return f"{greeting}{tf_cap}, {subj_str} earned {inc_formatted} and spent {exp_formatted}, {status_desc} across {agg.transaction_count} transaction(s)."

    # 4. Standard spending query fallback
    if has_multi_curr and agg.expense_currency_totals:
        total_str = ", ".join(f"{v:,.2f} {k}" for k, v in agg.expense_currency_totals.items())
    elif has_multi_curr and agg.currency_totals:
        total_str = ", ".join(f"{v:,.2f} {k}" for k, v in agg.currency_totals.items())
    else:
        total_str = f"{agg.total_amount:,.2f} {agg.primary_currency}"
        
    top_cat_str = ""
    if query_result.category_breakdown and query_result.category_breakdown.top_category:
        cb = query_result.category_breakdown
        top_cat_str = f" (Top category: {cb.top_category} at {cb.top_category_amount:,.2f} {cb.primary_currency})"
        
    comp_str = ""
    if agg.comparison:
        comp = agg.comparison
        if comp.difference_amount == 0.0:
            comp_str = f" That's the exact same total as {comp.previous_timeframe.replace('_', ' ')} ({comp.previous_total_amount:,.2f} {agg.primary_currency})!"
        elif comp.percentage_change is not None:
            more_less = "more" if comp.difference_amount > 0 else "less"
            comp_str = f" That's {abs(comp.difference_amount):,.2f} {agg.primary_currency} ({abs(comp.percentage_change):.2f}%) {more_less} than {comp.previous_timeframe.replace('_', ' ')} ({comp.previous_total_amount:,.2f} {agg.primary_currency})!"
            
    member_str = ""
    if query_result.member_breakdown and len(query_result.member_breakdown.members) > 1 and not query_result.intent.member_filter:
        mb = query_result.member_breakdown
        member_parts = [f"{name}: {m.total_amount:,.2f}" for name, m in mb.members.items()]
        member_str = f" ({'; '.join(member_parts)})"
            
    return f"{greeting}{subject} {has_verb} spent {total_str} across {agg.transaction_count} transactions {tf_period}{member_str}{top_cat_str}.{comp_str}"
