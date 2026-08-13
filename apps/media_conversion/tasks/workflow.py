from __future__ import annotations

import logging

from celery import shared_task
from django.db import close_old_connections, transaction
from django.utils import timezone

from apps.media_conversion.models import (
    MediaConversionJob,
    MediaJobStatus,
)
from apps.media_conversion.services.workflows import (
    load_workflow_handler,
)

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    queue="video",
    autoretry_for=(),
)
def process_media_workflow_task(
    self,
    *,
    job_id: int,
):
    close_old_connections()

    job = (
        MediaConversionJob.objects
        .select_related("content_type")
        .filter(pk=job_id)
        .first()
    )

    if job is None:
        return

    if job.status in {
        MediaJobStatus.DONE,
        MediaJobStatus.CANCELED,
        MediaJobStatus.FAILED,
    }:
        return

    current_task_id = str(self.request.id or "")

    if (
        job.task_id
        and current_task_id
        and job.task_id != current_task_id
    ):
        return

    try:
        with transaction.atomic():
            locked = (
                MediaConversionJob.objects
                .select_for_update()
                .get(pk=job.pk)
            )

            if locked.status == MediaJobStatus.QUEUED:
                if (
                    locked.max_attempts is not None
                    and locked.attempt >= locked.max_attempts
                ):
                    locked.mark_failed(
                        "Maximum workflow attempts reached."
                    )
                    return

                now = timezone.now()

                locked.attempt = (locked.attempt or 0) + 1
                locked.status = MediaJobStatus.PROCESSING
                locked.progress = max(1, locked.progress or 0)
                locked.message = "Processing"
                locked.error = None
                locked.started_at = now
                locked.heartbeat_at = now

                locked.save(
                    update_fields=[
                        "attempt",
                        "status",
                        "progress",
                        "message",
                        "error",
                        "started_at",
                        "heartbeat_at",
                        "updated_at",
                    ]
                )

        job.refresh_from_db()

        handler = load_workflow_handler(job)
        handler.run_workflow(job)

    except Exception as exc:
        logger.exception(
            "media_workflow.failed",
            extra={"job_id": job_id},
        )

        refreshed = (
            MediaConversionJob.objects
            .filter(pk=job_id)
            .first()
        )

        if (
            refreshed is not None
            and refreshed.status
            not in {
                MediaJobStatus.CANCELED,
                MediaJobStatus.DONE,
            }
        ):
            refreshed.mark_failed(str(exc))