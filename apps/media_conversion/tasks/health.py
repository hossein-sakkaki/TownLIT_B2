# apps/media_conversion/tasks/health.py

from celery import shared_task
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta
import logging

from apps.media_conversion.models import MediaConversionJob, MediaJobStatus

logger = logging.getLogger(__name__)


@shared_task(bind=True, ignore_result=True)
def auto_fail_stale_media_jobs(self):
    """
    Auto-fail media conversion jobs that stopped sending heartbeat.
    Runs via Celery Beat.
    """
    now = timezone.now()
    stale_after = timedelta(minutes=2)
    cutoff = now - stale_after

    qs = (
        MediaConversionJob.objects
        .filter(status=MediaJobStatus.PROCESSING)
        .filter(
            Q(heartbeat_at__lt=cutoff)
            |
            Q(heartbeat_at__isnull=True)
        )
        .distinct()
    )

    count = qs.count()
    if not count:
        return

    failed_count = 0

    for job in qs:
        try:
            job.status = MediaJobStatus.FAILED
            job.progress = min(job.progress or 0, 99)
            job.message = "Auto-failed: stale heartbeat"
            job.error = "auto_failed:heartbeat_stale"
            job.finished_at = now
            job.heartbeat_at = now

            update_fields = [
                "status",
                "progress",
                "message",
                "error",
                "finished_at",
                "heartbeat_at",
                "updated_at",
            ]

            if job.started_at and job.duration_ms is None:
                job.duration_ms = int(
                    (job.finished_at - job.started_at).total_seconds() * 1000
                )
                update_fields.append("duration_ms")

            job.save(update_fields=update_fields)
            failed_count += 1

        except Exception:
            logger.exception(
                "Failed to auto-fail MediaConversionJob id=%s",
                job.id,
            )

    logger.warning(
        "🧠 Auto-failed %s stale media jobs",
        failed_count,
    )