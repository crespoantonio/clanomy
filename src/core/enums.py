from enum import Enum


class IntentType(str, Enum):
    # Financial Logging & Modifications
    LOG_EXPENSE = "log_expense"
    LOG_TRANSACTION = "log_transaction"
    EDIT_LAST = "edit_last"
    UNDO_LAST = "undo_last"

    # Financial Queries
    SPENDING_SUMMARY = "spending_summary"
    QUERY_SPENDING = "query_spending"
    INCOME_SUMMARY = "income_summary"
    QUERY_INCOME = "query_income"
    EARNINGS_SUMMARY = "earnings_summary"
    NET_CASH_FLOW = "net_cash_flow"
    NET_BALANCE = "net_balance"
    CASH_FLOW_SUMMARY = "cash_flow_summary"
    UPCOMING_BILLS = "upcoming_bills"
    EXPORT_DATA = "export_data"

    # Family & Workspace Operations
    CREATE_FAMILY = "create_family"
    GENERATE_INVITE = "generate_invite"
    FAMILY_INFO = "family_info"
    LEAVE_FAMILY = "leave_family"
    REMOVE_MEMBER = "remove_member"

    # Account & Integration Management
    DELETE_ACCOUNT = "delete_account"
    NOTION_MANAGE = "notion_manage"
    MANAGE_CURRENCY = "manage_currency"


class PlanType(str, Enum):
    FREE = "free"
    SOLO_PRO = "solo_pro"
    FAMILY_PRO = "family_pro"


class BillStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    DISMISSED = "dismissed"
