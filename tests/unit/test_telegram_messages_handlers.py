"""
Comprehensive unit tests for extracted telegram message templates across
Category A (Bills, Commands, Transactions, Webhook Flows) and Category B (Currency, Family, Notion).
Validates:
1. English canonical baseline (default).
2. Spanish natural translations.
3. Zero-quota command hints where conversational alternatives exist.
4. HTML character escaping security.
"""

import pytest
from uuid import uuid4
from src.templates.telegram_messages import (
    format_exchange_rate_line,
    format_batch_bill_item,
    format_batch_tx_item,
    format_bill_settled_response,
    format_overdue_bills_reminder,
    format_bill_settlement_card,
    format_bill_not_found_card,
    format_bill_already_paid_card,
    format_help_message,
    format_timezone_overview,
    format_timezone_unrecognized,
    format_timezone_admin_required,
    format_timezone_updated,
    format_delete_my_data_confirm_prompt,
    format_delete_my_data_success,
    format_delete_my_data_failure,
    format_undo_no_transactions,
    format_undo_success,
    format_correction_no_transactions,
    format_correction_success,
    format_currency_menu_text,
    format_currency_success_text,
    format_family_created_text,
    format_family_invite_text,
    format_family_info_text,
    format_member_removed_notice,
    format_notion_pro_required,
    format_notion_connect_instructions,
    format_notion_invalid_token,
    format_notion_connected_success,
    format_notion_no_databases,
    format_notion_status_message,
    format_notion_disconnected,
    format_bill_edit_prompt,
    format_bill_edit_cancelled,
    format_bill_edit_invalid_amount,
    format_monthly_free_limit_reached,
    format_daily_limit_reached,
    format_welcome_message,
    format_location_calibrated,
    format_location_calibration_failed,
    format_subscription_expired_notice,
)


from datetime import datetime

class TestExchangeRateAndBatchLines:
    def test_format_exchange_rate_line(self):
        en = format_exchange_rate_line("USD", 1250.0, "ARS", "1,250.00 ARS", is_spanish=False)
        assert "Rate: 1 USD = 1,250.00 ARS" in en

        es = format_exchange_rate_line("USD", 1250.0, "ARS", "1,250.00 ARS", is_spanish=True)
        assert "Cotización: 1 USD = 1,250.00 ARS" in es

        assert format_exchange_rate_line("USD", None, "ARS", "", is_spanish=False) == ""

    def test_format_batch_bill_item(self):
        dt = datetime(2026, 10, 1)
        en = format_batch_bill_item("Gym <Membership>", "50.00 USD", dt, is_spanish=False)
        assert "&lt;Membership&gt;" in en
        assert "Due:" in en
        assert "01/10" in en

        es = format_batch_bill_item("Gimnasio", "50.00 USD", dt, is_spanish=True)
        assert "Vence:" in es
        assert "01/10" in es

    def test_format_batch_tx_item(self):
        en_inc = format_batch_tx_item("💰", "Salary", "+2,000.00 USD", "Work")
        assert "Salary" in en_inc
        assert "+2,000.00 USD" in en_inc

        es_exp = format_batch_tx_item("💸", "Lunch", "-15.00 USD", "Food")
        assert "Lunch" in es_exp
        assert "-15.00 USD" in es_exp


class TestBillTemplates:
    def test_format_bill_settled_response(self):
        en = format_bill_settled_response("Electricity", "$75.00", "$150.00", is_spanish=False)
        assert "Bill marked as paid:" in en
        assert "Electricity" in en
        assert "Remaining pending bills:" in en

        es = format_bill_settled_response("Luz", "$75.00", "$150.00", is_spanish=True)
        assert "Factura registrada como pagada:" in es
        assert "Luz" in es
        assert "Pendiente por pagar este mes:" in es

    def test_format_overdue_bills_reminder(self):
        lines = ["• Internet ($50.00)"]
        en = format_overdue_bills_reminder(lines, is_spanish=False)
        assert "Upcoming / Due Bills Reminder:" in en
        assert "/bills" in en

        es = format_overdue_bills_reminder(lines, is_spanish=True)
        assert "Recordatorio de Vencimientos:" in es
        assert "/bills" in es

        assert format_overdue_bills_reminder([], is_spanish=False) == ""

    def test_format_bill_settlement_card(self):
        b_id = uuid4()
        en_text, en_kb = format_bill_settlement_card("Internet", "$50.00", "Tomorrow", "Utilities", b_id, is_spanish=False)
        assert "Settle Bill: Internet" in en_text
        assert "Recorded Amount:" in en_text
        assert len(en_kb["inline_keyboard"]) == 3

        es_text, es_kb = format_bill_settlement_card("Internet", "$50.00", "Manana", "Servicios", b_id, is_spanish=True)
        assert "Pagar Factura: Internet" in es_text
        assert "Monto Registrado:" in es_text
        assert len(es_kb["inline_keyboard"]) == 3

    def test_format_bill_not_found_card(self):
        en_msg, en_kb = format_bill_not_found_card(is_spanish=False)
        assert "Bill not found." in en_msg
        assert en_kb["inline_keyboard"][0][0]["text"] == "🔙 Back"

        es_msg, es_kb = format_bill_not_found_card(is_spanish=True)
        assert "Factura no encontrada." in es_msg
        assert es_kb["inline_keyboard"][0][0]["text"] == "🔙 Volver"

    def test_format_bill_already_paid_card(self):
        en_msg, en_kb = format_bill_already_paid_card(is_spanish=False)
        assert "This bill is already marked as paid." in en_msg
        assert en_kb["inline_keyboard"][0][0]["text"] == "🔙 Back"

        es_msg, es_kb = format_bill_already_paid_card(is_spanish=True)
        assert "Esta factura ya fue pagada." in es_msg
        assert es_kb["inline_keyboard"][0][0]["text"] == "🔙 Volver"


class TestCommandTemplates:
    def test_format_help_message(self):
        en = format_help_message(is_spanish=False)
        assert "Clanomy" in en
        assert "/month" in en
        assert "/me" in en
        assert "/bills" in en
        assert "100% free" in en

        es = format_help_message(is_spanish=True)
        assert "Clanomy" in es
        assert "/month" in es
        assert "/me" in es
        assert "/bills" in es
        assert "100% gratuitos" in es

    def test_format_timezone_templates(self):
        en_ov = format_timezone_overview("America/Argentina/Buenos_Aires", "America/Argentina/Buenos_Aires", None, is_spanish=False)
        assert "Timezone Settings" in en_ov

        es_ov = format_timezone_overview("Europe/Madrid", "Europe/Madrid", None, is_spanish=True)
        assert "Configuración de Zona Horaria" in es_ov or "Zona Horaria" in es_ov

        en_err = format_timezone_unrecognized("Atlantis", is_spanish=False)
        assert "Unrecognized timezone" in en_err

        es_err = format_timezone_unrecognized("Atlantis", is_spanish=True)
        assert "Zona horaria no reconocida" in es_err

        en_admin = format_timezone_admin_required(is_spanish=False)
        assert "Only household administrators" in en_admin

        es_admin = format_timezone_admin_required(is_spanish=True)
        assert "Solo los administradores" in es_admin

        en_upd = format_timezone_updated("Europe/Paris", is_household=False, is_spanish=False)
        assert "Personal Timezone Updated!" in en_upd

        es_upd = format_timezone_updated("Europe/Paris", is_household=True, is_spanish=True)
        assert "Zona Horaria del Hogar Actualizada!" in es_upd

    def test_format_delete_my_data_templates(self):
        en_prompt = format_delete_my_data_confirm_prompt(is_spanish=False)
        assert "Confirm Permanent Data Erasure" in en_prompt
        assert "/delete_my_data confirm" in en_prompt

        es_prompt = format_delete_my_data_confirm_prompt(is_spanish=True)
        assert "Confirmar Borrado Permanente de Datos" in es_prompt
        assert "/delete_my_data confirmar" in es_prompt

        en_succ = format_delete_my_data_success(is_spanish=False)
        assert "Data Purged Successfully" in en_succ

        es_succ = format_delete_my_data_success(is_spanish=True)
        assert "Datos Eliminados Exitosamente" in es_succ

        en_fail = format_delete_my_data_failure(is_spanish=False)
        assert "Failed to delete your data" in en_fail

        es_fail = format_delete_my_data_failure(is_spanish=True)
        assert "No se pudieron borrar tus datos" in es_fail


class TestUndoAndCorrectionTemplates:
    def test_format_undo_templates(self):
        en_empty = format_undo_no_transactions(is_spanish=False)
        assert "You don't have any recent transactions to undo." in en_empty

        es_empty = format_undo_no_transactions(is_spanish=True)
        assert "No tienes transacciones recientes para deshacer." in es_empty

        en_succ = format_undo_success(
            items_block="• 💸 -15.50 USD (Food - Lunch)",
            month_name="September",
            primary_curr="USD",
            formatted_in="$0.00",
            formatted_out="$100.00",
            formatted_net="-$100.00",
            pct_str="",
            is_spanish=False
        )
        assert "Removed latest transaction:" in en_succ
        assert "Updated September Balance" in en_succ

        es_succ = format_undo_success(
            items_block="• 💸 -15.50 USD (Comida - Almuerzo)",
            month_name="Septiembre",
            primary_curr="USD",
            formatted_in="$0.00",
            formatted_out="$100.00",
            formatted_net="-$100.00",
            pct_str="",
            is_spanish=True
        )
        assert "Última transacción revertida:" in es_succ
        assert "Balance Actualizado de Septiembre" in es_succ

    def test_format_correction_templates(self):
        en_empty = format_correction_no_transactions(is_spanish=False)
        assert "You don't have any recent transactions to update." in en_empty

        es_empty = format_correction_no_transactions(is_spanish=True)
        assert "No tienes transacciones recientes para modificar." in es_empty

        en_succ = format_correction_success(
            icon="💸",
            sign="-",
            formatted_amt="25.00 USD",
            category="Food",
            concept="Coffee & snack",
            type_note="",
            month_name="September",
            formatted_in="$0.00",
            formatted_out="$100.00",
            formatted_net="-$100.00",
            pct_str="",
            is_spanish=False
        )
        assert "Updated latest transaction:" in en_succ
        assert "Updated September Balance:" in en_succ

        es_succ = format_correction_success(
            icon="💸",
            sign="-",
            formatted_amt="25.00 USD",
            category="Comida",
            concept="Café",
            type_note="",
            month_name="Septiembre",
            formatted_in="$0.00",
            formatted_out="$100.00",
            formatted_net="-$100.00",
            pct_str="",
            is_spanish=True
        )
        assert "Última transacción modificada:" in es_succ
        assert "Balance Actualizado de Septiembre:" in es_succ


class TestCurrencyAndFamilyTemplates:
    def test_format_currency_templates(self):
        en_menu = format_currency_menu_text("USD", is_spanish=False)
        assert "Select Household Default Currency" in en_menu
        assert "Currently active: <b>USD</b>" in en_menu

        es_menu = format_currency_menu_text("EUR", is_spanish=True)
        assert "Seleccionar Moneda Predeterminada del Hogar" in es_menu
        assert "Actualmente activa: <b>EUR</b>" in es_menu

        en_succ = format_currency_success_text("GBP", is_spanish=False)
        assert "Default Currency Updated to GBP!" in en_succ

        es_succ = format_currency_success_text("ARS", is_spanish=True)
        assert "¡Moneda Predeterminada Actualizada a ARS!" in es_succ

    def test_format_family_templates(self):
        en_cr = format_family_created_text("Smiths", is_spanish=False)
        assert "Family group 'Smiths' has been created!" in en_cr

        es_cr = format_family_created_text("Los Perez", is_spanish=True)
        assert "¡El grupo familiar 'Los Perez' ha sido creado!" in es_cr

        en_inv = format_family_invite_text("https://t.me/ClanomyBot?start=inv_123", is_spanish=False)
        assert "Here is your family invite link" in en_inv

        es_inv = format_family_invite_text("https://t.me/ClanomyBot?start=inv_123", is_spanish=True)
        assert "Aquí tienes el link de invitación" in es_inv

        en_info = format_family_info_text(
            name="Household",
            plan_desc="Solo Pro",
            tx_info="5 (Unlimited)",
            members_formatted="• Alice",
            tx_count=42,
            invite_count=0,
            is_spanish=False
        )
        assert "Family Workspace: Household" in en_info
        assert "AI Logs:" in en_info
        assert "Total Transactions:" in en_info
        assert "42" in en_info

        es_info = format_family_info_text(
            name="Hogar",
            plan_desc="Solo Pro",
            tx_info="5 (Ilimitado)",
            members_formatted="• Alice",
            tx_count=42,
            invite_count=0,
            is_spanish=True
        )
        assert "Espacio Familiar: Hogar" in es_info
        assert "Registros de IA:" in es_info
        assert "Total de Transacciones:" in es_info
        assert "42" in es_info

        en_rem = format_member_removed_notice(is_spanish=False)
        assert "removed from the family workspace" in en_rem

        es_rem = format_member_removed_notice(is_spanish=True)
        assert "removido del espacio familiar" in es_rem


class TestNotionTemplates:
    def test_format_notion_templates(self):
        en_pro = format_notion_pro_required(is_spanish=False)
        assert "Notion Mirroring is a Pro Feature" in en_pro

        es_pro = format_notion_pro_required(is_spanish=True)
        assert "La Sincronización con Notion es una Función Pro" in es_pro

        en_inst = format_notion_connect_instructions(is_spanish=False)
        assert "Connect your Notion Workspace" in en_inst
        assert "/notion connect" in en_inst

        es_inst = format_notion_connect_instructions(is_spanish=True)
        assert "Conecta tu Espacio de Notion" in es_inst
        assert "/notion connect" in es_inst

        en_inv = format_notion_invalid_token(is_spanish=False)
        assert "Invalid Token!" in en_inv

        es_inv = format_notion_invalid_token(is_spanish=True)
        assert "¡Token Inválido!" in es_inv

        en_succ = format_notion_connected_success("Budget", "db_123", is_spanish=False)
        assert "Notion Workspace Connected!" in en_succ
        assert "Budget" in en_succ

        es_succ = format_notion_connected_success("Presupuesto", "db_123", is_spanish=True)
        assert "¡Espacio de Notion Conectado!" in es_succ
        assert "Presupuesto" in es_succ

        en_nodb = format_notion_no_databases(is_spanish=False)
        assert "No databases found!" in en_nodb

        es_nodb = format_notion_no_databases(is_spanish=True)
        assert "¡No se encontraron bases de datos!" in es_nodb

        en_stat = format_notion_status_message(True, "Budget", "db_123", "2026-09-07", is_spanish=False)
        assert "Notion Connection Status:" in en_stat
        assert "Connected ✅" in en_stat

        es_stat = format_notion_status_message(False, is_spanish=True)
        assert "Estado de Conexión con Notion:" in es_stat
        assert "No Conectado ❌" in es_stat

        en_disc = format_notion_disconnected(is_spanish=False)
        assert "Notion Disconnected" in en_disc

        es_disc = format_notion_disconnected(is_spanish=True)
        assert "Notion Desconectado" in es_disc


class TestWebhookFlowTemplates:
    def test_format_bill_edit_templates(self):
        b_id = uuid4()
        en_prompt, en_toast = format_bill_edit_prompt(b_id, "Gym", is_spanish=False)
        assert "Settle 'Gym'" in en_prompt
        assert "Reply with the new amount" in en_toast

        es_prompt, es_toast = format_bill_edit_prompt(b_id, "Gimnasio", is_spanish=True)
        assert "Pagar 'Gimnasio'" in es_prompt
        assert "Responde con el nuevo monto" in es_toast

        en_cancel = format_bill_edit_cancelled(is_spanish=False)
        assert "Bill payment cancelled" in en_cancel

        es_cancel = format_bill_edit_cancelled(is_spanish=True)
        assert "Pago de factura cancelado" in es_cancel

        en_inv = format_bill_edit_invalid_amount(is_spanish=False)
        assert "Could not recognize a valid amount" in en_inv

        es_inv = format_bill_edit_invalid_amount(is_spanish=True)
        assert "No pude reconocer un monto válido" in es_inv

    def test_format_monthly_free_limit_reached(self):
        en_admin = format_monthly_free_limit_reached(is_admin=True, limit=20, is_spanish=False)
        assert "Monthly Free Limit Reached (20/20 logs)" in en_admin
        assert "/upgrade" in en_admin
        assert "/month, /me, /balance, /bills" in en_admin

        es_admin = format_monthly_free_limit_reached(is_admin=True, limit=20, is_spanish=True)
        assert "Límite Mensual Gratuito Alcanzado (20/20 registros)" in es_admin
        assert "/upgrade" in es_admin

        en_member = format_monthly_free_limit_reached(is_admin=False, limit=20, is_spanish=False)
        assert "ask your family admin" in en_member

        es_member = format_monthly_free_limit_reached(is_admin=False, limit=20, is_spanish=True)
        assert "pídele al administrador" in es_member

    def test_format_location_templates(self):
        en_cal = format_location_calibrated("America/New_York", is_spanish=False)
        assert "Location Detected & Calibrated!" in en_cal
        assert "America/New_York" in en_cal

        es_cal = format_location_calibrated("America/Argentina/Buenos_Aires", is_spanish=True)
        assert "¡Ubicación Detectada y Calibrada!" in es_cal
        assert "America/Argentina/Buenos_Aires" in es_cal

        en_fail = format_location_calibration_failed(is_spanish=False)
        assert "Could not determine the timezone" in en_fail
        assert "/timezone" in en_fail

        es_fail = format_location_calibration_failed(is_spanish=True)
        assert "No se pudo determinar la zona horaria" in es_fail
        assert "/timezone" in es_fail

    def test_format_subscription_expired_notice(self):
        en_exp = format_subscription_expired_notice(limit=20, is_spanish=False)
        assert "Subscription Expired/Failed:" in en_exp
        assert "Free tier (20 logs/month)" in en_exp

        es_exp = format_subscription_expired_notice(limit=20, is_spanish=True)
        assert "Suscripción Expirada o Fallida:" in es_exp
        assert "plan Gratuito (20 registros/mes)" in es_exp

    def test_format_daily_limit_reached(self):
        en_msg = format_daily_limit_reached(limit=60, is_spanish=False)
        assert "Daily Limit Reached" in en_msg
        assert "60 messages" in en_msg
        assert "10:00 UTC" in en_msg

        es_msg = format_daily_limit_reached(limit=60, is_spanish=True)
        assert "Límite Diario Alcanzado" in es_msg
        assert "60 mensajes" in es_msg
        assert "10:00 UTC" in es_msg

    def test_format_welcome_message_daily_limits(self):
        from src.db.models import User, Family
        user = User(telegram_id=123, full_name="Tony Tester")

        fam_solo = Family(plan_type="solo_pro")
        en_solo = format_welcome_message(user, fam_solo, {"first_name": "Tony"}, is_spanish=False)
        assert "Solo Pro (Active — 60 daily AI logs" in en_solo

        es_solo = format_welcome_message(user, fam_solo, {"first_name": "Tony"}, is_spanish=True)
        assert "Solo Pro (Activo — 60 registros diarios con IA" in es_solo

        fam_duo = Family(plan_type="duo_pro")
        en_duo = format_welcome_message(user, fam_duo, {"first_name": "Tony"}, is_spanish=False)
        assert "Duo Pro (Active — 120 daily AI logs" in en_duo

        es_duo = format_welcome_message(user, fam_duo, {"first_name": "Tony"}, is_spanish=True)
        assert "Duo Pro (Activo — 120 registros diarios con IA" in es_duo

        fam_fam = Family(plan_type="family_pro")
        en_fam = format_welcome_message(user, fam_fam, {"first_name": "Tony"}, is_spanish=False)
        assert "Family Pro (Active — 300 daily AI logs" in en_fam

        es_fam = format_welcome_message(user, fam_fam, {"first_name": "Tony"}, is_spanish=True)
        assert "Family Pro (Activo — 300 registros diarios con IA" in es_fam
