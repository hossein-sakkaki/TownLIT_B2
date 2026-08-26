# apps/media_conversion/tasks/base.py

from __future__ import annotations

import os
import time
import logging
import tempfile
import subprocess
from typing import Optional

from celery import current_task
from django.apps import apps
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from apps.media_conversion.models import MediaConversionJob, MediaJobStatus

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# Cancellation
# ---------------------------------------------------------------------
class MediaConversionCanceled(Exception):
    """
    Raised when the authoritative media job was canceled or removed.
    """


class MediaConversionTaskSuperseded(Exception):
    """
    Raised when this Celery task no longer owns the MediaConversionJob row.
    """


class MediaConversionSuperseded(Exception):
    """
    Raised when a queued task no longer targets the model's current source.

    The positional message form keeps the exception pickle-safe if it ever
    escapes a worker boundary.
    """

    def __init__(
        self,
        message: str | None = None,
        *,
        model_name: str = "",
        instance_id: int = 0,
        field_name: str = "",
        expected_source_path: str = "",
        current_source_path: str = "",
    ):
        self.model_name = model_name
        self.instance_id = instance_id
        self.field_name = field_name
        self.expected_source_path = expected_source_path
        self.current_source_path = current_source_path

        if message is None:
            message = (
                "Media conversion source was replaced: "
                f"{model_name}[{instance_id}].{field_name} "
                f"expected={expected_source_path!r} "
                f"current={current_source_path!r}"
            )

        super().__init__(message)
        

def get_current_task_id() -> str:
    """
    Return the active Celery task id, if called from a worker task.
    """

    try:
        return str(
            getattr(
                getattr(
                    current_task,
                    "request",
                    None,
                ),
                "id",
                "",
            )
            or ""
        )

    except Exception:
        return ""


def _get_authoritative_job(
    job: Optional[MediaConversionJob],
) -> Optional[MediaConversionJob]:
    """
    Reload the current DB row without mutating the worker's stale instance.
    """

    if not job or not getattr(job, "pk", None):
        return None

    try:
        return (
            MediaConversionJob.objects
            .select_related("content_type")
            .filter(pk=job.pk)
            .first()
        )

    except Exception:
        return None


def is_job_current_task(
    job: Optional[MediaConversionJob],
) -> bool:
    """
    True when this worker still owns the authoritative job row.

    Missing jobs are no longer authoritative.
    """

    if not job:
        return True

    authoritative = _get_authoritative_job(job)

    if authoritative is None:
        return False

    current_task_id = get_current_task_id()

    if not current_task_id:
        return True

    authoritative_task_id = str(
        authoritative.task_id
        or ""
    )

    if not authoritative_task_id:
        return True

    return authoritative_task_id == current_task_id


def is_job_canceled(
    job: Optional[MediaConversionJob],
) -> bool:
    """
    Fresh DB check.

    A job that existed when this worker started but was later deleted is
    treated as canceled. Continuing without an authoritative job would allow
    stale work to bind output after cancellation cleanup.
    """

    if not job:
        return False

    authoritative = _get_authoritative_job(job)

    if authoritative is None:
        return True

    return (
        authoritative.status
        == MediaJobStatus.CANCELED
    )


def raise_if_job_canceled(
    job: Optional[MediaConversionJob],
) -> None:
    """
    Stop when this worker is canceled or no longer owns the job.
    """

    if not job:
        return

    authoritative = _get_authoritative_job(job)

    if authoritative is None:
        raise MediaConversionCanceled(
            "Media conversion job no longer exists."
        )

    current_task_id = get_current_task_id()
    authoritative_task_id = str(
        authoritative.task_id
        or ""
    )

    if (
        current_task_id
        and authoritative_task_id
        and current_task_id
        != authoritative_task_id
    ):
        raise MediaConversionTaskSuperseded(
            (
                "Media conversion task was superseded: "
                f"job={authoritative.pk} "
                f"worker_task={current_task_id!r} "
                f"current_task={authoritative_task_id!r}"
            )
        )

    if (
        authoritative.status
        == MediaJobStatus.CANCELED
    ):
        raise MediaConversionCanceled(
            "Media conversion was canceled."
        )


# ---------------------------------------------------------------------
# Generic instance fetch
# ---------------------------------------------------------------------
def get_instance(
    app_label: str,
    model_name: str,
    pk: int,
    retries: int = 3,
    delay: float = 0.2,
):
    """
    Fetch model instance with tiny retry window to avoid race with on_commit.
    Uses _base_manager to bypass custom default managers.
    """
    Model = apps.get_model(
        app_label=app_label,
        model_name=model_name,
    )

    for index in range(retries + 1):
        try:
            return Model._base_manager.get(pk=pk)
        except Model.DoesNotExist:
            if index < retries:
                time.sleep(delay)
                continue
            raise


# ---------------------------------------------------------------------
# Source identity
# ---------------------------------------------------------------------
def normalize_storage_key(value) -> str:
    """
    Normalize a Django storage key for safe identity comparison.
    """

    if value is None:
        return ""

    name = getattr(value, "name", value)

    return str(name or "").strip().lstrip("/")


def get_instance_file_source_path(
    instance,
    field_name: str,
) -> str:
    """
    Return the current storage key from a normal model FileField/ImageField.

    Raises AttributeError for invalid field names instead of silently
    classifying a programming error as a superseded conversion.
    """

    if not hasattr(instance, field_name):
        raise AttributeError(
            f"{type(instance).__name__} has no field '{field_name}'"
        )

    return normalize_storage_key(
        getattr(instance, field_name)
    )


def raise_if_source_superseded(
    *,
    instance,
    model_name: str,
    instance_id: int,
    field_name: str,
    expected_source_path: str,
) -> None:
    """
    Stop a stale task if the model no longer references its queued source.

    An empty current source also means the original upload was cleared and
    the queued task must not continue or bind its output.
    """

    expected_key = normalize_storage_key(
        expected_source_path
    )

    current_key = get_instance_file_source_path(
        instance,
        field_name,
    )

    if current_key == expected_key:
        return

    raise MediaConversionSuperseded(
        model_name=model_name,
        instance_id=instance_id,
        field_name=field_name,
        expected_source_path=expected_key,
        current_source_path=current_key,
    )

# ---------------------------------------------------------------------
# Job resolution
# ---------------------------------------------------------------------
def get_job_by_current_task() -> Optional[MediaConversionJob]:
    """
    Resolve MediaConversionJob by current Celery task_id.
    Safe: never raises.
    """
    try:
        task_id = getattr(
            getattr(current_task, "request", None),
            "id",
            None,
        )

        if not task_id:
            return None

        return (
            MediaConversionJob.objects
            .select_related("content_type")
            .filter(task_id=task_id)
            .first()
        )

    except Exception:
        return None


# ---------------------------------------------------------------------
# Target availability
# ---------------------------------------------------------------------
def _maybe_mark_target_available(
    job: MediaConversionJob,
):
    """
    Delegate target readiness to the shared field-aware availability service.
    """

    from apps.media_conversion.services.availability import (
        maybe_mark_media_target_available,
    )

    maybe_mark_media_target_available(
        job
    )


# ---------------------------------------------------------------------
# Job heartbeat & progress update
# ---------------------------------------------------------------------
def job_update(
    job: Optional[MediaConversionJob],
    *,
    status: Optional[str] = None,
    progress: Optional[int] = None,
    message: Optional[str] = None,
    error: Optional[str] = None,

    stage: Optional[str] = None,
    stage_index: Optional[int] = None,
    stage_count: Optional[int] = None,
    stage_weight: Optional[int] = None,
    stage_progress: Optional[float] = None,
    stage_started: bool = False,

    source_path: Optional[str] = None,
    output_path: Optional[str] = None,
    started: bool = False,
    finished: bool = False,
) -> None:
    """
    Best-effort authoritative MediaConversionJob update.

    Safety:
    - CANCELED cannot be overwritten by worker progress/failure.
    - A stale Celery task cannot mutate a job row that has been reassigned.
    - A deleted job is never recreated or treated as authoritative.
    """

    if not job:
        return

    try:
        authoritative = _get_authoritative_job(
            job
        )

        if authoritative is None:
            return

        current_task_id = get_current_task_id()
        authoritative_task_id = str(
            authoritative.task_id
            or ""
        )

        if (
            current_task_id
            and authoritative_task_id
            and current_task_id
            != authoritative_task_id
        ):
            return

        if (
            authoritative.status
            == MediaJobStatus.CANCELED
            and status
            != MediaJobStatus.CANCELED
        ):
            return

        job = authoritative

        now = timezone.now()
        fields: list[str] = []

        job.heartbeat_at = now
        fields.append("heartbeat_at")

        if (
            status is not None
            and job.status != status
        ):
            job.status = status
            fields.append("status")

        weighted_active = bool(
            getattr(
                job,
                "stage_plan",
                None,
            )
        ) and (
            int(
                getattr(
                    job,
                    "stage_total_weight",
                    0,
                )
                or 0
            )
            > 0
        )

        if progress is not None:
            normalized_progress = max(
                0,
                min(
                    100,
                    int(progress),
                ),
            )

            terminal_statuses = {
                MediaJobStatus.DONE,
                MediaJobStatus.FAILED,
                MediaJobStatus.CANCELED,
            }

            is_terminal = (
                job.status
                in terminal_statuses
            ) or bool(
                finished
            )

            if (
                not weighted_active
                or is_terminal
                or normalized_progress
                in {
                    0,
                    100,
                }
            ):
                if (
                    job.progress
                    != normalized_progress
                ):
                    job.progress = (
                        normalized_progress
                    )

                    fields.append(
                        "progress"
                    )

        if (
            message is not None
            and job.message != message
        ):
            job.message = message
            fields.append("message")

        if error is not None:
            cleaned_error = (
                error
                or ""
            )[:20000]

            if job.error != cleaned_error:
                job.error = cleaned_error
                fields.append("error")

        if (
            source_path is not None
            and job.source_path != source_path
        ):
            job.source_path = source_path
            fields.append("source_path")

        if (
            output_path is not None
            and job.output_path != output_path
        ):
            job.output_path = output_path
            fields.append("output_path")

        if (
            started
            and not job.started_at
        ):
            job.started_at = now
            fields.append("started_at")

        if (
            finished
            and not job.finished_at
        ):
            job.finished_at = now
            fields.append("finished_at")

        previous_stage = (
            job.stage
        )

        if (
            stage is not None
            and job.stage != stage
        ):
            job.stage = stage
            fields.append("stage")

        if (
            stage_index is not None
            and job.stage_index
            != stage_index
        ):
            job.stage_index = stage_index
            fields.append("stage_index")

        if (
            stage_count is not None
            and job.stage_count
            != stage_count
        ):
            job.stage_count = stage_count
            fields.append("stage_count")

        if (
            stage_weight is not None
            and job.stage_weight
            != stage_weight
        ):
            job.stage_weight = stage_weight
            fields.append("stage_weight")

        if stage_progress is not None:
            normalized_stage_progress = max(
                0.0,
                min(
                    1.0,
                    float(
                        stage_progress
                    ),
                ),
            )

            if (
                job.stage_progress
                != normalized_stage_progress
            ):
                job.stage_progress = (
                    normalized_stage_progress
                )

                fields.append(
                    "stage_progress"
                )

        stage_changed = (
            stage is not None
            and previous_stage != stage
        )

        if (
            stage_started
            or stage_changed
        ):
            job.stage_started_at = now
            fields.append(
                "stage_started_at"
            )

        if (
            finished
            and job.started_at
            and job.finished_at
            and job.duration_ms is None
        ):
            job.duration_ms = int(
                (
                    job.finished_at
                    - job.started_at
                ).total_seconds()
                * 1000
            )

            fields.append(
                "duration_ms"
            )

        fields.append(
            "updated_at"
        )

        job.save(
            update_fields=list(
                dict.fromkeys(
                    fields
                )
            )
        )

        if (
            status
            == MediaJobStatus.DONE
        ):
            transaction.on_commit(
                lambda: (
                    _maybe_mark_target_available(
                        job
                    )
                )
            )

    except Exception:
        return

# ---------------------------------------------------------------------
# Thumbnail helpers
# ---------------------------------------------------------------------
def can_autogen_thumbnail(instance) -> bool:
    """
    Auto-thumbnail only if:
    - model has a thumbnail field
    - thumbnail is empty
    - instance has a video
    """
    try:
        instance._meta.get_field("thumbnail")
    except Exception:
        return False

    if not getattr(instance, "video", None):
        return False

    thumbnail = getattr(instance, "thumbnail", None)
    if thumbnail and getattr(thumbnail, "name", None):
        return False

    return True


def pick_thumbnail_second(dur_ms: int | None) -> float:
    """
    Practical UGC heuristic.
    """
    if not dur_ms or dur_ms <= 0:
        return 5.0

    duration_seconds = dur_ms / 1000.0

    if duration_seconds <= 6.0:
        return max(
            0.5,
            min(1.5, duration_seconds * 0.25),
        )

    return min(
        5.0,
        duration_seconds * 0.15,
    )


def extract_video_thumbnail(
    instance,
    source_path: str,
    *,
    seconds: float | None = None,
) -> Optional[str]:
    """
    Extract a single-frame thumbnail from video.
    """
    if not source_path or not default_storage.exists(source_path):
        return None

    from utils.common.video_utils import _probe_duration_ms

    with tempfile.TemporaryDirectory() as tmp:
        in_path = os.path.join(tmp, "input")
        out_path = os.path.join(tmp, "thumb.jpg")

        with default_storage.open(source_path, "rb") as read_file:
            with open(in_path, "wb") as write_file:
                write_file.write(read_file.read())

        duration_ms = _probe_duration_ms(in_path)

        if seconds is None:
            seconds = pick_thumbnail_second(duration_ms)

        vf = ",".join(
            [
                "scale=720:-2",
                "setsar=1",
            ]
        )

        cmd = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-ss",
            str(seconds),
            "-i",
            in_path,
            "-frames:v",
            "1",
            "-vf",
            vf,
            "-q:v",
            "3",
            out_path,
        ]

        try:
            subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as exc:
            logger.warning("Thumbnail ffmpeg failed: %s", exc)
            return None

        if not os.path.exists(out_path):
            return None

        with open(out_path, "rb") as file:
            data = file.read()

    filename = f"thumb_{instance.pk}.jpg"
    relative_path = instance.thumbnail.field.generate_filename(
        instance,
        filename,
    )

    default_storage.save(
        relative_path,
        ContentFile(data),
    )

    return relative_path


# ---------------------------------------------------------------------
# Model binding
# ---------------------------------------------------------------------
def maybe_activate_after_convert(
    instance,
    field_name: str,
    update_fields: list[str],
) -> None:
    """
    Optional model hook:
    def on_media_converted(self, field_name, update_fields): ...
    """
    hook = getattr(instance, "on_media_converted", None)

    if callable(hook):
        try:
            hook(field_name, update_fields)
        except Exception as exc:
            logger.warning("Activation hook failed: %s", exc)


def _bind_converted_file_to_instance(
    *,
    instance,
    model_name: str,
    instance_id: int,
    field_name: str,
    relative_path: str,
    mark_converted: bool,
) -> None:
    """
    Apply one converted storage key to an already-resolved instance.
    """

    if not hasattr(instance, field_name):
        raise AttributeError(
            f"{model_name} has no field '{field_name}'"
        )

    file_field = getattr(
        instance,
        field_name,
    )

    file_field.name = relative_path

    update_fields = [field_name]

    if mark_converted and hasattr(instance, "is_converted"):
        instance.is_converted = True
        update_fields.append("is_converted")

    maybe_activate_after_convert(
        instance,
        field_name,
        update_fields,
    )

    # Prevent worker-bound output from re-enqueueing conversion.
    setattr(
        instance,
        "_skip_media_autoconvert_once",
        True,
    )

    instance.save(
        update_fields=list(
            dict.fromkeys(update_fields)
        )
    )

    logger.info(
        "Bound converted file %s -> %s[%s].%s mark_converted=%s",
        relative_path,
        model_name,
        instance_id,
        field_name,
        mark_converted,
    )
    
    
def bind_converted_file(
    *,
    model_name: str,
    app_label: str,
    instance_id: int,
    field_name: str,
    relative_path: str,
    mark_converted: bool = False,
    expected_source_path: str | None = None,
) -> None:
    """
    Bind an already-uploaded converted file to a model field.

    When expected_source_path is provided, binding is guarded by a row lock.
    The output is bound only if the model still references the source that
    originally created this conversion task.

    Existing callers that do not pass expected_source_path preserve the
    previous behavior.
    """

    if os.path.isabs(relative_path):
        raise ValueError("Expected relative storage path.")

    normalized_output_path = normalize_storage_key(
        relative_path
    )

    if not default_storage.exists(
        normalized_output_path
    ):
        raise FileNotFoundError(
            (
                "Converted media output does not "
                "exist in storage: "
                f"{normalized_output_path}"
            )
        )

    try:
        if expected_source_path is None:
            instance = get_instance(
                app_label,
                model_name,
                instance_id,
            )

            _bind_converted_file_to_instance(
                instance=instance,
                model_name=model_name,
                instance_id=instance_id,
                field_name=field_name,
                relative_path=normalized_output_path,
                mark_converted=mark_converted,
            )

            return

        model_class = apps.get_model(
            app_label=app_label,
            model_name=model_name,
        )

        with transaction.atomic():
            instance = (
                model_class._base_manager
                .select_for_update()
                .get(pk=instance_id)
            )

            raise_if_source_superseded(
                instance=instance,
                model_name=model_name,
                instance_id=instance_id,
                field_name=field_name,
                expected_source_path=expected_source_path,
            )

            _bind_converted_file_to_instance(
                instance=instance,
                model_name=model_name,
                instance_id=instance_id,
                field_name=field_name,
                relative_path=normalized_output_path,
                mark_converted=mark_converted,
            )

    except MediaConversionSuperseded:
        raise

    except Exception:
        logger.exception("Failed to bind converted file")
        raise