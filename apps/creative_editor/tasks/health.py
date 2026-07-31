# apps/creative_editor/tasks/health.py

from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

from apps.creative_editor.constants import CREATIVE_RENDER_QUEUE
from apps.creative_editor.models import (
    CreativeComposition,
    CreativeRenderJob,
)


logger = logging.getLogger(__name__)


def queued_timeout_minutes() -> int:
    """
    Read queued job timeout.
    """

    return max(
        2,
        int(
            getattr(
                settings,
                "CREATIVE_RENDER_QUEUED_TIMEOUT_MINUTES",
                10,
            )
        ),
    )


def processing_timeout_minutes() -> int:
    """
    Read processing timeout.
    """

    return max(
        2,
        int(
            getattr(
                settings,
                "CREATIVE_RENDER_PROCESSING_TIMEOUT_MINUTES",
                15,
            )
        ),
    )


def dispatch_render_job(job_id: int) -> None:
    """
    Dispatch one render job.
    """

    from apps.creative_editor.tasks.render import (
        render_creative_composition_task,
    )

    result = render_creative_composition_task.apply_async(
        kwargs={
            "render_job_id": job_id,
        },
        queue=CREATIVE_RENDER_QUEUE,
    )

    CreativeRenderJob.objects.filter(pk=job_id).update(
        task_id=str(result.id or ""),
        queue=CREATIVE_RENDER_QUEUE,
        heartbeat_at=timezone.now(),
        updated_at=timezone.now(),
    )


@shared_task
def recover_stale_creative_render_jobs():
    """
    Recover queued jobs and fail stuck jobs.
    """

    now = timezone.now()

    queued_cutoff = now - timedelta(
        minutes=queued_timeout_minutes()
    )

    processing_cutoff = now - timedelta(
        minutes=processing_timeout_minutes()
    )

    queued_ids = list(
        CreativeRenderJob.objects.filter(
            status=CreativeRenderJob.Status.QUEUED,
            heartbeat_at__lt=queued_cutoff,
            attempt__lt=models.F("max_attempts"),
        ).values_list(
            "id",
            flat=True,
        )[:100]
    )

    for job_id in queued_ids:
        dispatch_render_job(job_id)

    stale_processing_ids = list(
        CreativeRenderJob.objects.filter(
            status=CreativeRenderJob.Status.PROCESSING,
            heartbeat_at__lt=processing_cutoff,
        ).values_list(
            "id",
            flat=True,
        )[:100]
    )

    failed_count = 0

    for job_id in stale_processing_ids:
        with transaction.atomic():
            job = (
                CreativeRenderJob.objects.select_for_update()
                .select_related("composition")
                .filter(
                    pk=job_id,
                    status=CreativeRenderJob.Status.PROCESSING,
                )
                .first()
            )

            if job is None:
                continue

            job.status = CreativeRenderJob.Status.FAILED
            job.progress = 100
            job.stage = "failed"
            job.message = "Render worker heartbeat expired"
            job.error = (
                "Render job exceeded the processing timeout."
            )
            job.finished_at = now
            job.heartbeat_at = now

            job.save(
                update_fields=[
                    "status",
                    "progress",
                    "stage",
                    "message",
                    "error",
                    "finished_at",
                    "heartbeat_at",
                    "updated_at",
                ]
            )

            CreativeComposition.objects.filter(
                pk=job.composition_id,
                revision=job.requested_revision,
                status=CreativeComposition.Status.RENDERING,
            ).update(
                status=CreativeComposition.Status.FAILED,
                render_error=job.error,
                updated_at=now,
            )

            failed_count += 1

    result = {
        "requeued": len(queued_ids),
        "failed": failed_count,
    }

    logger.info(
        "creative_editor.render_health.completed",
        extra=result,
    )

    return result