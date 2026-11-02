"""
Telegram HTML Message Templates Facade for Clanomy.
Re-exports all template strings, constants, and formatting functions from domain-scoped submodules:
- src.templates.common: Localization, errors, and formatting helpers
- src.templates.onboarding: Terms of service, privacy policy, welcome, and timezone prompts
- src.templates.billing: Subscription tiers, quota notices, and Paddle billing alerts
- src.templates.bills: Scheduled bills, settlement cards, and reminders
- src.templates.transactions: Single/batch confirmations, cash flow, exchange, and undo
- src.templates.workspace: Family workspace management, invites, and Notion templates
"""

from src.templates.common import *
from src.templates.onboarding import *
from src.templates.billing import *
from src.templates.bills import *
from src.templates.transactions import *
from src.templates.workspace import *
