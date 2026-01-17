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
    Delete ALL objects under prefix on S3 (best-effort).
    Requires S3 permissions: ListBucket + DeleteObject(s)
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
    try:
        if not field:
            return
        name = getattr(field, "name", None)
        if not name:
            return

        storage = getattr(field, "storage", None)
        key = str(name).lstrip("/")

        # 1) delete the file itself
        field.delete(save=False)
        logger.info("✅ Moment media deleted (%s): %s", label, key)

        # 2) if this is HLS master, delete folder too
        if label == "video" and key.lower().endswith(".m3u8") and storage:
            prefix = os.path.dirname(key)
            if prefix:
                _safe_delete_prefix(storage, prefix, "moment.video-hls")

    except Exception:
        logger.exception("❌ Failed deleting Moment media (%s): %s", label, getattr(field, "name", None))


@receiver(post_delete, sender=Moment, dispatch_uid="moment.cleanup.media.delete.v2")
def moment_cleanup_media_on_delete(sender, instance: Moment, **kwargs):
    """
    When a Moment row is deleted, also delete its media files from storage (S3).
    Also delete MediaConversionJob paths (raw + output).
    """

    def _cleanup():
        # ✅ 0) delete RAW/output paths recorded in MediaConversionJob (if any)
        try:
            ct = ContentType.objects.get_for_model(Moment)
            jobs_qs = MediaConversionJob.objects.filter(content_type=ct, object_id=instance.pk)
            jobs = list(jobs_qs)

            for job in jobs:
                if job.source_path:
                    _safe_delete_storage_key(job.source_path, label="job.source")

                if job.output_path:
                    out = (job.output_path or "").lstrip("/")
                    if out:
                        # treat file path vs folder path safely
                        if os.path.splitext(out)[1]:
                            prefix = os.path.dirname(out)
                        else:
                            prefix = out.rstrip("/")
                        if prefix:
                            _safe_delete_prefix(default_storage, prefix, "job.output-prefix")

            jobs_qs.delete()
            logger.info("✅ Deleted MediaConversionJob rows for moment %s", instance.pk)

        except Exception:
            logger.exception("❌ Failed deleting MediaConversionJob paths for moment %s", instance.pk)

        # ✅ 1) delete model-linked fields
        _safe_delete_filefield(getattr(instance, "image", None), "image")
        _safe_delete_filefield(getattr(instance, "video", None), "video")
        _safe_delete_filefield(getattr(instance, "thumbnail", None), "thumbnail")

    transaction.on_commit(_cleanup)
