# apps/media_conversion/services/workflows.py

from __future__ import annotations

import importlib

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.media_conversion.models import (
    MediaConversionJob,
    MediaJobKind,
    MediaJobStatus,
)


def load_workflow_handler(job: MediaConversionJob):
    if job.kind != MediaJobKind.WORKFLOW:
        raise ValidationError("Job is not a workflow.")

    path = str(job.workflow_handler or "").strip()

    if not path or not path.startswith("apps."):
        raise ValidationError("Invalid workflow handler.")

    module = importlib.import_module(path)

    if not callable(getattr(module, "run_workflow", None)):
        raise ValidationError(
            "Workflow handler does not define run_workflow()."
        )

    return module


def enqueue_workflow_job(
    job: MediaConversionJob,
    *,
    countdown: int = 0,
):
    job.refresh_from_db(
        fields=[
            "status",
            "kind",
            "queue",
        ]
    )

    if job.kind != MediaJobKind.WORKFLOW:
        raise ValidationError("Job is not a workflow.")

    if job.status not in {
        MediaJobStatus.QUEUED,
        MediaJobStatus.PROCESSING,
    }:
        return None

    from apps.media_conversion.tasks.workflow import (
        process_media_workflow_task,
    )

    result = process_media_workflow_task.apply_async(
        kwargs={"job_id": job.pk},
        queue=job.queue or "video",
        countdown=max(0, int(countdown)),
    )

    MediaConversionJob.objects.filter(
        pk=job.pk,
        status__in=[
            MediaJobStatus.QUEUED,
            MediaJobStatus.PROCESSING,
        ],
    ).update(
        task_id=str(result.id or ""),
        queue=job.queue or "video",
    )

    return result


def retry_workflow_job(
    job: MediaConversionJob,
) -> MediaConversionJob:
    with transaction.atomic():
        locked = (
            MediaConversionJob.objects
            .select_for_update()
            .get(pk=job.pk)
        )

        if locked.kind != MediaJobKind.WORKFLOW:
            raise ValidationError("Job is not a workflow.")

        if locked.status not in {
            MediaJobStatus.FAILED,
            MediaJobStatus.CANCELED,
        }:
            raise ValidationError(
                "Only failed or canceled workflow jobs can be retried."
            )

        if (
            locked.max_attempts is not None
            and locked.attempt >= locked.max_attempts
        ):
            raise ValidationError(
                "This job has reached the maximum retry attempts."
            )

        locked.status = MediaJobStatus.QUEUED
        locked.progress = 0
        locked.message = "Queued for retry"
        locked.error = None
        locked.task_id = None
        locked.started_at = None
        locked.finished_at = None
        locked.duration_ms = None
        locked.heartbeat_at = None
        locked.output_path = None
        locked.stage = None
        locked.stage_index = None
        locked.stage_count = None
        locked.stage_weight = None
        locked.stage_progress = None
        locked.stage_started_at = None
        locked.stage_plan = None
        locked.stage_total_weight = None
        locked.stage_completed_weight = None

        locked.save(
            update_fields=[
                "status",
                "progress",
                "message",
                "error",
                "task_id",
                "started_at",
                "finished_at",
                "duration_ms",
                "heartbeat_at",
                "output_path",
                "stage",
                "stage_index",
                "stage_count",
                "stage_weight",
                "stage_progress",
                "stage_started_at",
                "stage_plan",
                "stage_total_weight",
                "stage_completed_weight",
                "updated_at",
            ]
        )

        transaction.on_commit(
            lambda: enqueue_workflow_job(locked)
        )

    return locked


def cancel_workflow_job(
    job: MediaConversionJob,
) -> MediaConversionJob:
    job.refresh_from_db()

    if job.status == MediaJobStatus.DONE:
        raise ValidationError(
            "Completed workflow jobs cannot be canceled."
        )

    if job.status == MediaJobStatus.CANCELED:
        return job

    job.mark_canceled()

    try:
        handler = load_workflow_handler(job)
        callback = getattr(
            handler,
            "cancel_workflow",
            None,
        )

        if callable(callback):
            callback(job)
    except Exception:
        # Job cancellation itself remains authoritative.
        pass

    return job