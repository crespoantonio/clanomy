import html
from typing import Optional, List, Dict, Any
from src.core.config import settings
from src.services.query.models import QueryResult, DecryptedScheduledBill
from src.services.query.date_resolver import _sanitize_concept_for_prompt

def format_currency_dict(curr_dict: Optional[Dict[str, float]], default_curr: str = "USD") -> str:
    if not curr_dict:
        return f"0.00 {default_curr}"
    if len(curr_dict) == 1:
        c, val = next(iter(curr_dict.items()))
        return f"{val:,.2f} {c}"
    return ", ".join(f"{val:,.2f} {c}" for c, val in sorted(curr_dict.items()))

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
            top = f", Top category: {m.top_category}" if m.top_category else ""
            if m.total_earned > 0:
                pct = f", {m.percentage_of_total:.1f}% of expenses" if m.percentage_of_total is not None else ""
                inc_str = format_currency_dict(m.income_currency_totals, m.primary_currency) if m.income_currency_totals else f"{m.total_earned:,.2f} {m.primary_currency}"
                exp_str = format_currency_dict(m.expense_currency_totals, m.primary_currency) if m.expense_currency_totals else f"{m.total_spent:,.2f} {m.primary_currency}"
                ctx.append(f"- {name}: Earned {inc_str} | Spent {exp_str} (Net: {m.net_balance:+,.2f} {m.primary_currency}{pct}{top})")
            else:
                pct = f", {m.percentage_of_total:.1f}% of total" if m.percentage_of_total is not None else ""
                amt_str = f"{m.total_amount:,.2f} {m.primary_currency}"
                ctx.append(f"- {name}: {amt_str} ({m.transaction_count} transactions{pct}{top})")

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

def format_timezone_footer(tz_name: Optional[str] = None) -> str:
    tz = tz_name or getattr(settings, "DEFAULT_TIMEZONE", "America/Argentina/Buenos_Aires")
    return f"💡 <i>Active timezone: {tz}. Change with /timezone</i>"

def format_month_summary(
    query_result: QueryResult, 
    family_name: Optional[str] = None,
    timeframe_label: Optional[str] = None,
    tz_name: Optional[str] = None
) -> str:
    agg = query_result.aggregation
    curr = agg.primary_currency if agg else (settings.DEFAULT_CURRENCY or "USD")
    raw_tf = timeframe_label or (query_result.intent.timeframe or "this_month").replace('_', ' ').capitalize()
    tf_str = html.escape(raw_tf, quote=False)
    fam_label = f" ({html.escape(family_name, quote=False)})" if family_name else ""
    
    lines = [
        f"📊 <b>Family Summary — {tf_str}</b>{fam_label}",
        "━━━━━━━━━━━━━━━━━━━━━"
    ]
    
    if not agg or query_result.total_count == 0:
        lines.append("<i>No transactions recorded for this month yet.</i>")
        lines.append("")
        lines.append(format_timezone_footer(tz_name))
        return "\n".join(lines)
        
    has_multi_curr = len(agg.currency_totals) > 1 or len(agg.income_currency_totals) > 1 or len(agg.expense_currency_totals) > 1
    
    if has_multi_curr:
        lines.append("💰 <b>Household Income:</b>")
        if agg.income_currency_totals:
            for c, val in sorted(agg.income_currency_totals.items()):
                lines.append(f"  • {val:,.2f} {c}")
        else:
            lines.append(f"  • 0.00 {curr}")
            
        lines.append("💸 <b>Household Expenses:</b>")
        if agg.expense_currency_totals:
            for c, val in sorted(agg.expense_currency_totals.items()):
                lines.append(f"  • {val:,.2f} {c}")
        else:
            lines.append(f"  • 0.00 {curr}")
    else:
        sign = "+" if agg.net_balance > 0 else ""
        sav_str = f" ({agg.savings_rate:.1f}% saved)" if agg.savings_rate is not None and agg.total_income > 0 else ""
        lines.append(f"💰 <b>Household Income:</b> {agg.total_income:,.2f} {curr}")
        lines.append(f"💸 <b>Household Expenses:</b> {agg.total_expenses:,.2f} {curr}")
        lines.append(f"📈 <b>Net Family Balance:</b> {sign}{agg.net_balance:,.2f} {curr}{sav_str}")

    # Member Breakdown
    if query_result.member_breakdown and query_result.member_breakdown.members:
        lines.append("")
        lines.append("👥 <b>Member Breakdown:</b>")
        for name, m in query_result.member_breakdown.members.items():
            escaped_name = html.escape(name, quote=False)
            if has_multi_curr:
                m_inc = format_currency_dict(m.income_currency_totals, curr)
                m_exp = format_currency_dict(m.expense_currency_totals, curr)
                lines.append(f"👤 <b>{escaped_name}</b>:")
                lines.append(f"  • Incomes: {m_inc}")
                lines.append(f"  • Expenses: {m_exp}")
            else:
                lines.append(f"👤 <b>{escaped_name}</b>:")
                lines.append(f"  • Incomes: {m.total_earned:,.2f} {curr} | Expenses: {m.total_spent:,.2f} {curr}")
                sign_m = "+" if m.net_balance > 0 else ""
                lines.append(f"  • Net: {sign_m}{m.net_balance:,.2f} {curr}")
                
    lines.append("")
    lines.append(f"📊 <i>Total logs: {agg.transaction_count} transaction(s)</i>")
    lines.append("")
    lines.append(format_timezone_footer(tz_name))
    return "\n".join(lines)

def format_me_summary(
    query_result: QueryResult, 
    user_name: Optional[str] = None,
    timeframe_label: Optional[str] = None,
    tz_name: Optional[str] = None
) -> str:
    agg = query_result.aggregation
    curr = agg.primary_currency if agg else (settings.DEFAULT_CURRENCY or "USD")
    raw_tf = timeframe_label or (query_result.intent.timeframe or "this_month").replace('_', ' ').capitalize()
    tf_str = html.escape(raw_tf, quote=False)
    u_label = f" — {html.escape(user_name, quote=False)}" if user_name else ""
    
    lines = [
        f"👤 <b>Personal Summary — {tf_str}</b>{u_label}",
        "━━━━━━━━━━━━━━━━━━━━━"
    ]
    
    if not agg or query_result.total_count == 0:
        lines.append("<i>You haven't logged any transactions for this month yet.</i>")
        lines.append("")
        lines.append(format_timezone_footer(tz_name))
        return "\n".join(lines)

    has_multi_curr = len(agg.currency_totals) > 1 or len(agg.income_currency_totals) > 1 or len(agg.expense_currency_totals) > 1

    if has_multi_curr:
        lines.append("💰 <b>Income:</b>")
        if agg.income_currency_totals:
            for c, val in sorted(agg.income_currency_totals.items()):
                lines.append(f"  • {val:,.2f} {c}")
        else:
            lines.append(f"  • 0.00 {curr}")
            
        lines.append("💸 <b>Expenses:</b>")
        if agg.expense_currency_totals:
            for c, val in sorted(agg.expense_currency_totals.items()):
                lines.append(f"  • {val:,.2f} {c}")
        else:
            lines.append(f"  • 0.00 {curr}")
    else:
        sign = "+" if agg.net_balance > 0 else ""
        sav_str = f" ({agg.savings_rate:.1f}% saved)" if agg.savings_rate is not None and agg.total_income > 0 else ""
        lines.append(f"💰 <b>Income:</b> {agg.total_income:,.2f} {curr}")
        lines.append(f"💸 <b>Expenses:</b> {agg.total_expenses:,.2f} {curr}")
        lines.append(f"📈 <b>Net Balance:</b> {sign}{agg.net_balance:,.2f} {curr}{sav_str}")

    # Top Categories
    if agg.expense_category_breakdown:
        lines.append("")
        lines.append("🏷️ <b>Top Categories:</b>")
        sorted_cats = sorted(agg.expense_category_breakdown.items(), key=lambda x: x[1], reverse=True)[:4]
        for cat, val in sorted_cats:
            pct = (val / agg.total_expenses * 100) if agg.total_expenses > 0 else 0.0
            lines.append(f"  • {cat}: {val:,.2f} {curr} ({pct:.1f}%)")

    lines.append("")
    lines.append(f"📊 <i>Total logs: {agg.transaction_count} transaction(s)</i>")
    lines.append("")
    lines.append(format_timezone_footer(tz_name))
    return "\n".join(lines)

def format_today_summary(
    query_result: QueryResult,
    is_family: bool = True,
    tz_name: Optional[str] = None
) -> str:
    agg = query_result.aggregation
    curr = agg.primary_currency if agg else (settings.DEFAULT_CURRENCY or "USD")
    
    scope_title = "Household" if is_family else "Personal"
    lines = [
        f"📅 <b>Today's Activity ({scope_title})</b>",
        "━━━━━━━━━━━━━━━━━━━━━"
    ]
    
    if not query_result.transactions:
        lines.append("<i>No transactions logged today.</i>")
        lines.append("")
        lines.append(format_timezone_footer(tz_name))
        return "\n".join(lines)
        
    has_multi_curr = agg and (len(agg.currency_totals) > 1 or len(agg.income_currency_totals) > 1 or len(agg.expense_currency_totals) > 1)
    
    if agg:
        if has_multi_curr:
            exp_str = format_currency_dict(agg.expense_currency_totals, curr)
            inc_str = format_currency_dict(agg.income_currency_totals, curr)
            lines.append(f"💸 Spent Today: {exp_str}")
            if agg.income_count > 0:
                lines.append(f"💰 Earned Today: {inc_str}")
        else:
            lines.append(f"💸 Spent Today: {agg.total_expenses:,.2f} {curr}")
            if agg.total_income > 0:
                lines.append(f"💰 Earned Today: {agg.total_income:,.2f} {curr}")
                
    lines.append("")
    lines.append("📝 <b>Today's Transactions:</b>")
    for tx in query_result.transactions[:10]:
        tx_type_icon = "🟢" if getattr(tx, "type", "expense") == "income" else "🔴"
        u_str = f" ({html.escape(tx.user_name, quote=False)})" if is_family and tx.user_name else ""
        c_esc = html.escape(tx.concept or "", quote=False)
        cat_esc = html.escape(tx.category or "", quote=False)
        lines.append(f"{tx_type_icon} {tx.amount:,.2f} {tx.currency} — {c_esc} [<i>{cat_esc}</i>]{u_str}")
        
    if len(query_result.transactions) > 10:
        lines.append(f"<i>...and {len(query_result.transactions) - 10} more</i>")
        
    lines.append("")
    lines.append(format_timezone_footer(tz_name))
    return "\n".join(lines)

def format_bills_summary(
    bills: List[DecryptedScheduledBill],
    timeframe_label: str = "This Month",
    tz_name: Optional[str] = None
) -> str:
    escaped_tf = html.escape(timeframe_label, quote=False)
    lines = [
        f"⏰ <b>Upcoming Bills — {escaped_tf}</b>",
        "━━━━━━━━━━━━━━━━━━━━━"
    ]
    
    if not bills:
        lines.append("<i>No pending bills due for this period! 🎉</i>")
        lines.append("")
        lines.append(format_timezone_footer(tz_name))
        return "\n".join(lines)
        
    totals_by_curr: dict[str, float] = {}
    for b in bills:
        totals_by_curr[b.currency] = totals_by_curr.get(b.currency, 0.0) + b.amount
        date_str = b.due_date.strftime("%b %d") if hasattr(b.due_date, "strftime") else str(b.due_date)
        u_str = f" • by {html.escape(b.user_name, quote=False)}" if b.user_name else ""
        c_esc = html.escape(b.concept or "", quote=False)
        cat_esc = html.escape(b.category or "", quote=False)
        lines.append(f"🗓️ <b>{date_str}</b>: {b.amount:,.2f} {b.currency} — {c_esc} (<i>{cat_esc}</i>){u_str}")
        
    lines.append("")
    total_parts = [f"{amt:,.2f} {curr}" for curr, amt in totals_by_curr.items()]
    total_str = " + ".join(total_parts)
    lines.append(f"📌 <b>Total Pending:</b> {total_str}")
    lines.append(f"📋 <i>{len(bills)} pending commitment(s)</i>")
    lines.append("")
    lines.append(format_timezone_footer(tz_name))
    return "\n".join(lines)

def format_balance_summary(
    query_result: QueryResult,
    tz_name: Optional[str] = None
) -> str:
    agg = query_result.aggregation
    curr = agg.primary_currency if agg else (settings.DEFAULT_CURRENCY or "USD")
    raw_tf = (query_result.intent.timeframe or "this_month").replace('_', ' ').capitalize()
    tf_str = html.escape(raw_tf, quote=False)
    
    lines = [
        f"💰 <b>Cash Flow & Balance — {tf_str}</b>",
        "━━━━━━━━━━━━━━━━━━━━━"
    ]
    
    if not agg or query_result.total_count == 0:
        lines.append("<i>No transactions recorded for this period.</i>")
        lines.append("")
        lines.append(format_timezone_footer(tz_name))
        return "\n".join(lines)
        
    has_multi_curr = len(agg.currency_totals) > 1 or len(agg.income_currency_totals) > 1 or len(agg.expense_currency_totals) > 1
    
    if has_multi_curr:
        inc_str = format_currency_dict(agg.income_currency_totals, curr)
        exp_str = format_currency_dict(agg.expense_currency_totals, curr)
        lines.append(f"💰 Total Incomes: {inc_str}")
        lines.append(f"💸 Total Expenses: {exp_str}")
    else:
        sign = "+" if agg.net_balance > 0 else ""
        sav_str = f" ({agg.savings_rate:.1f}% savings rate)" if agg.savings_rate is not None and agg.total_income > 0 else ""
        lines.append(f"💰 Total Incomes: {agg.total_income:,.2f} {curr}")
        lines.append(f"💸 Total Expenses: {agg.total_expenses:,.2f} {curr}")
        lines.append(f"📈 Net Cash Flow: {sign}{agg.net_balance:,.2f} {curr}{sav_str}")
        
    lines.append("")
    lines.append(f"📊 <i>Total: {agg.transaction_count} transaction(s)</i>")
    lines.append("")
    lines.append(format_timezone_footer(tz_name))
    return "\n".join(lines)


