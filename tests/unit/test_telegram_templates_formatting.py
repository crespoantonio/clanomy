import html
import asyncio
from uuid import uuid4
import pytest
import xml.etree.ElementTree as ET
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from src.templates import telegram_messages
from src.services.handlers.command_handler import CommandHandler
from src.services.query.formatters import (
    format_month_summary,
    format_me_summary,
    format_today_summary,
    format_bills_summary,
    format_balance_summary
)
from src.services.query.models import QueryResult, ParsedQueryIntent, DecryptedScheduledBill, DecryptedTransaction
from src.services.telegram_service import TelegramService


import re


def assert_valid_telegram_html(text: str):
    """
    Validates that the provided text is well-formed XML/HTML when wrapped in a root element.
    Telegram allows bare '&' surrounded by whitespace, so we normalize bare '&' before XML validation.
    """
    normalized = re.sub(r"&(?!(amp|lt|gt|quot|apos);)", "&amp;", text)
    try:
        ET.fromstring(f"<root>{normalized}</root>")
    except ET.ParseError as e:
        pytest.fail(f"Invalid Telegram HTML formatting: {e}\nContent was:\n{text}")


def test_static_template_constants_are_valid_html():
    """All static message templates in telegram_messages.py must be valid HTML."""
    constants = [
        telegram_messages.UNAUTHORIZED_ACCESS_MESSAGE,
        telegram_messages.UNSUPPORTED_FORMAT_MESSAGE,
        telegram_messages.SELF_HOSTED_UPGRADE_MESSAGE,
        telegram_messages.LIFETIME_PRO_CONFIRMATION,
        telegram_messages.SOLO_PRO_CONFIRMATION,
        telegram_messages.FAMILY_PRO_CONFIRMATION,
        telegram_messages.SOLO_PRO_MEMBER_NOTICE,
        telegram_messages.REFUND_PROCESSED_MESSAGE,
        telegram_messages.PLAN_EXPIRED_MESSAGE,
        telegram_messages.UPGRADE_MENU_INTRO,
        telegram_messages.UPGRADE_MENU_ANNUAL_INTRO,
        telegram_messages.BILLING_PORTAL_MESSAGE,
        telegram_messages.SUBSCRIPTION_CANCELLED_MESSAGE,
        telegram_messages.SUBSCRIPTION_PAYMENT_FAILED_MESSAGE,
        telegram_messages.LEAVE_FAMILY_ADMIN_ACTIVE_PRO_BLOCKED,
    ]
    for const in constants:
        assert_valid_telegram_html(const)


def test_welcome_message_all_plans_and_special_characters():
    """format_welcome_message must be valid HTML across all plan types and with special chars in user name."""
    user = MagicMock()
    user.full_name = "Tony <Pro & Hacker>"

    family = MagicMock()
    family.trial_ends_at = datetime.now(timezone.utc)
    family.monthly_tx_count = 10

    plans = ["trial", "free", "solo_pro", "family_pro", "lifetime_pro", None]

    for plan in plans:
        family.plan_type = plan
        rendered = telegram_messages.format_welcome_message(user, family if plan else None, {"first_name": "Tony"})
        
        # Verify no unescaped '<40ms' or latency claims exist
        assert "(<40ms)" not in rendered
        assert "40ms" not in rendered
        assert "fastest responses" in rendered or "free and don't count" in rendered

        # Verify HTML validity
        assert_valid_telegram_html(rendered)


def test_dynamic_family_prompts_with_special_characters():
    """Ensure dynamic family prompts escape arbitrary user/family strings containing <, >, and &."""
    fam = "Smith & Wesson <VIP>"
    adm = "John <The Admin> & Co"

    assert_valid_telegram_html(telegram_messages.format_leave_family_admin_prompt(fam, adm))
    assert_valid_telegram_html(telegram_messages.format_leave_family_member_prompt(fam, adm))
    assert_valid_telegram_html(telegram_messages.format_non_admin_upgrade_intro(fam, adm))
    assert_valid_telegram_html(telegram_messages.format_family_split_notice(adm))
    assert_valid_telegram_html(telegram_messages.format_member_graduated_notice(adm, "Family Pro & Lifetime"))


def test_help_command_is_valid_html():
    """The /help response must be valid HTML."""
    handler = CommandHandler()
    res = asyncio.run(handler.handle_help(MagicMock(), MagicMock()))
    assert_valid_telegram_html(res)


def test_formatters_with_malicious_or_special_concepts():
    """Formatters must properly escape transactions with &, <, > in concept, category, or user_name."""
    tx = DecryptedTransaction(
        id=uuid4(),
        family_id=uuid4(),
        user_id=uuid4(),
        user_name="Alice <Bob & Eve>",
        amount=50.0,
        currency="USD",
        concept="AT&T Bill <Due Today>",
        category="Utilities & Telecom",
        type="expense",
        timestamp=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc)
    )

    qr = QueryResult(
        intent=ParsedQueryIntent(intent="spending_summary", timeframe="this_month", scope="family"),
        resolved_start_time=datetime.now(timezone.utc),
        resolved_end_time=datetime.now(timezone.utc),
        transactions=[tx],
        total_count=1,
        aggregation=None
    )

    today_msg = format_today_summary(qr, is_family=True)
    assert_valid_telegram_html(today_msg)

    bill = DecryptedScheduledBill(
        id=uuid4(),
        family_id=uuid4(),
        user_id=uuid4(),
        user_name="Partner & Me",
        amount=120.0,
        currency="USD",
        concept="H&M <Sale>",
        category="Clothes & Fashion",
        due_date=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc)
    )
    bills_msg = format_bills_summary([bill], timeframe_label="This & Next Month")
    assert_valid_telegram_html(bills_msg)

    balance_msg = format_balance_summary(qr)
    assert_valid_telegram_html(balance_msg)


def test_telegram_fallback_resends_plain_text():
    """If Telegram returns 400 can't parse entities, fallback retries as plain text without parse_mode."""
    svc = TelegramService()

    raw_html = "<b>Hello</b> & <i>World</i> <tag>broken"
    import httpx

    call_count = 0
    sent_payloads = []

    async def mock_post(endpoint, json=None, **kwargs):
        nonlocal call_count
        call_count += 1
        sent_payloads.append(json)
        if call_count == 1:
            req = httpx.Request("POST", "http://test")
            resp = httpx.Response(400, text='{"description": "Bad Request: can\'t parse entities"}', request=req)
            raise httpx.HTTPStatusError("can't parse entities", request=req, response=resp)
        return httpx.Response(200, json={"ok": True})

    with patch.object(svc, "_post_with_retry", side_effect=mock_post):
        asyncio.run(svc.send_message(chat_id=123, text=raw_html, parse_mode="HTML"))

    assert call_count == 2
    # First call had parse_mode HTML and raw HTML
    assert sent_payloads[0]["parse_mode"] == "HTML"
    assert sent_payloads[0]["text"] == raw_html

    # Fallback call had parse_mode None and original text preserved
    assert "parse_mode" not in sent_payloads[1]
    assert sent_payloads[1]["text"] == raw_html
