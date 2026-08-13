# apps/media_conversion/services/jobs.py

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from apps.media_conversion.models import (
    MediaConversionJob,
    MediaJobKind,
    MediaJobStatus,
)


def get_ct(instance):
    return ContentType.objects.get_for_model(instance.__class__)


def upsert_job(
    instance,
    field_name: str,
    kind: str,
    *,
    status: str = MediaJobStatus.QUEUED,
    source_path: str | None = None,
    task_id: str | None = None,
    queue: str | None = None,
    message: str | None = None,
    workflow_handler: str | None = None,
    payload: dict | None = None,
):
    """
    Create/update one processing job per object field.

    Existing media jobs keep their current behavior.
    Workflow jobs may persist a handler and request snapshot.
    """
    ct = get_ct(instance)
    now = timezone.now()

    allowed_kinds = {
        MediaJobKind.VIDEO,
        MediaJobKind.AUDIO,
        MediaJobKind.IMAGE,
        MediaJobKind.WORKFLOW,
    }

    if kind not in allowed_kinds:
        raise ValueError(f"Invalid kind: {kind}")

    if kind == MediaJobKind.WORKFLOW and not workflow_handler:
        raise ValueError("Workflow jobs require a workflow_handler.")

    job, _ = MediaConversionJob.objects.update_or_create(
        content_type=ct,
        object_id=instance.pk,
        field_name=field_name,
        defaults={
            "kind": kind,
            "status": status,
            "progress": 0 if status == MediaJobStatus.QUEUED else 1,
            "message": message,
            "error": None,
            "task_id": task_id,
            "queue": queue,
            "workflow_handler": workflow_handler,
            "payload": dict(payload or {}),
            "source_path": source_path,
            "output_path": None,
            "heartbeat_at": now,
            "started_at": None,
            "finished_at": None,
            "duration_ms": None,
            "stage": None,
            "stage_index": None,
            "stage_count": None,
            "stage_weight": None,
            "stage_progress": None,
            "stage_started_at": None,
            "stage_plan": None,
            "stage_total_weight": None,
            "stage_completed_weight": None,
        },
    )

    return job


def attach_task(
    job: MediaConversionJob,
    task_id: str,
    queue: str | None = None,
):
    job.task_id = task_id

    if queue:
        job.queue = queue

    job.save(
        update_fields=[
            "task_id",
            "queue",
            "updated_at",
        ]
    )

    return job