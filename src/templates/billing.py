"""
Subscription, tiers, quota limits, and Paddle billing templates for Clanomy.
"""
import html
from typing import Optional, Any
from datetime import datetime
from src.db.models import Family
from src.core.subscription_config import FREE_TIER_MONTHLY_LIMIT
from src.templates.common import is_spanish_text, is_family_spanish, format_date_localized

SELF_HOSTED_UPGRADE_MESSAGE = (
    "⏳ <b>Subscriptions Coming Soon</b>\n\n"
    "We are currently in private beta testing. Dedicated subscription tiers "
    "will be required in the future, but right now all features are <b>100% unlocked for free</b>."
)

DAILY_LIMIT_REACHED_MESSAGE = (
    "⚠️ <b>Daily Limit Reached</b>\n\n"
    "Your workspace has reached its fair-use limit of <b>{limit} messages</b> for today.\n\n"
    "All limits reset to zero daily at <b>10:00 UTC</b>."
)

def format_daily_limit_reached(limit: int, is_spanish: bool = False) -> str:
    """Localized fair-use daily message quota exhaustion notice."""
    if is_spanish:
        return (
            "⚠️ <b>Límite Diario Alcanzado</b>\n\n"
            f"Tu espacio ha alcanzado el límite de uso justo de <b>{limit} mensajes</b> para hoy.\n\n"
            "Todos los límites se reinician a cero diariamente a las <b>10:00 UTC</b>."
        )
    return DAILY_LIMIT_REACHED_MESSAGE.format(limit=limit)

LIFETIME_PRO_CONFIRMATION = (
    "⭐️ <b>Clanomy Lifetime Pro Active</b>\n\n"
    "You have unlocked permanent Lifetime Pro access to Clanomy. Enjoy unlimited voice and text logging forever!"
)

SOLO_PRO_CONFIRMATION = (
    "🎉 <b>Welcome to Clanomy Solo Pro!</b>\n\n"
    "Your subscription is now active. Enjoy unlimited AI voice and text logging, "
    "instant deterministic summaries, and private Notion mirroring."
)

DUO_PRO_CONFIRMATION = (
    "🎉 <b>Welcome to Clanomy Duo Pro!</b>\n\n"
    "Your subscription is now active. Enjoy unlimited AI voice and text logging for 2 partners, "
    "a shared couple ledger, per-member breakdowns, and real-time Notion database mirroring."
)

FAMILY_PRO_CONFIRMATION = (
    "🎉 <b>Welcome to Clanomy Family Pro!</b>\n\n"
    "Your subscription is now active. Enjoy unlimited AI voice and text logging for your entire household, "
    "shared family ledger, per-member breakdowns, and real-time Notion database mirroring."
)

SOLO_PRO_MEMBER_NOTICE = (
    "ℹ️ <b>Workspace Plan Update</b>\n\n"
    "Your workspace admin has updated the workspace to the <b>Solo Pro</b> plan. "
    "As a non-admin member, you can continue viewing past records, or upgrade to your own "
    "plan anytime using /upgrade."
)

REFUND_PROCESSED_MESSAGE = (
    "ℹ️ <b>Subscription Update:</b> Your payment was refunded. "
    "Your workspace has been moved to the Free plan. Type /upgrade to resubscribe anytime."
)

PLAN_EXPIRED_MESSAGE = (
    "🔒 <b>Clanomy Pro Required</b>\n\n"
    "This feature requires an active <b>Clanomy Pro</b> subscription. "
    "To unlock unlimited AI logging, family sharing, and Notion sync, "
    "please upgrade to <b>Clanomy Pro</b> using /upgrade."
)

UPGRADE_MENU_INTRO = (
    "⭐️ <b>Upgrade to Clanomy Pro</b>\n\n"
    "Choose the plan that fits your needs with secure billing (Apple Pay, Google Pay, or Credit/Debit Card):\n\n"
    "1️⃣ <b>Solo Pro ($4.99 / month)</b>\n"
    "• Unlimited text &amp; voice logging &amp; Notion sync for 1 User\n\n"
    "2️⃣ <b>Duo Pro ($7.99 / month) — Best for Couples ⭐</b>\n"
    "• Everything in Solo Pro for 2 Partners with shared ledger &amp; Notion sync\n\n"
    "3️⃣ <b>Family Pro ($11.99 / month)</b>\n"
    "• Everything in Duo Pro for up to 5 Family Members with shared ledger\n\n"
    "🎁 <i>Annual Savings: 2 Months Free on annual plans ($49.99, $79.99, $119.99/yr)!</i>\n\n"
    "📋 <b>Billing Terms &amp; Transparency:</b>\n"
    "• <b>Auto-Renewal:</b> Subscriptions auto-renew monthly or annually until cancelled.\n"
    "• <b>Cancel Anytime:</b> 1-tap cancellation via /billing to prevent future charges.\n"
    "• <b>Refund Policy:</b> All workspaces include a 60-day free trial. Paid subscriptions are non-refundable once billed.\n"
    "• By subscribing, you agree to our /tos and /privacy.\n\n"
    "<i>Tap a button below to open secure checkout and activate immediately:</i>"
)

UPGRADE_MENU_ANNUAL_INTRO = (
    "🎁 <b>Clanomy Pro Annual Plans (2 Months Free!)</b>\n\n"
    "Get a full year of unlimited AI financial tracking and save 17%:\n\n"
    "1️⃣ <b>Solo Pro Annual ($49.99 / year)</b> — ~$4.16/mo (1 User)\n\n"
    "2️⃣ <b>Duo Pro Annual ($79.99 / year)</b> — ~$6.66/mo (2 Partners ⭐)\n\n"
    "3️⃣ <b>Family Pro Annual ($119.99 / year)</b> — ~$9.99/mo (Up to 5 Members)\n\n"
    "📋 <b>Billing Terms:</b>\n"
    "• Subscriptions auto-renew annually until cancelled. Cancel anytime via /billing.\n"
    "• All plans include a 60-day free evaluation; paid subscriptions are non-refundable. Terms: /tos.\n\n"
    "<i>Tap a button below to activate your annual subscription!</i>"
)

BILLING_PORTAL_MESSAGE = (
    "⚙️ <b>Manage Your Subscription</b>\n\n"
    "You can update your payment method, view past receipts, or cancel your subscription anytime "
    "through your secure customer billing portal.\n\n"
    "<i>Tap the button below to open your billing portal:</i>"
)

SUBSCRIPTION_CANCELLED_MESSAGE = (
    "ℹ️ <b>Subscription Cancelled</b>\n\n"
    "Your subscription auto-renewal has been cancelled. "
    "You will retain full Pro access until the end of your current billing period."
)

SUBSCRIPTION_PAYMENT_FAILED_MESSAGE = (
    "⚠️ <b>Subscription Payment Failed</b>\n\n"
    "We were unable to process your subscription renewal. "
    "Please update your payment method in the billing portal to avoid service interruption."
)

def format_free_tier_exceeded(monthly_tx_count: int) -> str:
    return (
        f"⚠️ <b>Monthly AI Quota Exceeded ({monthly_tx_count}/20)</b>\n\n"
        "You've reached your free monthly AI quota for voice &amp; text logs.\n\n"
        "⚡ <b>Commands are ALWAYS 100% Free &amp; Unlimited:</b>\n"
        "• Type /month or /me for your spending breakdown\n"
        "• Type /today for today's logs\n"
        "• Type /bills for upcoming bill reminders\n"
        "• Type /balance for net cash flow &amp; savings\n\n"
        "⭐️ <b>Upgrade to Clanomy Pro:</b>\n"
        "Unlock unlimited AI voice/text logging and family sharing with /upgrade."
    )

def format_non_admin_upgrade_intro(family_name: str, admin_name: str, is_spanish: bool = False) -> str:
    escaped_family = html.escape(family_name, quote=False)
    escaped_admin = html.escape(admin_name, quote=False)
    if is_spanish:
        return (
            f"⭐️ <b>Crea tu propia familia independiente</b>\n\n"
            f"Actualmente eres miembro de <b>{escaped_family}</b> (administrada por {escaped_admin}).\n\n"
            "⚠️ <b>Aviso importante:</b> Solo puedes tener acceso a <b>una sola familia a la vez</b>. Al mejorar tu plan, "
            f"saldrás de <b>{escaped_family}</b> y comenzarás tu propia familia como Administrador/a. "
            "<b>Todo tu historial personal de transacciones se migrará contigo</b> automáticamente:\n\n"
            "1️⃣ <b>Solo Pro ($4.99 / mes)</b> — Registro personal ilimitado y Notion privado (1 Usuario).\n\n"
            "2️⃣ <b>Duo Pro ($7.99 / mes) ⭐</b> — Espacio compartido para ti y tu pareja (2 Miembros).\n\n"
            "3️⃣ <b>Family Pro ($11.99 / mes)</b> — Tu propia familia de hasta 5 miembros con registro compartido.\n\n"
            "<i>Toca un botón abajo para elegir tu plan y comenzar tu propia familia:</i>"
        )
    return (
        f"⭐️ <b>Start Your Own Independent Family Workspace</b>\n\n"
        f"You are currently a member of <b>{escaped_family}</b> (managed by {escaped_admin}).\n\n"
        "⚠️ <b>Important Notice:</b> You can only have access to <b>one family workspace at a time</b>. Upgrading will "
        f"transition you out of <b>{escaped_family}</b> and start your own separate family workspace as Admin. "
        "<b>All your personal transaction history will migrate with you</b> seamlessly:\n\n"
        "1️⃣ <b>Solo Pro ($4.99 / mo)</b> — Unlimited personal AI logging &amp; private Notion sync (1 User).\n\n"
        "2️⃣ <b>Duo Pro ($7.99 / mo) ⭐</b> — Shared workspace for you and your partner (2 Members).\n\n"
        "3️⃣ <b>Family Pro ($11.99 / mo)</b> — Start your own family workspace for up to 5 members.\n\n"
        "<i>Tap a button below to choose your plan and launch your new workspace:</i>"
    )

def format_subscription_activated_message(
    tier_name: str,
    interval: str = "month",
    period_end: Optional[datetime] = None,
    is_spanish: bool = False
) -> str:
    """Sent ONLY to the paying user/admin upon successful checkout or tier upgrade."""
    escaped_tier = html.escape(tier_name, quote=False)
    cadence_str = "anual" if "year" in interval.lower() or "annual" in interval.lower() else "mensual"
    cadence_en = "yearly" if "year" in interval.lower() or "annual" in interval.lower() else "monthly"

    end_str = ""
    if period_end:
        date_formatted = format_date_localized(period_end, is_spanish=is_spanish)
        if is_spanish:
            end_str = f"• <b>Próxima fecha de renovación:</b> {date_formatted}\n"
        else:
            end_str = f"• <b>Next renewal date:</b> {date_formatted}\n"

    if is_spanish:
        return (
            f"🎉 <b>¡Suscripción Confirmada! Bienvenido a {escaped_tier}</b>\n\n"
            f"Tu pago se ha procesado con éxito y tu espacio familiar ya cuenta con <b>{escaped_tier}</b> activo.\n\n"
            f"📋 <b>Detalles de tu suscripción:</b>\n"
            f"• <b>Plan:</b> {escaped_tier}\n"
            f"• <b>Facturación:</b> Cobro automático {cadence_str}\n"
            f"{end_str}"
            f"• <b>Cancelación:</b> Puedes cancelar en cualquier momento desde /billing.\n\n"
            f"¡Ya tienes acceso a todas las funcionalidades premium! 🚀"
        )
    return (
        f"🎉 <b>Subscription Confirmed! Welcome to {escaped_tier}</b>\n\n"
        f"Your payment was successful and your family workspace is now active on <b>{escaped_tier}</b>.\n\n"
        f"📋 <b>Subscription Details:</b>\n"
        f"• <b>Plan:</b> {escaped_tier}\n"
        f"• <b>Billing:</b> Auto-renews {cadence_en}\n"
        f"{end_str}"
        f"• <b>Cancel Anytime:</b> You can cancel anytime directly via /billing.\n\n"
        f"You are all set with full premium access! 🚀"
    )

def format_subscription_canceled_message(
    tier_name: str,
    effective_end: Optional[datetime] = None,
    is_spanish: bool = False
) -> str:
    """Broadcast to ALL family members when a subscription cancellation is confirmed."""
    escaped_tier = html.escape(tier_name, quote=False)

    if effective_end:
        end_date_str = format_date_localized(effective_end, is_spanish=is_spanish)
        last_day_en = f"You will continue to have full access to <b>{escaped_tier}</b> until <b>{end_date_str}</b> (the end of your current billing period)."
        last_day_es = f"Seguirán teniendo acceso completo a <b>{escaped_tier}</b> hasta el <b>{end_date_str}</b> (fin del período de facturación actual)."
    else:
        last_day_en = f"Your access to <b>{escaped_tier}</b> has ended."
        last_day_es = f"El acceso a <b>{escaped_tier}</b> ha finalizado."

    if is_spanish:
        return (
            f"ℹ️ <b>Cancelación de Suscripción Confirmada</b>\n\n"
            f"Se ha procesado la cancelación de la suscripción a <b>{escaped_tier}</b> para su espacio familiar.\n\n"
            f"📅 <b>Período de acceso:</b>\n"
            f"{last_day_es}\n\n"
            f"📉 <b>Próximo plan (Gratuito):</b>\n"
            f"Luego de esa fecha, su espacio pasará al plan <b>Free</b> con un límite de <b>{FREE_TIER_MONTHLY_LIMIT} transacciones por mes</b> (hasta 5 miembros). "
            f"Todo su historial de gastos e información permanece 100% seguro y guardado.\n\n"
            f"💡 <i>Pueden volver a suscribirse a Premium en cualquier momento enviando /upgrade.</i>"
        )
    return (
        f"ℹ️ <b>Subscription Cancellation Confirmed</b>\n\n"
        f"The subscription for <b>{escaped_tier}</b> has been cancelled for your family workspace.\n\n"
        f"📅 <b>Access Period:</b>\n"
        f"{last_day_en}\n\n"
        f"📉 <b>Upcoming Plan (Free):</b>\n"
        f"After that date, your workspace will move to the <b>Free</b> plan with a limit of <b>{FREE_TIER_MONTHLY_LIMIT} transactions per month</b> (up to 5 members). "
        f"All your transaction history and data remain completely safe and intact.\n\n"
        f"💡 <i>You can resubscribe to Premium anytime by typing /upgrade.</i>"
    )

def format_family_split_notice(new_admin_name: str) -> str:
    escaped_admin = html.escape(new_admin_name, quote=False)
    return (
        "ℹ️ <b>Family Workspace Update</b>\n\n"
        "The workspace admin has switched to a personal Solo Pro plan. You and the remaining family members have been placed into a new shared family workspace on the Free tier.\n\n"
        f"👑 <b>{escaped_admin}</b> is your new workspace admin.\n\n"
        "Type /family to view your group, or /upgrade to unlock Family Pro anytime!"
    )

def format_member_graduated_notice(member_name: str, plan_name: str) -> str:
    escaped_member = html.escape(member_name, quote=False)
    escaped_plan = html.escape(plan_name, quote=False)
    return (
        "ℹ️ <b>Family Member Graduated</b>\n\n"
        f"<b>{escaped_member}</b> has upgraded to their own <b>{escaped_plan}</b> plan and transitioned to their own sovereign workspace. Their personal transactions have moved with them."
    )

def format_monthly_free_limit_reached(is_admin: bool, limit: int = FREE_TIER_MONTHLY_LIMIT, is_spanish: bool = False) -> str:
    """Monthly free quota exhaustion message, customized by admin role."""
    if is_spanish:
        if is_admin:
            return (
                f"⛔ <b>Límite Mensual Gratuito Alcanzado ({limit}/{limit} registros)</b>\n\n"
                f"Tu familia ha alcanzado el límite de {limit} registros gratuitos con IA para este mes (Cuota Alcanzada). "
                "Escribe /upgrade para desbloquear registros ilimitados con IA, o continúa usando nuestros comandos gratuitos ilimitados (/month, /me, /balance, /bills)."
            )
        return (
            f"⛔ <b>Límite Mensual Gratuito Alcanzado ({limit}/{limit} registros)</b>\n\n"
            f"Tu familia ha alcanzado el límite de {limit} registros gratuitos con IA para este mes (Cuota Alcanzada). "
            "Por favor pídele al administrador de tu hogar que actualice el espacio mediante /upgrade, o continúa usando nuestros comandos gratuitos ilimitados (/month, /me, /balance, /bills)."
        )
    if is_admin:
        return (
            f"⛔ <b>Monthly Free Limit Reached ({limit}/{limit} logs)</b>\n\n"
            f"Your family has reached the limit of {limit} free transaction logs for this month (Quota Reached). "
            "Type /upgrade to unlock unlimited AI logs, or continue using our unlimited free commands (/month, /me, /balance, /bills)."
        )
    return (
        f"⛔ <b>Monthly Free Limit Reached ({limit}/{limit} logs)</b>\n\n"
        f"Your family has reached the limit of {limit} free transaction logs for this month (Quota Reached). "
        "Please ask your family admin to upgrade the workspace via /upgrade, or continue using our unlimited free commands (/month, /me, /balance, /bills)."
    )

def format_subscription_expired_notice(limit: int = FREE_TIER_MONTHLY_LIMIT, is_spanish: bool = False) -> str:
    """Alert message sent to admin when subscription payment fails or expires."""
    if is_spanish:
        return (
            "⚠️ <b>Suscripción Expirada o Fallida:</b> El pago de tu espacio familiar falló o expiró. "
            f"Tu espacio ha pasado al plan Gratuito ({limit} registros/mes). "
            "Todo tu historial, registros anteriores y sincronización con Notion permanecen 100% seguros."
        )
    return (
        "⚠️ <b>Subscription Expired/Failed:</b> Your workspace payment failed or expired. "
        f"Your workspace has transitioned to the Free tier ({limit} logs/month). "
        "All your historical data, past entries, and Notion sync remain 100% safe."
    )
