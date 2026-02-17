# apps/asset_delivery/services/job_resolver.py

from typing import Optional
from django.contrib.contenttypes.models import ContentType

from apps.media_conversion.models import MediaConversionJob, MediaJobStatus


def get_latest_done_output_path(*, target_obj, field_name: str, kind: str) -> Optional[str]:
    """
    Resolve playback key from latest successful conversion job.
    We assume output_path points to master manifest for HLS (or final artifact for audio).
    """
    ct = ContentType.objects.get_for_model(target_obj.__class__)

    job = (
        MediaConversionJob.objects
        .filter(
            content_type=ct,
            object_id=target_obj.pk,
            field_name=field_name,
            kind=kind,
            status=MediaJobStatus.DONE,
        )
        .order_by("-finished_at", "-updated_at")
        .first()
    )

    if not job:
        return None

    return (job.output_path or "").strip() or None
