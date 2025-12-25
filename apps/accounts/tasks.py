# apps/accounts/tasks.py

from celery import shared_task
from django.utils import timezone
from django.conf import settings
from datetime import timedelta
import logging
from django.contrib.auth import get_user_model
from utils.email.email_tools import send_custom_email

CustomUser = get_user_model()
logger = logging.getLogger(__name__)


# Delete expired tokens -----------------------------------------------------------
@shared_task
def delete_expired_tokens():
    CustomUser.objects.filter(reset_token_expiration__lt=timezone.now()).update(reset_token=None, reset_token_expiration=None)


# Delete abandoned users ----------------------------------------------------------
@shared_task
def delete_abandoned_users():
    threshold = timezone.now() - timedelta(hours=2)

    users_to_delete = CustomUser.objects.filter(
        is_active=False,
        user_active_code_expiry__lt=timezone.now(),
        registration_started_at__lt=threshold,
        last_login__isnull=True,
    ).exclude(member_profile__isnull=False).exclude(guestuser__isnull=False)

    count = users_to_delete.count()
    users_to_delete.delete()

    return f"{count} abandoned users deleted."


# Send Welcome Email --------------------------------------------------------------
@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 30})
def send_believer_welcome_email(self, user_id):
    """
    Send welcome email to newly onboarded BELIEVER users.
    Must never raise to caller.
    """

    try:
        user = CustomUser.objects.get(id=user_id)
    except CustomUser.DoesNotExist:
        logger.warning(f"[WelcomeEmail] User not found: {user_id}")
        return "user_not_found"

    # Safety check: only believers
    if not user.is_member:
        logger.info(f"[WelcomeEmail] Skipped (not believer): {user.email}")
        return "skipped_not_believer"

    context = {
        "first_name": user.name or "",
        "user": user,
        "site_domain": settings.SITE_URL,
        "logo_base_url": settings.EMAIL_LOGO_URL,
        "current_year": timezone.now().year,
    }

    success = send_custom_email(
        to=user.email,
        subject="You’re In — Begin Your Journey in TownLIT",
        template_path="emails/invite/welcome_believer.html",
        context=context,
        text_template_path=None,
    )

    if not success:
        logger.error(f"[WelcomeEmail] Failed to send to {user.email}")
        return "send_failed"

    logger.info(f"[WelcomeEmail] Sent to {user.email}")
    return "sent"