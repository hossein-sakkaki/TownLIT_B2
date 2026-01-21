# apps/translations/tasks.py

from datetime import timedelta
from django.utils import timezone
from celery import shared_task

from apps.translations.models import TranslationCache


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=30, retry_kwargs={"max_retries": 3})
def purge_stale_translations(self, days: int = 90) -> dict:
    """
    Delete translation cache entries not accessed within TTL.
    """
    cutoff = timezone.now() - timedelta(days=days)

    qs = TranslationCache.objects.filter(last_accessed_at__lt=cutoff)
    deleted_count, _ = qs.delete()

    return {
        "deleted": deleted_count,
        "cutoff": cutoff.isoformat(),
        "ttl_days": days,
    }
