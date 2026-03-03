# apps/posts/signals/prayer_media_cleanup.py

import logging
import os

from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from django.core.files.storage import default_storage

from apps.media_conversion.models import MediaConversionJob
from apps.posts.models.pray import Prayer, PrayerResponse

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _safe_delete_storage_key(key: str, label: str):
    """Delete a single storage key (best-effort)."""
    try:
        if not key:
            return

        key = str(key).lstrip("/")
        if default_storage.exists(key):
            default_storage.delete(key)
            logger.info("✅ Deleted storage key (%s): %s", label, key)

    except Exception:
        logger.exception("❌ Failed deleting storage key (%s): %s", label, key)


def _safe_delete_prefix(storage, prefix: str, label: str):
    """
    Delete ALL objects under prefix (S3 safe).
    Requires ListBucket + DeleteObject permissions.
    """
    try:
        if not prefix:
            return

        prefix = prefix.lstrip("/")
        if not prefix.endswith("/"):
            prefix += "/"

        bucket = getattr(storage, "bucket", None)
        if not bucket:
            return  # not S3 or no bucket handle

        bucket.objects.filter(Prefix=prefix).delete()
        logger.info("✅ Deleted S3 prefix (%s): %s", label, prefix)

    except Exception:
        logger.exception("❌ Failed deleting S3 prefix (%s): %s", label, prefix)


def _safe_delete_filefield(field, label: str):
    """Delete model FileField + related HLS folder if needed."""
    try:
        if not field:
            return

        name = getattr(field, "name", None)
        if not name:
            return

        storage = getattr(field, "storage", None)
        key = str(name).lstrip("/")

        # 1️⃣ Delete the file itself
        field.delete(save=False)
        logger.info("✅ Prayer media deleted (%s): %s", label, key)

        # 2️⃣ If this is HLS master (.m3u8), delete folder
        if label == "video" and key.lower().endswith(".m3u8") and storage:
            prefix = os.path.dirname(key)
            if prefix:
                _safe_delete_prefix(storage, prefix, "prayer.video-hls")

    except Exception:
        logger.exception(
            "❌ Failed deleting Prayer media (%s): %s",
            label,
            getattr(field, "name", None),
        )


def _cleanup_conversion_jobs(model_class, instance_pk: int):
    """
    Delete MediaConversionJob rows + their stored files.
    """
    try:
        ct = ContentType.objects.get_for_model(model_class)
        jobs_qs = MediaConversionJob.objects.filter(
            content_type=ct,
            object_id=instance_pk,
        )

        jobs = list(jobs_qs)

        for job in jobs:
            # Delete RAW source
            if job.source_path:
                _safe_delete_storage_key(job.source_path, label="job.source")

            # Delete output folder or file
            if job.output_path:
                out = (job.output_path or "").lstrip("/")

                if out:
                    if os.path.splitext(out)[1]:
                        prefix = os.path.dirname(out)
                    else:
                        prefix = out.rstrip("/")

                    if prefix:
                        _safe_delete_prefix(default_storage, prefix, "job.output-prefix")

        jobs_qs.delete()
        logger.info(
            "✅ Deleted MediaConversionJob rows for %s %s",
            model_class.__name__,
            instance_pk,
        )

    except Exception:
        logger.exception(
            "❌ Failed deleting MediaConversionJob paths for %s %s",
            model_class.__name__,
            instance_pk,
        )


# -----------------------------------------------------------------------------
# Prayer Cleanup
# -----------------------------------------------------------------------------
@receiver(
    post_delete,
    sender=Prayer,
    dispatch_uid="prayer.cleanup.media.delete.v1",
)
def prayer_cleanup_media_on_delete(sender, instance: Prayer, **kwargs):
    """
    When Prayer is deleted:
    - Delete MediaConversionJob (raw + output)
    - Delete image / video / thumbnail
    """

    def _cleanup():
        # 0️⃣ Conversion jobs
        _cleanup_conversion_jobs(Prayer, instance.pk)

        # 1️⃣ FileFields
        _safe_delete_filefield(getattr(instance, "image", None), "image")
        _safe_delete_filefield(getattr(instance, "video", None), "video")
        _safe_delete_filefield(getattr(instance, "thumbnail", None), "thumbnail")

    transaction.on_commit(_cleanup)


# -----------------------------------------------------------------------------
# PrayerResponse Cleanup
# -----------------------------------------------------------------------------
@receiver(
    post_delete,
    sender=PrayerResponse,
    dispatch_uid="prayer_response.cleanup.media.delete.v1",
)
def prayer_response_cleanup_media_on_delete(sender, instance: PrayerResponse, **kwargs):
    """
    When PrayerResponse is deleted:
    - Delete MediaConversionJob
    - Delete media files
    """

    def _cleanup():
        # 0️⃣ Conversion jobs
        _cleanup_conversion_jobs(PrayerResponse, instance.pk)

        # 1️⃣ FileFields
        _safe_delete_filefield(getattr(instance, "image", None), "response.image")
        _safe_delete_filefield(getattr(instance, "video", None), "response.video")
        _safe_delete_filefield(getattr(instance, "thumbnail", None), "response.thumbnail")

    transaction.on_commit(_cleanup)