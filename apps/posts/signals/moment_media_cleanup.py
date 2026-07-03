# apps/posts/signals/moment_media_cleanup.py

import logging
import os

from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from django.core.files.storage import default_storage

from apps.media_conversion.models import MediaConversionJob
from apps.posts.models.moment import Moment

logger = logging.getLogger(__name__)


def _safe_delete_storage_key(key: str, label: str):
    """
    Delete a single storage object by key.
    """
    try:
        if not key:
            return

        key = str(key).lstrip("/")

        if default_storage.exists(key):
            default_storage.delete(key)

    except Exception:
        logger.exception("❌ Failed deleting storage key (%s): %s", label, key)


def _safe_delete_prefix(storage, prefix: str, label: str):
    """
    Delete ALL objects under prefix on S3 (best-effort).

    Requires S3 permissions:
    - ListBucket
    - DeleteObject(s)
    """
    try:
        if not prefix:
            return

        prefix = str(prefix).lstrip("/")
        if not prefix.endswith("/"):
            prefix += "/"

        bucket = getattr(storage, "bucket", None)
        if not bucket:
            return  # Not S3 or no bucket handle.

        bucket.objects.filter(Prefix=prefix).delete()

    except Exception:
        logger.exception("❌ Failed deleting S3 prefix (%s): %s", label, prefix)


def _safe_delete_filefield(field, label: str):
    """
    Delete a model FileField/ImageField and related HLS folder when needed.
    """
    try:
        if not field:
            return

        name = getattr(field, "name", None)
        if not name:
            return

        storage = getattr(field, "storage", None)
        key = str(name).lstrip("/")

        # Delete the file itself.
        field.delete(save=False)

        # If this is HLS master, delete the whole folder too.
        if label == "video" and key.lower().endswith(".m3u8") and storage:
            prefix = os.path.dirname(key)
            if prefix:
                _safe_delete_prefix(storage, prefix, "moment.video-hls")

    except Exception:
        logger.exception(
            "❌ Failed deleting Moment media (%s): %s",
            label,
            getattr(field, "name", None),
        )


def _iter_image_item_keys(instance: Moment):
    """
    Yield unique JSON-backed image keys for multi-photo Moments.
    """
    seen = set()

    try:
        items = instance.normalized_image_items()
    except Exception:
        items = []

    for item in items:
        if not isinstance(item, dict):
            continue

        key = str(item.get("key") or "").strip().lstrip("/")
        if not key:
            continue

        if key in seen:
            continue

        seen.add(key)
        yield key


def _delete_image_items(instance: Moment):
    """
    Delete all JSON-backed photo files.

    The first image may also be stored in Moment.image for backward compatibility.
    Duplicate deletion is safe because _safe_delete_storage_key checks existence.
    """
    for key in _iter_image_item_keys(instance):
        _safe_delete_storage_key(key, label="moment.image-item")


def _delete_media_conversion_paths(instance: Moment):
    """
    Delete raw/output paths recorded in MediaConversionJob.
    """
    try:
        ct = ContentType.objects.get_for_model(Moment)
        jobs_qs = MediaConversionJob.objects.filter(
            content_type=ct,
            object_id=instance.pk,
        )
        jobs = list(jobs_qs)

        for job in jobs:
            if job.source_path:
                _safe_delete_storage_key(job.source_path, label="job.source")

            if job.output_path:
                out = str(job.output_path or "").lstrip("/")
                if not out:
                    continue

                # Treat file path vs folder path safely.
                if os.path.splitext(out)[1]:
                    prefix = os.path.dirname(out)
                else:
                    prefix = out.rstrip("/")

                if prefix:
                    _safe_delete_prefix(
                        default_storage,
                        prefix,
                        "job.output-prefix",
                    )

        jobs_qs.delete()

    except Exception:
        logger.exception(
            "❌ Failed deleting MediaConversionJob paths for moment %s",
            instance.pk,
        )


@receiver(post_delete, sender=Moment, dispatch_uid="moment.cleanup.media.delete.v3")
def moment_cleanup_media_on_delete(sender, instance: Moment, **kwargs):
    """
    When a Moment row is deleted, also delete its media files from storage.

    Supports:
    - legacy single image
    - JSON-backed multi-photo image_items
    - video / HLS output
    - thumbnail
    - MediaConversionJob source/output paths
    """

    def _cleanup():
        # 1) Delete conversion job paths first.
        _delete_media_conversion_paths(instance)

        # 2) Delete JSON-backed multi-photo files.
        _delete_image_items(instance)

        # 3) Delete legacy model-linked fields.
        _safe_delete_filefield(getattr(instance, "image", None), "image")
        _safe_delete_filefield(getattr(instance, "video", None), "video")
        _safe_delete_filefield(getattr(instance, "thumbnail", None), "thumbnail")

    transaction.on_commit(_cleanup)