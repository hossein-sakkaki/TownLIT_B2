# apps/payment/utils.py
from django.utils import timezone
from django.conf import settings
from utils.email.email_tools import send_custom_email
import logging

logger = logging.getLogger(__name__)

def _resolve_recipient_email(payment_instance):
    """Choose recipient email: Payment.email → User.email → None."""
    if getattr(payment_instance, "email", None):
        return payment_instance.email
    user = getattr(payment_instance, "user", None)
    if user and getattr(user, "email", None):
        return user.email
    return None

def _resolve_first_name(payment_instance, recipient_email):
    user = getattr(payment_instance, "user", None)
    if user and getattr(user, "name", None):
        return user.name
    if recipient_email and "@" in recipient_email:
        return recipient_email.split("@", 1)[0]  # local-part
    return "Friend"

def _safe_setting(name, default=""):
    return getattr(settings, name, default) or default

# Confirmation Payment Email Send ---------------------------------------
def send_payment_confirmation_email(payment_instance):
    to_email = _resolve_recipient_email(payment_instance)
    if not to_email:
        logger.info("Payment %s: no recipient email (skipping confirmation email).",
                    getattr(payment_instance, "reference_number", ""))
        return False  # keep False so caller can log a soft warning

    first_name = _resolve_first_name(payment_instance, to_email)
    subject = "💳 Your Payment to TownLIT Was Successful"

    context = {
        "first_name": first_name,
        "email": to_email,
        "reference_number": getattr(payment_instance, "reference_number", ""),
        "amount": getattr(payment_instance, "amount", ""),
        "type": getattr(payment_instance, "get_type_display", lambda: "")(),
        "payment_type": payment_instance.__class__.__name__.replace("Payment", "").lower(),
        "date": timezone.now(),
        "site_domain": _safe_setting("SITE_URL", "https://www.townlit.com"),
        "logo_base_url": _safe_setting("EMAIL_LOGO_URL", _safe_setting("SITE_URL", "")),
        "current_year": timezone.now().year,
    }

    return send_custom_email(
        to=to_email,
        subject=subject,
        template_path="emails/payment/payment_confirmation.html",
        context=context,
    )

# Rejection Payment Email Send ---------------------------------------
def send_payment_rejection_email(payment_instance):
    to_email = _resolve_recipient_email(payment_instance)
    if not to_email:
        logger.info("Payment %s: no recipient email (skipping rejection email).",
                    getattr(payment_instance, "reference_number", ""))
        return False

    first_name = _resolve_first_name(payment_instance, to_email)
    subject = "⚠️ Your Payment to TownLIT Was Not Completed"

    context = {
        "first_name": first_name,
        "email": to_email,
        "reference_number": getattr(payment_instance, "reference_number", ""),
        "amount": getattr(payment_instance, "amount", ""),
        "type": getattr(payment_instance, "get_type_display", lambda: "")(),
        "payment_type": payment_instance.__class__.__name__.replace("Payment", "").lower(),
        "date": timezone.now(),
        "site_domain": _safe_setting("SITE_URL", "https://www.townlit.com"),
        "logo_base_url": _safe_setting("EMAIL_LOGO_URL", _safe_setting("SITE_URL", "")),
        "current_year": timezone.now().year,
    }

    return send_custom_email(
        to=to_email,
        subject=subject,
        template_path="emails/payment/payment_rejected.html",
        context=context,
    )
