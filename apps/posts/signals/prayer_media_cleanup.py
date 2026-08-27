# apps/posts/signals/prayer_media_cleanup.py

import logging

from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType

from apps.media_conversion.models import MediaConversionJob
from apps.media_conversion.services.storage_cleanup import (
    clean_storage_key,
    delete_job_output,
    delete_storage_key,
    delete_video_output,
)
from apps.posts.models.pray import Prayer, PrayerResponse

logger = logging.getLogger(__name__)


def _safe_delete_filefield(field, label: str):
    try:
        if not field:
            return

        key = clean_storage_key(getattr(field, "name", None))
        storage = getattr(field, "storage", None)

        if not key:
            return

        is_video = (
            label == "video"
            or label.endswith(".video")
            or label.endswith("-video")
        )

        if is_video and key.lower().endswith(".m3u8"):
            delete_video_output(
                key,
                label=f"{label}.hls",
                storage=storage,
            )
        else:
            delete_storage_key(
                key,
                label=label,
                storage=storage,
            )

    except Exception:
        logger.exception(
            "Failed deleting Prayer media (%s): %s",
            label,
            getattr(field, "name", None),
        )


def _cleanup_conversion_jobs(model_class, instance_pk: int):
    try:
        ct = ContentType.objects.get_for_model(model_class)

        jobs_qs = MediaConversionJob.objects.filter(
            content_type=ct,
            object_id=instance_pk,
        )

        jobs = list(jobs_qs)

        for job in jobs:
            delete_storage_key(
                job.source_path,
                label=f"{model_class.__name__}.job.source",
            )

            delete_job_output(
                job.kind,
                job.output_path,
                label=f"{model_class.__name__}.job.output",
            )

        jobs_qs.delete()

    except Exception:
        logger.exception(
            "❌ Failed deleting MediaConversionJob paths for %s %s",
            model_class.__name__,
            instance_pk,
        )


@receiver(
    post_delete,
    sender=Prayer,
    dispatch_uid="prayer.cleanup.media.delete.v2",
)
def prayer_cleanup_media_on_delete(sender, instance: Prayer, **kwargs):
    def _cleanup():
        _cleanup_conversion_jobs(Prayer, instance.pk)

        _safe_delete_filefield(
            getattr(instance, "image", None),
            "image",
        )
        _safe_delete_filefield(
            getattr(instance, "video", None),
            "video",
        )
        _safe_delete_filefield(
            getattr(instance, "thumbnail", None),
            "thumbnail",
        )

    transaction.on_commit(_cleanup)


@receiver(
    post_delete,
    sender=PrayerResponse,
    dispatch_uid="prayer_response.cleanup.media.delete.v2",
)
def prayer_response_cleanup_media_on_delete(
    sender,
    instance: PrayerResponse,
    **kwargs,
):
    def _cleanup():
        _cleanup_conversion_jobs(
            PrayerResponse,
            instance.pk,
        )

        _safe_delete_filefield(
            getattr(instance, "image", None),
            "response.image",
        )
        _safe_delete_filefield(
            getattr(instance, "video", None),
            "response.video",
        )
        _safe_delete_filefield(
            getattr(instance, "thumbnail", None),
            "response.thumbnail",
        )

    transaction.on_commit(_cleanup)