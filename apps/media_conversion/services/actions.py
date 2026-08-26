# apps/media_conversion/services/actions.py

from __future__ import annotations

import inspect
import logging
import mimetypes
import os
import uuid
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
from apps.media_conversion.services.cancellation import (
    cleanup_canceled_media_job,
)
from apps.media_conversion.services.workflows import (
    cancel_workflow_job,
    retry_workflow_job,
)
from apps.media_conversion.tasks.audio import (
    convert_audio_to_mp3_task,
)
from apps.media_conversion.tasks.image import (
    convert_image_to_jpg_task,
    convert_moment_image_item_to_jpg_task,
)
from apps.media_conversion.tasks.video import (
    convert_video_to_multi_hls_task,
)
from utils.common.utils import FileUpload

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# Public actions
# ---------------------------------------------------------------------
def cancel_media_job(
    job: MediaConversionJob,
) -> MediaConversionJob:
    """
    Cancel one conversion job.

    Database state is authoritative.
    Celery revoke is only a best-effort optimization.

    Existing workflow and domain cleanup policies remain unchanged.
    """

    job.refresh_from_db()

    if job.kind == MediaJobKind.WORKFLOW:
        return cancel_workflow_job(
            job
        )

    task_id_to_revoke = None
    should_revoke = False

    with transaction.atomic():
        locked_job = (
            MediaConversionJob.objects
            .select_for_update()
            .select_related(
                "content_type"
            )
            .get(
                pk=job.pk
            )
        )

        if (
            locked_job.status
            == MediaJobStatus.DONE
        ):
            raise ValidationError(
                "Completed jobs cannot be canceled."
            )

        if (
            locked_job.status
            != MediaJobStatus.CANCELED
        ):
            now = timezone.now()

            task_id_to_revoke = (
                locked_job.task_id
            )

            should_revoke = bool(
                task_id_to_revoke
            )

            locked_job.status = (
                MediaJobStatus.CANCELED
            )

            locked_job.message = (
                "Canceled"
            )

            locked_job.error = None

            locked_job.progress = min(
                locked_job.progress
                or 0,
                99,
            )

            locked_job.finished_at = (
                locked_job.finished_at
                or now
            )

            locked_job.heartbeat_at = now

            update_fields = [
                "status",
                "message",
                "error",
                "progress",
                "finished_at",
                "heartbeat_at",
                "updated_at",
            ]

            if (
                locked_job.started_at
                and locked_job.duration_ms
                is None
            ):
                locked_job.duration_ms = int(
                    (
                        locked_job.finished_at
                        - locked_job.started_at
                    ).total_seconds()
                    * 1000
                )

                update_fields.append(
                    "duration_ms"
                )

            locked_job.save(
                update_fields=update_fields
            )

        canceled_snapshot = locked_job

    # CANCELED is committed before the worker is asked to stop.
    if (
        should_revoke
        and task_id_to_revoke
    ):
        try:
            current_app.control.revoke(
                task_id_to_revoke,
                terminate=False,
            )

        except Exception:
            logger.warning(
                (
                    "Could not revoke media task "
                    "job=%s task=%s"
                ),
                canceled_snapshot.pk,
                task_id_to_revoke,
                exc_info=True,
            )

    cleanup_canceled_media_job(
        canceled_snapshot,
        reason="api-cancel",
        delete_job=True,
        delete_unconverted_target=True,
    )

    persisted_job = (
        MediaConversionJob.objects
        .select_related(
            "content_type"
        )
        .filter(
            pk=canceled_snapshot.pk
        )
        .first()
    )

    return (
        persisted_job
        or canceled_snapshot
    )

def _build_canonical_fileupload_payload(
    *,
    job: MediaConversionJob,
    target,
) -> dict[str, str]:
    """
    Rebuild FileUpload configuration from the target model's
    authoritative media_conversion_config.

    Retry must use the exact same FileUpload contract as the
    initial MediaConversionMixin enqueue path.
    """

    field_name = str(
        job.field_name
        or ""
    ).strip()

    if not field_name:
        raise ValidationError(
            "Media job has no field name."
        )

    config = getattr(
        target,
        "media_conversion_config",
        None,
    )

    if (
        not isinstance(
            config,
            dict,
        )
        or field_name not in config
    ):
        raise ValidationError(
            (
                "Target does not define media conversion "
                f"configuration for '{field_name}'."
            )
        )

    resolver = getattr(
        target,
        "_resolve_upload_and_kind",
        None,
    )

    if not callable(
        resolver
    ):
        raise ValidationError(
            "Target does not support media conversion configuration."
        )

    try:
        upload, configured_kind = resolver(
            config[
                field_name
            ],
            field_name,
        )

    except Exception as exc:
        raise ValidationError(
            (
                "Could not resolve media conversion "
                f"configuration for '{field_name}'."
            )
        ) from exc

    if (
        configured_kind is not None
        and str(
            configured_kind
        )
        != str(
            job.kind
        )
    ):
        raise ValidationError(
            (
                "Media conversion configuration kind "
                "does not match the job kind."
            )
        )

    to_dict = getattr(
        upload,
        "to_dict",
        None,
    )

    if not callable(
        to_dict
    ):
        raise ValidationError(
            (
                "Media conversion upload configuration "
                "cannot be serialized."
            )
        )

    payload = to_dict()

    if not isinstance(
        payload,
        dict,
    ):
        raise ValidationError(
            "Invalid media conversion upload configuration."
        )

    required_keys = (
        "app_name",
        "direction",
        "folder",
    )

    if any(
        not str(
            payload.get(
                key,
                ""
            )
            or ""
        ).strip()
        for key in required_keys
    ):
        raise ValidationError(
            "Incomplete media conversion upload configuration."
        )

    return {
        "app_name": str(
            payload[
                "app_name"
            ]
        ),
        "direction": str(
            payload[
                "direction"
            ]
        ),
        "folder": str(
            payload[
                "folder"
            ]
        ),
    }

def retry_media_job(
    job: MediaConversionJob,
) -> MediaConversionJob:
    """
    Retry a failed or preserved canceled media job.

    The retry state and Celery task identity are committed
    before the task becomes visible to a worker.
    """

    job.refresh_from_db()

    if job.kind == MediaJobKind.WORKFLOW:
        return retry_workflow_job(
            job
        )

    if job.status not in {
        MediaJobStatus.FAILED,
        MediaJobStatus.CANCELED,
    }:
        raise ValidationError(
            "Only failed or canceled jobs can be retried."
        )

    if (
        job.max_attempts is not None
        and job.attempt >= job.max_attempts
    ):
        raise ValidationError(
            "This job has reached the maximum retry attempts."
        )

    if not job.source_path:
        raise ValidationError(
            "This job has no source file to retry."
        )

    source_path = str(
        job.source_path
    ).lstrip("/")

    if not default_storage.exists(
        source_path
    ):
        raise ValidationError(
            "The original source file no longer exists."
        )

    target = _resolve_target(
        job
    )

    task = _resolve_task(
        job
    )

    is_moment_image_item_job = (
        job.kind
        == MediaJobKind.IMAGE
        and str(
            job.field_name
            or ""
        ).startswith(
            "image_items:"
        )
    )

    if is_moment_image_item_job:
        # Keep the existing custom Moment image-item retry
        # contract untouched until that task is audited separately.
        fileupload = _build_fileupload_payload(
            source_path
        )

    else:
        fileupload = _build_canonical_fileupload_payload(
            job=job,
            target=target,
        )

    model_class = (
        job.content_type
        .model_class()
    )

    if model_class is None:
        raise ValidationError(
            "Invalid media job target model."
        )

    model_name = (
        model_class
        .__name__
    )

    app_label = (
        job.content_type
        .app_label
    )

    retry_task_id = str(
        uuid.uuid4()
    )

    retry_queue = _queue_for_kind(
        job.kind
    )

    with transaction.atomic():
        locked_job = (
            MediaConversionJob.objects
            .select_for_update()
            .select_related(
                "content_type"
            )
            .get(
                pk=job.pk
            )
        )

        if locked_job.status not in {
            MediaJobStatus.FAILED,
            MediaJobStatus.CANCELED,
        }:
            raise ValidationError(
                "This job is no longer retryable."
            )

        if (
            locked_job.max_attempts is not None
            and locked_job.attempt
            >= locked_job.max_attempts
        ):
            raise ValidationError(
                (
                    "This job has reached the "
                    "maximum retry attempts."
                )
            )

        now = timezone.now()

        locked_job.status = (
            MediaJobStatus.QUEUED
        )

        locked_job.progress = 0
        locked_job.message = (
            "Queued for retry"
        )
        locked_job.error = None

        locked_job.attempt = (
            locked_job.attempt
            or 0
        ) + 1

        # Persist task identity before broker dispatch.
        locked_job.task_id = (
            retry_task_id
        )

        locked_job.queue = (
            retry_queue
        )

        locked_job.source_path = (
            source_path
        )

        locked_job.output_path = None

        locked_job.started_at = None
        locked_job.finished_at = None
        locked_job.duration_ms = None
        locked_job.heartbeat_at = now

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

        job_id = locked_job.pk
        field_name = locked_job.field_name
        target_id = target.pk

        task_args = [
            model_name,
            app_label,
            target_id,
            field_name,
            source_path,
            fileupload,
        ]

        def _enqueue_retry_after_commit():
            _dispatch_retry_task(
                job_id=job_id,
                task_id=retry_task_id,
                task=task,
                task_args=task_args,
                queue=retry_queue,
            )

        transaction.on_commit(
            _enqueue_retry_after_commit
        )

    return (
        MediaConversionJob.objects
        .select_related(
            "content_type"
        )
        .get(
            pk=job.pk
        )
    )


# ---------------------------------------------------------------------
# Retry dispatch
# ---------------------------------------------------------------------
def _dispatch_retry_task(
    *,
    job_id: int,
    task_id: str,
    task,
    task_args: list,
    queue: str,
) -> None:
    """
    Dispatch only if this retry still owns the queued job.
    """

    still_current = (
        MediaConversionJob.objects
        .filter(
            pk=job_id,
            status=MediaJobStatus.QUEUED,
            task_id=task_id,
        )
        .exists()
    )

    if not still_current:
        return

    try:
        task.apply_async(
            args=task_args,
            queue=queue,
            task_id=task_id,
        )

    except Exception as exc:
        logger.exception(
            (
                "Failed dispatching media retry "
                "job=%s task=%s"
            ),
            job_id,
            task_id,
        )

        failed_job = (
            MediaConversionJob.objects
            .filter(
                pk=job_id,
                status=MediaJobStatus.QUEUED,
                task_id=task_id,
            )
            .first()
        )

        if failed_job is not None:
            failed_job.mark_failed(
                (
                    "Failed to enqueue media "
                    f"conversion retry: {exc}"
                )
            )


# ---------------------------------------------------------------------
# Dispatch helpers
# ---------------------------------------------------------------------
def _resolve_task(
    job: MediaConversionJob,
):
    """
    Pick the Celery task for this job.
    """

    if job.kind == MediaJobKind.VIDEO:
        return (
            convert_video_to_multi_hls_task
        )

    if job.kind == MediaJobKind.AUDIO:
        return (
            convert_audio_to_mp3_task
        )

    if job.kind == MediaJobKind.IMAGE:
        if str(
            job.field_name
            or ""
        ).startswith(
            "image_items:"
        ):
            return (
                convert_moment_image_item_to_jpg_task
            )

        return (
            convert_image_to_jpg_task
        )

    raise ValidationError(
        (
            "Unsupported media job kind: "
            f"{job.kind}"
        )
    )


def _queue_for_kind(
    kind: str,
) -> str:
    """
    Keep the current queue strategy.
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
    model_class = (
        job.content_type
        .model_class()
    )

    if model_class is None:
        raise ValidationError(
            "Invalid media job target model."
        )

    try:
        return (
            model_class
            ._base_manager
            .get(
                pk=job.object_id
            )
        )

    except model_class.DoesNotExist:
        raise ValidationError(
            "Target object no longer exists."
        )


def _build_fileupload_payload(
    source_path: str,
) -> dict[str, Any]:
    """
    Rebuild FileUpload payload for retry.
    """

    normalized_path = str(
        source_path
    ).lstrip("/")

    filename = os.path.basename(
        normalized_path
    )

    try:
        size = default_storage.size(
            normalized_path
        )
    except Exception:
        size = 0

    mime_type = (
        mimetypes.guess_type(
            filename
        )[0]
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
        "size": int(
            size
            or 0
        ),
        "size_bytes": int(
            size
            or 0
        ),
    }

    try:
        signature = inspect.signature(
            FileUpload
        )

        allowed = set(
            signature
            .parameters
            .keys()
        )

        accepts_kwargs = any(
            parameter.kind
            == inspect.Parameter.VAR_KEYWORD
            for parameter
            in signature.parameters.values()
        )

        if accepts_kwargs:
            return candidates

        return {
            key: value
            for key, value
            in candidates.items()
            if key in allowed
        }

    except Exception:
        return {
            "name": filename,
            "content_type": mime_type,
            "size": int(
                size
                or 0
            ),
        }