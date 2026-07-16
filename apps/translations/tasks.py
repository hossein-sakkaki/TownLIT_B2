# apps/translations/tasks.py

from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from apps.translations.models import TranslationCache


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=30,
    retry_kwargs={
        "max_retries": 3,
    },
)
def purge_stale_translations(
    self,
    days: int = 90,
) -> dict:
    """
    Delete translation cache entries that have not been accessed
    within the configured TTL.

    Immediate invalidation for edited or deleted source objects is handled
    by translation signals. This task is the final cleanup layer for valid
    but no-longer-used translations.
    """
    effective_days = max(
        int(days),
        1,
    )

    cutoff = timezone.now() - timedelta(
        days=effective_days
    )

    queryset = TranslationCache.objects.filter(
        last_accessed_at__lt=cutoff
    )

    deleted_count, _ = queryset.delete()

    return {
        "deleted": deleted_count,
        "cutoff": cutoff.isoformat(),
        "ttl_days": effective_days,
    }