# apps/media_conversion/services/serializer_gate.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from django.contrib.contenttypes.models import ContentType

from apps.media_conversion.models import MediaConversionJob, MediaJobStatus


@dataclass
class MediaGateState:
    ready: bool
    status: str
    job_id: Optional[int] = None


def _get_job_for(obj, field_name: str) -> Optional[MediaConversionJob]:
    ct = ContentType.objects.get_for_model(obj.__class__, for_concrete_model=False)
    return (
        MediaConversionJob.objects
        .filter(content_type=ct, object_id=obj.id, field_name=field_name)
        .order_by("-updated_at")
        .first()
    )


def _compute_gate_state(obj, field_name: str, require_job: bool) -> MediaGateState:
    """
    ✅ HARD RULE:
    - If obj.is_converted is NOT True => NOT READY, no matter what.
      (Prevents all leaks before conversion finishes.)
    """
    job = _get_job_for(obj, field_name)

    # missing job => not ready if require_job
    if not job and require_job:
        return MediaGateState(ready=False, status="missing_job", job_id=None)

    # If conversion flag is not True, treat as not-ready (even if job says done by mistake)
    if getattr(obj, "is_converted", False) is not True:
        # If job exists, report its status; otherwise generic "processing"
        st = (job.status if job else MediaJobStatus.PROCESSING)
        return MediaGateState(ready=False, status=str(st), job_id=(job.id if job else None))

    # obj.is_converted == True → now require DONE job if present, otherwise allow
    if job:
        if job.status == MediaJobStatus.DONE:
            return MediaGateState(ready=True, status="done", job_id=job.id)
        # is_converted true ولی job done نیست؟ برای safety: not ready
        return MediaGateState(ready=False, status=str(job.status), job_id=job.id)

    # no job and not required, but is_converted True => ready
    return MediaGateState(ready=True, status="done", job_id=None)


def _strip_media_keys(data: Dict[str, Any], field_name: str) -> None:
    """
    Remove ALL media-related keys that can leak access before readiness.
    Works with your mixins (video_key, video_signed_url, thumbnail_signed_url, etc).
    """
    # primary file field
    data.pop(field_name, None)
    data.pop(f"{field_name}_key", None)
    data.pop(f"{field_name}_signed_url", None)

    # also remove thumbnail when the main media is not ready
    # (your UX requirement: no poster until conversion ends)
    data.pop("thumbnail", None)
    data.pop("thumbnail_key", None)
    data.pop("thumbnail_signed_url", None)


def gate_media_payload(
    *,
    obj,
    data: Dict[str, Any],
    viewer=None,
    field_name: str,
    require_job: bool = True,
    include_job_target: bool = True,
) -> Dict[str, Any]:
    """
    ✅ Serializer-level gate:
    - If NOT READY:
        - strip media urls/keys/signed_urls
        - add converting flags + job_target for MediaConversionPanel
    - If READY:
        - keep payload unchanged
    """
    st = _compute_gate_state(obj, field_name=field_name, require_job=require_job)

    if st.ready:
        return data

    # NOT READY => strip
    _strip_media_keys(data, field_name)

    # Provide minimal UX flags (safe)
    data["converting"] = True
    data["ready_status"] = st.status
    data["job_id"] = st.job_id

    if include_job_target:
        # Must match your jobs API expectations
        data["job_target"] = {
            "content_type_model": "posts.testimony",
            "object_id": obj.id,
            "field_name": field_name,
        }

    return data
