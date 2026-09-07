"""
Unit tests for Telegram presentation and orchestrator message templates.
Validates English baseline, Spanish localization, zero-quota deterministic hints,
and proper HTML escaping in src/templates/telegram_messages.py.
"""

import pytest
from src.templates.telegram_messages import (
    is_spanish_text,
    format_batch_bills_tip,
    format_spending_summary_tip,
    format_upcoming_bills_tip,
    format_batch_bills_header,
    format_batch_transactions_header,
    format_batch_total_pending,
    format_payload_too_long_message,
    format_single_expense_confirmation,
    format_single_income_confirmation,
    format_exchange_confirmation,
    format_unmatched_bill_claim,
    format_unhandled_query_message,
    format_audio_error_message,
    format_persistence_error_message,
    format_extraction_error_message,
    format_empty_message_error,
    format_generic_error_message,
    format_bill_settled_notice,
)


class TestLanguageDetection:
    def test_empty_or_none_defaults_to_english(self):
        assert is_spanish_text(None) is False
        assert is_spanish_text("") is False
        assert is_spanish_text("   ") is False

    def test_english_phrases_return_false(self):
        assert is_spanish_text("Spent 25 dollars on lunch with clients") is False
        assert is_spanish_text("How much did I spend this week?") is False
        assert is_spanish_text("Paid internet bill 50 USD") is False

    def test_spanish_phrases_return_true(self):
        assert is_spanish_text("Gaste 5000 en el super") is True
        assert is_spanish_text("Pago de internet 1500 pesos") is True
        assert is_spanish_text("¿Qué vence esta semana?") is True
        assert is_spanish_text("Cambie 100 dolares a 1200 pesos") is True
        assert is_spanish_text("Cobré mi sueldo de 2000 USD") is True


class TestProTipsAndQuotaHints:
    def test_format_batch_bills_tip_bilingual(self):
        en_tip = format_batch_bills_tip(is_spanish=False)
        assert "/bills" in en_tip
        assert "monthly AI quota" in en_tip
        assert "Ask me" in en_tip

        es_tip = format_batch_bills_tip(is_spanish=True)
        assert "/bills" in es_tip
        assert "créditos de IA" in es_tip
        assert "Pregúntame" in es_tip

    def test_format_spending_summary_tip_free_tier(self):
        en_tip = format_spending_summary_tip(is_spanish=False, plan_type="free")
        assert "/month or /me" in en_tip
        assert "doesn't use your monthly AI quota" in en_tip

        es_tip = format_spending_summary_tip(is_spanish=True, plan_type="free")
        assert "/month o /me" in es_tip
        assert "sin gastar tu cuota mensual de IA" in es_tip

    def test_format_spending_summary_tip_paid_tier(self):
        en_tip = format_spending_summary_tip(is_spanish=False, plan_type="solo_pro")
        assert "/month or /me" in en_tip
        assert "monthly AI quota" not in en_tip

        es_tip = format_spending_summary_tip(is_spanish=True, plan_type="solo_pro")
        assert "/month o /me" in es_tip
        assert "cuota mensual de IA" not in es_tip

    def test_format_upcoming_bills_tip_free_tier(self):
        en_tip = format_upcoming_bills_tip(is_spanish=False, plan_type="free")
        assert "/bills" in en_tip
        assert "doesn't use your monthly AI quota" in en_tip

        es_tip = format_upcoming_bills_tip(is_spanish=True, plan_type="free")
        assert "/bills" in es_tip
        assert "sin gastar tu cuota mensual de IA" in es_tip

    def test_format_upcoming_bills_tip_paid_tier(self):
        en_tip = format_upcoming_bills_tip(is_spanish=False, plan_type="duo_pro")
        assert "/bills" in en_tip
        assert "monthly AI quota" not in en_tip

        es_tip = format_upcoming_bills_tip(is_spanish=True, plan_type="duo_pro")
        assert "/bills" in es_tip
        assert "cuota mensual de IA" not in es_tip


class TestBatchHeadersAndMessages:
    def test_format_batch_bills_header(self):
        assert format_batch_bills_header(3, is_spanish=False) == "📋 <b>3 Scheduled Bill(s):</b>\n\n"
        assert format_batch_bills_header(3, is_spanish=True) == "📋 <b>3 Factura(s) Programada(s):</b>\n\n"

    def test_format_batch_transactions_header_incomes_only(self):
        en = format_batch_transactions_header(incomes_count=2, expenses_count=0, total_count=2, is_spanish=False)
        es = format_batch_transactions_header(incomes_count=2, expenses_count=0, total_count=2, is_spanish=True)
        assert en == "📋 <b>2 Income(s) Logged:</b>\n\n"
        assert es == "📋 <b>2 Ingreso(s) Registrado(s):</b>\n\n"

    def test_format_batch_transactions_header_expenses_only(self):
        en = format_batch_transactions_header(incomes_count=0, expenses_count=3, total_count=3, is_spanish=False)
        es = format_batch_transactions_header(incomes_count=0, expenses_count=3, total_count=3, is_spanish=True)
        assert en == "📋 <b>3 Expense(s) Logged:</b>\n\n"
        assert es == "📋 <b>3 Gasto(s) Registrado(s):</b>\n\n"

    def test_format_batch_transactions_header_mixed(self):
        en = format_batch_transactions_header(incomes_count=1, expenses_count=2, total_count=3, is_spanish=False)
        es = format_batch_transactions_header(incomes_count=1, expenses_count=2, total_count=3, is_spanish=True)
        assert en == "📋 <b>3 Transactions Logged:</b>\n\n"
        assert es == "📋 <b>3 Transacciones Registradas:</b>\n\n"

    def test_format_batch_total_pending(self):
        assert format_batch_total_pending("$150.00", is_spanish=False) == "\n📌 <b>Total pending to pay:</b> $150.00"
        assert format_batch_total_pending("$150.00", is_spanish=True) == "\n📌 <b>Total pendiente por pagar:</b> $150.00"

    def test_format_payload_too_long_message(self):
        en = format_payload_too_long_message(is_spanish=False)
        es = format_payload_too_long_message(is_spanish=True)
        assert "List is too long" in en
        assert "Lista demasiado extensa" in es


class TestSingleTransactionConfirmations:
    def test_format_single_expense_confirmation_and_escaping(self):
        en = format_single_expense_confirmation(
            amount=42.5,
            currency="USD",
            concept="<script>alert(1)</script> Coffee",
            category="Food & Drink",
            date_str=" (2026-09-07)",
            is_spanish=False
        )
        assert "&lt;script&gt;" in en
        assert "Saved 42.5 USD for" in en
        assert "'Food &amp; Drink'" in en

        es = format_single_expense_confirmation(
            amount=42.5,
            currency="USD",
            concept="Café",
            category="Comida",
            date_str="",
            is_spanish=True
        )
        assert "Guardado 42.5 USD para 'Café' en la categoría 'Comida'." in es

    def test_format_single_income_confirmation_bilingual(self):
        en = format_single_income_confirmation(
            formatted_amt="$3,000.00",
            concept_detail="from Salary",
            date_str="",
            formatted_in="$3,000.00",
            formatted_out="$1,200.00",
            formatted_net="$1,800.00",
            pct_str=" (60.0%)",
            month_name="September",
            is_spanish=False
        )
        assert "Income Logged:" in en
        assert "September Snapshot:" in en
        assert "Net Savings: $1,800.00 (60.0%)" in en

        es = format_single_income_confirmation(
            formatted_amt="$3,000.00",
            concept_detail="por Sueldo",
            date_str="",
            formatted_in="$3,000.00",
            formatted_out="$1,200.00",
            formatted_net="$1,800.00",
            pct_str=" (60.0%)",
            month_name="September",
            is_spanish=True,
            month_num=9
        )
        assert "Ingreso Registrado:" in es
        assert "Resumen de Septiembre:" in es
        assert "Ahorro Neto: $1,800.00 (60.0%)" in es

    def test_format_exchange_confirmation_bilingual(self):
        en = format_exchange_confirmation(
            fmt_sold="100.00 USD",
            fmt_recv="120,000.00 ARS",
            rate_line="\n• 📈 Rate: 1 USD = 1,200.00 ARS",
            is_spanish=False
        )
        assert "Currency Exchange Logged:" in en
        assert "Sold: -100.00 USD" in en
        assert "Received: +120,000.00 ARS" in en
        assert "Categorized under <b>Exchange</b>" in en

        es = format_exchange_confirmation(
            fmt_sold="100.00 USD",
            fmt_recv="120,000.00 ARS",
            rate_line="\n• 📈 Tasa: 1 USD = 1,200.00 ARS",
            is_spanish=True
        )
        assert "Cambio de Moneda Registrado:" in es
        assert "Entregaste: -100.00 USD" in es
        assert "Recibiste: +120,000.00 ARS" in es
        assert "Categorizado bajo <b>Exchange</b>" in es


class TestBillSettlementAndQueryClaims:
    def test_format_unmatched_bill_claim_and_escaping(self):
        en = format_unmatched_bill_claim("<b>gym</b>", is_spanish=False)
        assert "&lt;b&gt;gym&lt;/b&gt;" in en
        assert "I couldn't find an upcoming bill matching" in en

        es = format_unmatched_bill_claim("gimnasio", is_spanish=True)
        assert "No encontré ninguna factura pendiente para 'gimnasio'" in es

    def test_format_bill_settled_notice_and_escaping(self):
        en = format_bill_settled_notice("<Wifi>", "$0.00", is_spanish=False)
        assert "&lt;Wifi&gt;" in en
        assert "Marked as paid!" in en
        assert "Remaining pending this month: <b>$0.00</b>" in en

        es = format_bill_settled_notice("Wifi", "$0.00", is_spanish=True)
        assert "¡Marcado como pagado!" in es
        assert "Restante pendiente este mes: <b>$0.00</b>" in es


class TestErrorFallbacks:
    def test_format_unhandled_query_message(self):
        assert format_unhandled_query_message(is_spanish=False) == "I couldn't process your request."
        assert format_unhandled_query_message(is_spanish=True) == "No pude procesar tu solicitud."

    def test_format_audio_error_message(self):
        assert "I couldn't understand the audio" in format_audio_error_message(is_spanish=False)
        assert "No pude entender el audio" in format_audio_error_message(is_spanish=True)

    def test_format_persistence_error_message(self):
        assert "Failed to save transaction." in format_persistence_error_message(is_spanish=False, is_batch=False)
        assert "Failed to save transactions." in format_persistence_error_message(is_spanish=False, is_batch=True)
        assert "No se pudo guardar la transacción." in format_persistence_error_message(is_spanish=True, is_batch=False)
        assert "No se pudieron guardar las transacciones." in format_persistence_error_message(is_spanish=True, is_batch=True)

    def test_format_extraction_error_message(self):
        assert "I couldn't extract the details" in format_extraction_error_message(is_spanish=False)
        assert "No pude extraer los detalles" in format_extraction_error_message(is_spanish=True)

    def test_format_empty_message_error(self):
        assert format_empty_message_error(is_spanish=False) == "No message or audio was provided."
        assert format_empty_message_error(is_spanish=True) == "No se proporcionó ningún mensaje o audio."

    def test_format_generic_error_message(self):
        assert "An unexpected error occurred" in format_generic_error_message(is_spanish=False)
        assert "Ocurrió un error inesperado" in format_generic_error_message(is_spanish=True)
