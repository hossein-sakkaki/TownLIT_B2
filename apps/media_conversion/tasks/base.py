# apps/media_conversion/tasks/base.py

from __future__ import annotations

import os
import time
import logging
import tempfile
import subprocess
from typing import Optional
from django.db import transaction
from celery import current_task

from django.apps import apps
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.utils import timezone

from apps.media_conversion.models import MediaConversionJob, MediaJobStatus

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# Generic instance fetch (race-safe)
# ---------------------------------------------------------------------
def get_instance(app_label: str, model_name: str, pk: int, retries: int = 3, delay: float = 0.2):
    """
    Fetch model instance with tiny retry window to avoid race with on_commit.
    """
    Model = apps.get_model(app_label=app_label, model_name=model_name)
    for i in range(retries + 1):
        try:
            return Model.objects.get(pk=pk)
        except Model.DoesNotExist:
            if i < retries:
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
        task_id = getattr(getattr(current_task, "request", None), "id", None)
        if not task_id:
            return None
        return MediaConversionJob.objects.filter(task_id=task_id).first()
    except Exception:
        return None


# ---------------------------------------------------------------------
# Target availability
# ---------------------------------------------------------------------
def _maybe_mark_target_available(job: MediaConversionJob):
    """
    If ALL conversion jobs for this target are done,
    trigger domain availability hook.
    """
    try:
        ct = job.content_type
        object_id = job.object_id

        unfinished_exists = MediaConversionJob.objects.filter(
            content_type=ct,
            object_id=object_id,
        ).exclude(
            status__in=[
                MediaJobStatus.DONE,
                MediaJobStatus.FAILED,
                MediaJobStatus.CANCELED,
            ]
        ).exists()

        if unfinished_exists:
            return

        model_class = ct.model_class()
        target = model_class.objects.filter(pk=object_id).first()
        if not target:
            return

        # Mark converted (job concern)
        if hasattr(target, "is_converted") and not target.is_converted:
            target.is_converted = True
            target.save(update_fields=["is_converted"])

        # 🔑 Delegate idempotency to domain
        if hasattr(target, "is_available") and hasattr(target, "on_available"):
            if target.is_available():
                target.on_available()

    except Exception:
        return
    

# ---------------------------------------------------------------------
# Job heartbeat & progress update (best effort)
# ---------------------------------------------------------------------
def job_update(
    job: Optional[MediaConversionJob],
    *,
    status: Optional[str] = None,
    progress: Optional[int] = None,
    message: Optional[str] = None,
    error: Optional[str] = None,

    # NEW (stage-based)
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

    ✅ Weighted-safe behavior:
    - If weighted timeline metadata exists (stage_plan + stage_total_weight),
      DO NOT overwrite job.progress with intermediate values (1..99).
    - Allow terminal progress=100 (and optionally 0) and allow updates when job is terminal.
    """
    if not job:
        return

    try:
        now = timezone.now()
        fields: list[str] = []

        # heartbeat (always)
        job.heartbeat_at = now
        fields.append("heartbeat_at")

        # status
        if status is not None and job.status != status:
            job.status = status
            fields.append("status")

        # Detect weighted timeline is active
        weighted_active = bool(getattr(job, "stage_plan", None)) and (int(getattr(job, "stage_total_weight", 0) or 0) > 0)

        # progress (⚠️ weighted-safe)
        if progress is not None:
            p = max(0, min(100, int(progress)))

            terminal_statuses = {"done", "failed", "canceled"}
            is_terminal = (getattr(job, "status", None) in terminal_statuses) or bool(finished)

            # If weighted is active, ignore intermediate p (1..99) to avoid overwriting weighted percent
            if (not weighted_active) or is_terminal or p in (0, 100):
                if job.progress != p:
                    job.progress = p
                    fields.append("progress")

        # message
        if message is not None and job.message != message:
            job.message = message
            fields.append("message")

        # error
        if error is not None:
            e = (error or "")[:20000]
            if job.error != e:
                job.error = e
                fields.append("error")

        # source/output paths
        if source_path is not None and job.source_path != source_path:
            job.source_path = source_path
            fields.append("source_path")

        if output_path is not None and job.output_path != output_path:
            job.output_path = output_path
            fields.append("output_path")

        # started/finished timestamps
        if started and not job.started_at:
            job.started_at = now
            fields.append("started_at")

        if finished and not job.finished_at:
            job.finished_at = now
            fields.append("finished_at")

        # ---- stage metadata ----
        # If stage changes, reset stage_started_at to "now"
        prev_stage = getattr(job, "stage", None)

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
            sp = max(0.0, min(1.0, float(stage_progress)))
            if job.stage_progress != sp:
                job.stage_progress = sp
                fields.append("stage_progress")

        # stage_started_at: set when explicitly requested OR stage changed
        stage_changed = (stage is not None and prev_stage != stage)
        if (stage_started or stage_changed):
            job.stage_started_at = now
            fields.append("stage_started_at")

        # duration
        if finished and job.started_at and job.finished_at and job.duration_ms is None:
            job.duration_ms = int((job.finished_at - job.started_at).total_seconds() * 1000)
            fields.append("duration_ms")

        fields.append("updated_at")
        job.save(update_fields=list(dict.fromkeys(fields)))

        # -------------------------------------------------
        # 🔑 CENTRAL AVAILABILITY TRIGGER (ONCE)
        # -------------------------------------------------
        if status == MediaJobStatus.DONE:
            transaction.on_commit(
                lambda: _maybe_mark_target_available(job)
            )

    except Exception:
        pass
    

# ---------------------------------------------------------------------
# Thumbnail helpers (video-only but reusable infra)
# ---------------------------------------------------------------------
def can_autogen_thumbnail(instance) -> bool:
    """
    Auto-thumbnail only if:
    - model has a 'thumbnail' field
    - thumbnail is empty
    - instance has a video
    """
    try:
        instance._meta.get_field("thumbnail")
    except Exception:
        return False

    if not getattr(instance, "video", None):
        return False

    thumb = getattr(instance, "thumbnail", None)
    if thumb and getattr(thumb, "name", None):
        return False

    return True


def pick_thumbnail_second(dur_ms: int | None) -> float:
    """
    Practical UGC heuristic:
    - If unknown duration: 5s
    - Very short videos: ~15% into the clip
    - Otherwise: 5s (common standard)
    """
    if not dur_ms or dur_ms <= 0:
        return 5.0

    dur_s = dur_ms / 1000.0
    if dur_s <= 6.0:
        # avoid black first frames + shaky start; still keep inside bounds
        return max(0.5, min(1.5, dur_s * 0.25))

    # common “standard”
    return min(5.0, dur_s * 0.15)


def extract_video_thumbnail(
    instance,
    source_path: str,
    *,
    seconds: float | None = None,
) -> Optional[str]:
    """
    Extract a single-frame thumbnail from video.
    Uses ffmpeg autorotation (CORRECT for mobile videos).
    """
    if not source_path or not default_storage.exists(source_path):
        return None


    from utils.common.video_utils import (
        _probe_duration_ms,
    )

    with tempfile.TemporaryDirectory() as tmp:
        in_path = os.path.join(tmp, "input")
        out_path = os.path.join(tmp, "thumb.jpg")

        # --------------------------------
        # Copy from storage → local
        # --------------------------------
        with default_storage.open(source_path, "rb") as rf:
            with open(in_path, "wb") as wf:
                wf.write(rf.read())

        # --------------------------------
        # Pick timestamp
        # --------------------------------
        dur_ms = _probe_duration_ms(in_path)
        if seconds is None:
            seconds = pick_thumbnail_second(dur_ms)

        # --------------------------------
        # ffmpeg (ALLOW autorotate)
        # --------------------------------
        vf = ",".join([
            "scale=720:-2",
            "setsar=1",
        ])

        cmd = [
            "ffmpeg", "-y",
            "-hide_banner",
            "-ss", str(seconds),
            "-i", in_path,
            "-frames:v", "1",
            "-vf", vf,
            "-q:v", "3",
            out_path,
        ]

        try:
            subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            logger.warning("Thumbnail ffmpeg failed: %s", e)
            return None

        if not os.path.exists(out_path):
            return None

        with open(out_path, "rb") as f:
            data = f.read()

    # --------------------------------
    # Save
    # --------------------------------
    filename = f"thumb_{instance.pk}.jpg"
    rel_path = instance.thumbnail.field.generate_filename(instance, filename)
    default_storage.save(rel_path, ContentFile(data))

    return rel_path




# ---------------------------------------------------------------------
# Model binding (no re-upload)
# ---------------------------------------------------------------------
def maybe_activate_after_convert(instance, field_name: str, update_fields: list[str]) -> None:
    """
    Optional model hook:
      def on_media_converted(self, field_name, update_fields): ...
    """
    hook = getattr(instance, "on_media_converted", None)
    if callable(hook):
        try:
            hook(field_name, update_fields)
        except Exception as e:
            logger.warning("Activation hook failed: %s", e)


# REPLACE bind_converted_file ENTIRELY
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
    Does NOT decide conversion completion unless explicitly told.
    """
    if os.path.isabs(relative_path):
        raise ValueError("Expected relative storage path.")

    try:
        instance = get_instance(app_label, model_name, instance_id)

        if not hasattr(instance, field_name):
            raise AttributeError(f"{model_name} has no field '{field_name}'")

        if not default_storage.exists(relative_path):
            logger.error("Converted file missing: %s", relative_path)
            return

        file_field = getattr(instance, field_name)
        file_field.name = relative_path

        update_fields = [field_name]

        # ✅ ONLY mark converted when explicitly allowed
        if mark_converted and hasattr(instance, "is_converted"):
            instance.is_converted = True
            update_fields.append("is_converted")

        maybe_activate_after_convert(instance, field_name, update_fields)
        instance.save(update_fields=update_fields)

        logger.info(
            "Bound converted file %s -> %s[%s].%s (mark_converted=%s)",
            relative_path,
            model_name,
            instance_id,
            field_name,
            mark_converted,
        )

    except Exception:
        logger.exception("Failed to bind converted file")
        raise
