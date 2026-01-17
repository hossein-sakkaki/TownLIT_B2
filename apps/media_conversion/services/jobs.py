# apps/media_conversion/services/jobs.py

from django.utils import timezone
from django.contrib.contenttypes.models import ContentType

from apps.media_conversion.models import (
    MediaConversionJob,
    MediaJobStatus,
    MediaJobKind,
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
):
    """
    Create/update a job for (instance, field_name) and RESET any prior stage/timeline metadata.
    This prevents stale weighted-timeline fields from leaking across runs.
    """
    ct = get_ct(instance)
    now = timezone.now()

    kind_val = kind
    if kind_val not in {MediaJobKind.VIDEO, MediaJobKind.AUDIO, MediaJobKind.IMAGE}:
        raise ValueError(f"Invalid kind: {kind_val}")

    # NOTE:
    # - Always reset stage + weighted timeline metadata
    # - Keep heartbeat fresh
    # - Reset started/finished/duration for a new run
    job, _ = MediaConversionJob.objects.update_or_create(
        content_type=ct,
        object_id=instance.pk,
        field_name=field_name,
        defaults={
            # what
            "kind": kind_val,

            # lifecycle
            "status": status,
            "progress": 0 if status == MediaJobStatus.QUEUED else 1,
            "message": message,
            "error": None,

            # celery
            "task_id": task_id,
            "queue": queue,

            # io
            "source_path": source_path,
            "output_path": None,

            # health/timing
            "heartbeat_at": now,
            "started_at": None,
            "finished_at": None,
            "duration_ms": None,

            # ---- RESET stage-based metadata ----
            "stage": None,
            "stage_index": None,
            "stage_count": None,
            "stage_weight": None,
            "stage_progress": None,
            "stage_started_at": None,

            # ---- RESET weighted timeline metadata ----
            "stage_plan": None,
            "stage_total_weight": None,
            "stage_completed_weight": None,
        },
    )
    return job


def attach_task(job: MediaConversionJob, task_id: str, queue: str | None = None):
    job.task_id = task_id
    if queue:
        job.queue = queue
    job.save(update_fields=["task_id", "queue", "updated_at"])
    return job
