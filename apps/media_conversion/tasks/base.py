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
    Raised when a user cancels a media conversion job.
    """


def is_job_canceled(job: Optional[MediaConversionJob]) -> bool:
    """
    Fresh DB check. Never trust a stale job instance inside a long task.
    """
    if not job:
        return False

    try:
        job.refresh_from_db(fields=["status", "updated_at"])
        return job.status == MediaJobStatus.CANCELED
    except Exception:
        return False


def raise_if_job_canceled(job: Optional[MediaConversionJob]) -> None:
    """
    Stop the worker flow if the user canceled this job.
    """
    if is_job_canceled(job):
        raise MediaConversionCanceled("Media conversion was canceled.")


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
def _maybe_mark_target_available(job: MediaConversionJob):
    """
    Mark target converted / available only when all jobs for that target are DONE.

    Important:
    FAILED or CANCELED jobs must NOT make the object available.
    """
    try:
        ct = job.content_type
        object_id = job.object_id

        jobs = MediaConversionJob.objects.filter(
            content_type=ct,
            object_id=object_id,
        )

        has_unfinished = jobs.exclude(
            status__in=[
                MediaJobStatus.DONE,
                MediaJobStatus.FAILED,
                MediaJobStatus.CANCELED,
            ]
        ).exists()

        if has_unfinished:
            return

        has_failed_or_canceled = jobs.filter(
            status__in=[
                MediaJobStatus.FAILED,
                MediaJobStatus.CANCELED,
            ]
        ).exists()

        if has_failed_or_canceled:
            return

        all_done = jobs.exists() and not jobs.exclude(
            status=MediaJobStatus.DONE
        ).exists()

        if not all_done:
            return

        model_class = ct.model_class()
        if not model_class:
            return

        target = model_class._base_manager.filter(pk=object_id).first()
        if not target:
            return

        if hasattr(target, "is_converted") and not target.is_converted:
            target.is_converted = True
            target.save(update_fields=["is_converted"])

        if hasattr(target, "is_available") and hasattr(target, "on_available"):
            if target.is_available():
                target.on_available()

    except Exception:
        logger.exception(
            "Failed to mark target available for MediaConversionJob id=%s",
            getattr(job, "id", None),
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
    Best-effort MediaConversionJob update.
    MUST NEVER raise.

    Cancel safety:
    - If the job was canceled by user, do not overwrite it with processing/done/failed.
    - Only allow status=canceled to pass through.
    """
    if not job:
        return

    try:
        try:
            job.refresh_from_db()
        except Exception:
            pass

        if job.status == MediaJobStatus.CANCELED and status != MediaJobStatus.CANCELED:
            return

        now = timezone.now()
        fields: list[str] = []

        job.heartbeat_at = now
        fields.append("heartbeat_at")

        if status is not None and job.status != status:
            job.status = status
            fields.append("status")

        weighted_active = bool(getattr(job, "stage_plan", None)) and (
            int(getattr(job, "stage_total_weight", 0) or 0) > 0
        )

        if progress is not None:
            p = max(0, min(100, int(progress)))

            terminal_statuses = {
                MediaJobStatus.DONE,
                MediaJobStatus.FAILED,
                MediaJobStatus.CANCELED,
            }

            is_terminal = (
                getattr(job, "status", None) in terminal_statuses
            ) or bool(finished)

            if (not weighted_active) or is_terminal or p in (0, 100):
                if job.progress != p:
                    job.progress = p
                    fields.append("progress")

        if message is not None and job.message != message:
            job.message = message
            fields.append("message")

        if error is not None:
            cleaned_error = (error or "")[:20000]
            if job.error != cleaned_error:
                job.error = cleaned_error
                fields.append("error")

        if source_path is not None and job.source_path != source_path:
            job.source_path = source_path
            fields.append("source_path")

        if output_path is not None and job.output_path != output_path:
            job.output_path = output_path
            fields.append("output_path")

        if started and not job.started_at:
            job.started_at = now
            fields.append("started_at")

        if finished and not job.finished_at:
            job.finished_at = now
            fields.append("finished_at")

        previous_stage = getattr(job, "stage", None)

        if stage is not None and job.stage != stage:
            job.stage = stage
            fields.append("stage")

        if stage_index is not None and job.stage_index != stage_index:
            job.stage_index = stage_index
            fields.append("stage_index")

        if stage_count is not None and job.stage_count != stage_count:
            job.stage_count = stage_count
            fields.append("stage_count")

        if stage_weight is not None and job.stage_weight != stage_weight:
            job.stage_weight = stage_weight
            fields.append("stage_weight")

        if stage_progress is not None:
            normalized_stage_progress = max(
                0.0,
                min(1.0, float(stage_progress)),
            )

            if job.stage_progress != normalized_stage_progress:
                job.stage_progress = normalized_stage_progress
                fields.append("stage_progress")

        stage_changed = stage is not None and previous_stage != stage

        if stage_started or stage_changed:
            job.stage_started_at = now
            fields.append("stage_started_at")

        if finished and job.started_at and job.finished_at and job.duration_ms is None:
            job.duration_ms = int(
                (job.finished_at - job.started_at).total_seconds() * 1000
            )
            fields.append("duration_ms")

        fields.append("updated_at")

        job.save(update_fields=list(dict.fromkeys(fields)))

        if status == MediaJobStatus.DONE:
            transaction.on_commit(
                lambda: _maybe_mark_target_available(job)
            )

    except Exception:
        pass


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


def bind_converted_file(
    *,
    model_name: str,
    app_label: str,
    instance_id: int,
    field_name: str,
    relative_path: str,
    mark_converted: bool = False,
) -> None:
    """
    Bind already-uploaded converted file to model field.
    Does not decide conversion completion unless explicitly told.
    """
    if os.path.isabs(relative_path):
        raise ValueError("Expected relative storage path.")

    try:
        instance = get_instance(
            app_label,
            model_name,
            instance_id,
        )

        if not hasattr(instance, field_name):
            raise AttributeError(
                f"{model_name} has no field '{field_name}'"
            )

        if not default_storage.exists(relative_path):
            logger.error("Converted file missing: %s", relative_path)
            return

        file_field = getattr(instance, field_name)
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

        instance.save(update_fields=update_fields)

        logger.info(
            "Bound converted file %s -> %s[%s].%s mark_converted=%s",
            relative_path,
            model_name,
            instance_id,
            field_name,
            mark_converted,
        )

    except Exception:
        logger.exception("Failed to bind converted file")
        raise