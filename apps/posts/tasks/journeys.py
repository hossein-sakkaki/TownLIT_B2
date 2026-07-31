# apps/posts/tasks/journeys.py

from __future__ import annotations

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from apps.posts.constants.journeys import JourneyRetentionPolicy
from apps.posts.models.journey import JourneyEntry


JOURNEY_LIFECYCLE_BATCH_SIZE = 500


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=5,
)
def process_expired_journey_entries(self):
    """
    Archive or delete expired Journey entries.

    Lifecycle signals handle:
    - AudioUsageGrant revocation before delete
    - reaction cascade
    - viewer-record cascade
    - immutable media cleanup after commit
    """

    now = timezone.now()

    entry_ids = list(
        JourneyEntry.objects.filter(
            expires_at__lte=now,
            archived_at__isnull=True,
        )
        .order_by(
            "expires_at",
            "id",
        )
        .values_list(
            "id",
            flat=True,
        )[:JOURNEY_LIFECYCLE_BATCH_SIZE]
    )

    archived = 0
    deleted = 0
    skipped = 0

    for entry_id in entry_ids:
        with transaction.atomic():
            entry = (
                JourneyEntry.objects.select_for_update()
                .filter(
                    pk=entry_id,
                    expires_at__lte=now,
                    archived_at__isnull=True,
                )
                .first()
            )

            if entry is None:
                skipped += 1
                continue

            if (
                entry.retention_policy
                == JourneyRetentionPolicy.DELETE_AFTER_EXPIRY
            ):
                # pre_delete revokes active grants.
                # post_delete schedules storage cleanup.
                entry.delete()

                deleted += 1
                continue

            entry.archived_at = now

            entry.save(
                update_fields=[
                    "archived_at",
                    "updated_at",
                ]
            )

            archived += 1

    return {
        "selected": len(entry_ids),
        "archived": archived,
        "deleted": deleted,
        "skipped": skipped,
    }