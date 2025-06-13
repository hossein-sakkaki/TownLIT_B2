from django.utils import timezone
from django.conf import settings
from utils.email.email_tools import send_custom_email



# Confirmation Payment Email Send ---------------------------------------
def send_payment_confirmation_email(payment_instance):
    if not payment_instance.email:
        return False

    user = payment_instance.user
    first_name = user.name if user and hasattr(user, "name") else "Friend"

    subject = "💳 Your Payment to TownLIT Was Successful"

    context = {
        "first_name": first_name,
        "email": payment_instance.email,
        "reference_number": payment_instance.reference_number,
        "amount": payment_instance.amount,
        "type": payment_instance.get_type_display() if hasattr(payment_instance, "get_type_display") else "",  # optional
        "payment_type": payment_instance.__class__.__name__.replace("Payment", "").lower(),  # donation / shop / ads / subscription
        "date": timezone.now(),
        "site_domain": settings.SITE_URL,
        "logo_base_url": settings.EMAIL_LOGO_URL,
        "current_year": timezone.now().year,
    }

    return send_custom_email(
        to=payment_instance.email,
        subject=subject,
        template_path="emails/payment/payment_confirmation.html",
        context=context,
    )



# Rejection Payment Email Send ---------------------------------------
def send_payment_rejection_email(payment_instance):
    if not payment_instance.email:
        return False

    user = payment_instance.user
    first_name = user.name if user and hasattr(user, "name") else "Friend"

    subject = "⚠️ Your Payment to TownLIT Was Not Completed"

    context = {
        "first_name": first_name,
        "email": payment_instance.email,
        "reference_number": payment_instance.reference_number,
        "amount": payment_instance.amount,
        "type": payment_instance.get_type_display() if hasattr(payment_instance, "get_type_display") else "",
        "payment_type": payment_instance.__class__.__name__.replace("Payment", "").lower(),
        "date": timezone.now(),
        "site_domain": settings.SITE_URL,
        "logo_base_url": settings.EMAIL_LOGO_URL,
        "current_year": timezone.now().year,
    }

    return send_custom_email(
        to=payment_instance.email,
        subject=subject,
        template_path="emails/payment/payment_rejected.html",
        context=context,
    )
