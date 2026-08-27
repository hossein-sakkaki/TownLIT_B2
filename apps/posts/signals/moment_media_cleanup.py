# apps/posts/signals/moment_media_cleanup.py

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
from apps.posts.models.moment import Moment

logger = logging.getLogger(__name__)


def _safe_delete_filefield(field, label: str):
    try:
        if not field:
            return

        key = clean_storage_key(getattr(field, "name", None))
        storage = getattr(field, "storage", None)

        if not key:
            return

        if label == "video" and key.lower().endswith(".m3u8"):
            delete_video_output(
                key,
                label="moment.video-hls",
                storage=storage,
            )
        else:
            delete_storage_key(
                key,
                label=f"moment.{label}",
                storage=storage,
            )

    except Exception:
        logger.exception(
            "❌ Failed deleting Moment media (%s): %s",
            label,
            getattr(field, "name", None),
        )


def _iter_image_item_keys(instance: Moment):
    seen = set()

    try:
        items = instance.normalized_image_items()
    except Exception:
        items = []

    for item in items:
        if not isinstance(item, dict):
            continue

        values = [item.get("key")]
        variants = item.get("variants")

        if isinstance(variants, dict):
            values.extend(variants.values())

        for value in values:
            if isinstance(value, dict):
                value = value.get("key") or value.get("path")

            key = clean_storage_key(value)

            if not key or key in seen:
                continue

            seen.add(key)
            yield key


def _delete_image_items(instance: Moment):
    for key in _iter_image_item_keys(instance):
        delete_storage_key(
            key,
            label="moment.image-item",
        )


def _delete_media_conversion_paths(instance: Moment):
    try:
        ct = ContentType.objects.get_for_model(Moment)

        jobs_qs = MediaConversionJob.objects.filter(
            content_type=ct,
            object_id=instance.pk,
        )

        jobs = list(jobs_qs)

        for job in jobs:
            delete_storage_key(
                job.source_path,
                label="moment.job.source",
            )

            delete_job_output(
                job.kind,
                job.output_path,
                label="moment.job.output",
            )

        jobs_qs.delete()

    except Exception:
        logger.exception(
            "❌ Failed deleting MediaConversionJob paths for moment %s",
            instance.pk,
        )


@receiver(
    post_delete,
    sender=Moment,
    dispatch_uid="moment.cleanup.media.delete.v4",
)
def moment_cleanup_media_on_delete(sender, instance: Moment, **kwargs):
    def _cleanup():
        _delete_media_conversion_paths(instance)
        _delete_image_items(instance)

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