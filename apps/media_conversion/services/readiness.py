# apps/media_conversion/services/readiness.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from django.contrib.contenttypes.models import ContentType

from apps.media_conversion.models import MediaConversionJob, MediaJobStatus


@dataclass(frozen=True)
class MediaReadyState:
    ready: bool
    # "ready" | "queued" | "processing" | "failed" | "canceled" | "missing" | ...
    status: str
    job_id: Optional[int] = None


def _ct_for(obj) -> ContentType:
    # Use non-concrete to keep proxy/abstract patterns safe
    return ContentType.objects.get_for_model(obj, for_concrete_model=False)


def get_job_for(obj, field_name: str) -> Optional[MediaConversionJob]:
    ct = _ct_for(obj)
    # Unique per (content_type, object_id, field_name)
    return (
        MediaConversionJob.objects
        .filter(content_type=ct, object_id=obj.pk, field_name=field_name)
        .only("id", "status", "output_path")  # keep query light
        .first()
    )


def get_media_ready_state(
    obj,
    field_name: str,
    *,
    require_job: bool = False,
    require_output_path_on_done: bool = True,
) -> MediaReadyState:
    """
    Central truth for gating UI/urls/notifications.

    Rules:
      - DONE => ready (optionally require output_path)
      - QUEUED/PROCESSING => not ready
      - FAILED/CANCELED => not ready
      - MISSING => ready only if require_job=False
    """
    job = get_job_for(obj, field_name)

    if not job:
        # Missing job can happen due to races (on_commit / worker delay).
        # For conversion-dependent media, call with require_job=True.
        return MediaReadyState(
            ready=(not require_job),
            status="missing",
            job_id=None,
        )

    if job.status == MediaJobStatus.DONE:
        # Optional hardening: DONE but no output is not usable.
        if require_output_path_on_done and not getattr(job, "output_path", None):
            return MediaReadyState(
                ready=False,
                status="ready_but_missing_output",
                job_id=job.id,
            )
        return MediaReadyState(ready=True, status="ready", job_id=job.id)

    if job.status in (MediaJobStatus.QUEUED, MediaJobStatus.PROCESSING):
        return MediaReadyState(ready=False, status=str(job.status), job_id=job.id)

    if job.status in (MediaJobStatus.FAILED, MediaJobStatus.CANCELED):
        return MediaReadyState(ready=False, status=str(job.status), job_id=job.id)

    # Fallback: unknown status => not ready
    return MediaReadyState(ready=False, status=str(job.status), job_id=job.id)


def is_media_ready(
    obj,
    field_name: str,
    *,
    require_job: bool = False,
    require_output_path_on_done: bool = True,
) -> bool:
    return get_media_ready_state(
        obj,
        field_name,
        require_job=require_job,
        require_output_path_on_done=require_output_path_on_done,
    ).ready


def require_media_ready_state(
    obj,
    field_name: str,
    *,
    require_output_path_on_done: bool = True,
) -> MediaReadyState:
    # For conversion-dependent media: missing job must be treated as NOT ready.
    return get_media_ready_state(
        obj,
        field_name,
        require_job=True,
        require_output_path_on_done=require_output_path_on_done,
    )
