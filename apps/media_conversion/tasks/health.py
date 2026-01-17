from celery import shared_task
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
    STALE_AFTER = timedelta(minutes=2)

    qs = MediaConversionJob.objects.filter(
        status=MediaJobStatus.PROCESSING,
    ).filter(
        # stale heartbeat OR never-heartbeated jobs
        (
            MediaConversionJob._meta.get_field("heartbeat_at").attname + "__lt",
            now - STALE_AFTER
        )
    )

    # Safer explicit version (clearer, recommended):
    qs = MediaConversionJob.objects.filter(
        status=MediaJobStatus.PROCESSING,
    ).filter(
        heartbeat_at__lt=now - STALE_AFTER
    ) | MediaConversionJob.objects.filter(
        status=MediaJobStatus.PROCESSING,
        heartbeat_at__isnull=True,
    )

    qs = qs.distinct()

    count = qs.count()
    if not count:
        return

    for job in qs:
        try:
            job.status = MediaJobStatus.FAILED
            job.progress = min(job.progress or 0, 99)
            job.error = "auto_failed:heartbeat_stale"
            job.finished_at = now
            job.updated_at = now

            # optional but consistent with base.py
            if job.started_at and job.duration_ms is None:
                job.duration_ms = int(
                    (job.finished_at - job.started_at).total_seconds() * 1000
                )

            job.save(update_fields=[
                "status",
                "progress",
                "error",
                "finished_at",
                "updated_at",
                "duration_ms",
            ])
        except Exception:
            logger.exception(
                "Failed to auto-fail MediaConversionJob id=%s",
                job.id
            )

    logger.warning("🧠 Auto-failed %s stale media jobs", count)
