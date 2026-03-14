# apps/accounts/tasks/maintenance_tasks.py

from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging

from django.contrib.auth import get_user_model

CustomUser = get_user_model()
logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Delete expired password reset tokens
# ------------------------------------------------------------------
@shared_task
def delete_expired_tokens():
    """
    Remove expired reset tokens from users.
    """
    CustomUser.objects.filter(
        reset_token_expiration__lt=timezone.now()
    ).update(
        reset_token=None,
        reset_token_expiration=None
    )


# ------------------------------------------------------------------
# Delete abandoned registrations
# ------------------------------------------------------------------
@shared_task
def delete_abandoned_users():
    """
    Delete users who started registration but never completed it.
    """

    threshold = timezone.now() - timedelta(hours=2)

    users_to_delete = CustomUser.objects.filter(
        is_active=False,
        user_active_code_expiry__lt=timezone.now(),
        registration_started_at__lt=threshold,
        last_login__isnull=True,
    ).exclude(
        member_profile__isnull=False
    ).exclude(
        guestuser__isnull=False
    )

    count = users_to_delete.count()
    users_to_delete.delete()

    logger.info(f"[Maintenance] {count} abandoned users deleted.")

    return f"{count} abandoned users deleted."