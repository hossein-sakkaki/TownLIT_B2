# apps/media_conversion/services/actions.py

from __future__ import annotations

import inspect
import mimetypes
import os
from typing import Any

from celery import current_app
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.db import transaction
from django.utils import timezone

from apps.media_conversion.models import (
    MediaConversionJob,
    MediaJobKind,
    MediaJobStatus,
)
from apps.media_conversion.services.jobs import attach_task
from apps.media_conversion.services.cancellation import cleanup_canceled_media_job
from apps.media_conversion.tasks.video import convert_video_to_multi_hls_task
from apps.media_conversion.tasks.audio import convert_audio_to_mp3_task
from apps.media_conversion.tasks.image import (
    convert_image_to_jpg_task,
    convert_moment_image_item_to_jpg_task,
)

from utils.common.utils import FileUpload


# ---------------------------------------------------------------------
# Public actions
# ---------------------------------------------------------------------
def cancel_media_job(
    job: MediaConversionJob,
) -> MediaConversionJob:
    """
    Cancel and root-clean a media conversion job.

    Important:
    - Marks job as CANCELED first.
    - Revokes queued task best-effort.
    - Immediately removes storage artifacts and unconverted Moment target.
    - Deletes MediaConversionJob row after cleanup, but returns the last snapshot.
    """
    job.refresh_from_db()

    if job.status == MediaJobStatus.DONE:
        raise ValidationError("Completed jobs cannot be canceled.")

    if job.status == MediaJobStatus.CANCELED:
        return job

    now = timezone.now()

    if job.task_id:
        try:
            current_app.control.revoke(
                job.task_id,
                terminate=False,
            )
        except Exception:
            pass

    job.status = MediaJobStatus.CANCELED
    job.message = "Canceled"
    job.error = None
    job.progress = min(job.progress or 0, 99)
    job.finished_at = job.finished_at or now
    job.heartbeat_at = now

    update_fields = [
        "status",
        "message",
        "error",
        "progress",
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

    # Keep a response-safe snapshot before cleanup deletes DB rows.
    canceled_snapshot = (
        MediaConversionJob.objects
        .select_related("content_type")
        .get(pk=job.pk)
    )

    cleanup_canceled_media_job(
        canceled_snapshot,
        reason="api-cancel",
        delete_job=True,
        delete_unconverted_target=True,
    )

    return canceled_snapshot


def retry_media_job(
    job: MediaConversionJob,
) -> MediaConversionJob:
    """
    Retry a failed/canceled media conversion job by dispatching the real Celery task.

    This is NOT only a status reset:
    - validates retry eligibility
    - validates target/source
    - resets lifecycle/stage/timeline fields
    - dispatches the correct task
    - attaches the new Celery task id to the job
    """
    job.refresh_from_db()

    if job.status not in {
        MediaJobStatus.FAILED,
        MediaJobStatus.CANCELED,
    }:
        raise ValidationError("Only failed or canceled jobs can be retried.")

    if job.max_attempts is not None and job.attempt >= job.max_attempts:
        raise ValidationError("This job has reached the maximum retry attempts.")

    if not job.source_path:
        raise ValidationError("This job has no source file to retry.")

    source_path = str(job.source_path).lstrip("/")

    if not default_storage.exists(source_path):
        raise ValidationError("The original source file no longer exists.")

    target = _resolve_target(job)
    task = _resolve_task(job)
    fileupload = _build_fileupload_payload(source_path)

    model_class = job.content_type.model_class()
    if model_class is None:
        raise ValidationError("Invalid media job target model.")

    model_name = model_class.__name__
    app_label = job.content_type.app_label

    with transaction.atomic():
        locked_job = (
            MediaConversionJob.objects
            .select_for_update()
            .select_related("content_type")
            .get(pk=job.pk)
        )

        if locked_job.status not in {
            MediaJobStatus.FAILED,
            MediaJobStatus.CANCELED,
        }:
            raise ValidationError("This job is no longer retryable.")

        now = timezone.now()

        locked_job.status = MediaJobStatus.QUEUED
        locked_job.progress = 0
        locked_job.message = "Queued for retry"
        locked_job.error = None

        locked_job.attempt = (locked_job.attempt or 0) + 1
        locked_job.task_id = None
        locked_job.queue = _queue_for_kind(locked_job.kind)

        locked_job.source_path = source_path
        locked_job.output_path = None

        locked_job.started_at = None
        locked_job.finished_at = None
        locked_job.duration_ms = None
        locked_job.heartbeat_at = now

        # Reset stage timeline.
        locked_job.stage = None
        locked_job.stage_index = None
        locked_job.stage_count = None
        locked_job.stage_weight = None
        locked_job.stage_progress = None
        locked_job.stage_started_at = None

        locked_job.stage_plan = None
        locked_job.stage_total_weight = None
        locked_job.stage_completed_weight = None

        locked_job.save(
            update_fields=[
                "status",
                "progress",
                "message",
                "error",
                "attempt",
                "task_id",
                "queue",
                "source_path",
                "output_path",
                "started_at",
                "finished_at",
                "duration_ms",
                "heartbeat_at",
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

        result = task.apply_async(
            args=[
                model_name,
                app_label,
                target.pk,
                locked_job.field_name,
                source_path,
                fileupload,
            ],
            queue=locked_job.queue or _queue_for_kind(locked_job.kind),
        )

        attach_task(
            locked_job,
            task_id=result.id,
            queue=locked_job.queue or _queue_for_kind(locked_job.kind),
        )

        locked_job.refresh_from_db()
        return locked_job


# ---------------------------------------------------------------------
# Dispatch helpers
# ---------------------------------------------------------------------
def _resolve_task(
    job: MediaConversionJob,
):
    """
    Pick the real Celery task for this job.
    """
    if job.kind == MediaJobKind.VIDEO:
        return convert_video_to_multi_hls_task

    if job.kind == MediaJobKind.AUDIO:
        return convert_audio_to_mp3_task

    if job.kind == MediaJobKind.IMAGE:
        if str(job.field_name or "").startswith("image_items:"):
            return convert_moment_image_item_to_jpg_task

        return convert_image_to_jpg_task

    raise ValidationError(f"Unsupported media job kind: {job.kind}")


def _queue_for_kind(
    kind: str,
) -> str:
    """
    Keep current queue strategy.
    """
    if kind in {
        MediaJobKind.VIDEO,
        MediaJobKind.AUDIO,
        MediaJobKind.IMAGE,
    }:
        return "video"

    return "video"


def _resolve_target(
    job: MediaConversionJob,
):
    model_class = job.content_type.model_class()

    if model_class is None:
        raise ValidationError("Invalid media job target model.")

    try:
        return model_class._base_manager.get(pk=job.object_id)
    except model_class.DoesNotExist:
        raise ValidationError("Target object no longer exists.")


def _build_fileupload_payload(
    source_path: str,
) -> dict[str, Any]:
    """
    Rebuild FileUpload payload for retry.

    The original task receives `fileupload: dict` and then calls:
        FileUpload(**fileupload)

    Because FileUpload shape may evolve, we inspect its accepted parameters and
    provide only matching keys.
    """
    normalized_path = str(source_path).lstrip("/")
    filename = os.path.basename(normalized_path)

    try:
        size = default_storage.size(normalized_path)
    except Exception:
        size = 0

    mime_type = (
        mimetypes.guess_type(filename)[0]
        or "application/octet-stream"
    )

    candidates: dict[str, Any] = {
        "name": filename,
        "filename": filename,
        "file_name": filename,
        "original_name": filename,
        "original_filename": filename,
        "path": normalized_path,
        "source_path": normalized_path,
        "content_type": mime_type,
        "mime_type": mime_type,
        "size": int(size or 0),
        "size_bytes": int(size or 0),
    }

    try:
        signature = inspect.signature(FileUpload)
        allowed = set(signature.parameters.keys())

        # If FileUpload accepts **kwargs, send the full safe payload.
        accepts_kwargs = any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD
            for parameter in signature.parameters.values()
        )

        if accepts_kwargs:
            return candidates

        return {
            key: value
            for key, value in candidates.items()
            if key in allowed
        }

    except Exception:
        # Fallback for dataclass / pydantic-like wrappers.
        return {
            "name": filename,
            "content_type": mime_type,
            "size": int(size or 0),
        }