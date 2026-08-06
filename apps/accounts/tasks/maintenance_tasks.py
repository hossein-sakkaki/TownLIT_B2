#
#  apps/accounts/tasks/maintenance_tasks.py
#  TownLIT
#
#  Created by Hossein Sakkaki on 2023-01-01.
#  Last Update by Hossein Sakkaki on 2026-08-04.
#

import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.accounts.account_deletion.service import (
    permanently_delete_account,
)


CustomUser = get_user_model()
logger = logging.getLogger(__name__)


@shared_task
def delete_expired_tokens():
    """
    Remove expired password reset tokens.
    """
    count = CustomUser.objects.filter(
        reset_token_expiration__lt=timezone.now(),
    ).update(
        reset_token=None,
        reset_token_expiration=None,
    )

    return count


@shared_task
def delete_abandoned_users():
    """
    Delete registrations that never completed onboarding.
    """
    threshold = (
        timezone.now()
        - timedelta(hours=2)
    )

    users_to_delete = (
        CustomUser.objects
        .filter(
            is_active=False,
            is_deleted=False,
            user_active_code_expiry__lt=timezone.now(),
            registration_started_at__lt=threshold,
            last_login__isnull=True,
        )
        .exclude(
            member_profile__isnull=False,
        )
        .exclude(
            guest_profile__isnull=False,
        )
    )

    count = users_to_delete.count()
    users_to_delete.delete()

    logger.info(
        "[Maintenance] %s abandoned users deleted.",
        count,
    )

    return count


@shared_task
def purge_scheduled_account_deletions():
    """
    Permanently anonymize accounts whose grace period ended.
    """
    try:
        batch_size = int(
            getattr(
                settings,
                "ACCOUNT_DELETION_BATCH_SIZE",
                50,
            )
        )
    except (TypeError, ValueError):
        batch_size = 50

    user_ids = list(
        CustomUser.objects.filter(
            is_deleted=True,
            deletion_completed_at__isnull=True,
            deletion_scheduled_for__isnull=False,
            deletion_scheduled_for__lte=timezone.now(),
        )
        .order_by(
            "deletion_scheduled_for",
            "id",
        )
        .values_list(
            "id",
            flat=True,
        )[:batch_size]
    )

    completed = 0
    failed = 0

    for user_id in user_ids:
        try:
            if permanently_delete_account(
                user_id=user_id,
            ):
                completed += 1

        except Exception:
            failed += 1

            logger.exception(
                "[AccountDeletion] Purge failed "
                "user_id=%s",
                user_id,
            )

    logger.info(
        "[AccountDeletion] Batch finished "
        "completed=%s failed=%s",
        completed,
        failed,
    )

    return {
        "completed": completed,
        "failed": failed,
    }