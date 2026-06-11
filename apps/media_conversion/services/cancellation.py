# apps/media_conversion/services/cancellation.py

from __future__ import annotations

import logging
import os
from typing import Iterable

from django.core.files.storage import default_storage
from django.db import transaction

from apps.media_conversion.models import MediaConversionJob, MediaJobStatus

logger = logging.getLogger(__name__)


class MediaConversionCanceled(Exception):
    pass


def raise_if_job_canceled(job: MediaConversionJob | None):
    if not job:
        return

    try:
        job.refresh_from_db(fields=["status"])
    except Exception:
        return

    if job.status == MediaJobStatus.CANCELED:
        raise MediaConversionCanceled("Media conversion was canceled.")


# ---------------------------------------------------------------------
# Storage cleanup helpers
# ---------------------------------------------------------------------
def _clean_key(value) -> str | None:
    if not value:
        return None

    raw = getattr(value, "name", value)

    if not raw:
        return None

    cleaned = str(raw).strip().lstrip("/")
    return cleaned or None


def _delete_storage_key(key: str | None, *, label: str) -> None:
    """
    Delete one storage object safely.
    """
    key = _clean_key(key)

    if not key:
        return

    try:
        if default_storage.exists(key):
            default_storage.delete(key)
            logger.info("🧹 Deleted %s: %s", label, key)
    except Exception:
        logger.exception("Failed deleting %s: %s", label, key)


def _delete_storage_tree(path: str | None, *, label: str) -> None:
    """
    Delete either a single file or a folder-like prefix.

    Useful for HLS outputs:
      posts/videos/.../master.m3u8
      posts/videos/.../segments/...
    """
    path = _clean_key(path)

    if not path:
        return

    # Delete exact object first.
    _delete_storage_key(path, label=label)

    # If path looks like a file, try deleting its parent prefix too.
    prefix = path

    if "." in os.path.basename(path):
        prefix = os.path.dirname(path)

    prefix = prefix.strip("/")

    if not prefix:
        return

    _delete_prefix_recursive(prefix, label=label)


def _delete_prefix_recursive(prefix: str, *, label: str) -> None:
    """
    Best-effort recursive delete using Django storage listdir.
    Works with S3 storages that implement listdir.
    """
    prefix = prefix.strip("/")

    if not prefix:
        return

    try:
        directories, files = default_storage.listdir(prefix)
    except Exception:
        return

    for filename in files:
        _delete_storage_key(
            f"{prefix}/{filename}",
            label=f"{label}.file",
        )

    for directory in directories:
        _delete_prefix_recursive(
            f"{prefix}/{directory}",
            label=f"{label}.dir",
        )


# ---------------------------------------------------------------------
# Target cleanup helpers
# ---------------------------------------------------------------------
def _safe_get_target(job: MediaConversionJob):
    try:
        model_class = job.content_type.model_class()

        if model_class is None:
            return None

        return model_class._base_manager.filter(pk=job.object_id).first()
    except Exception:
        return None


def _target_field_keys(target, field_names: Iterable[str]) -> list[str]:
    keys: list[str] = []

    if target is None:
        return keys

    for field_name in field_names:
        try:
            if not hasattr(target, field_name):
                continue

            value = getattr(target, field_name, None)
            key = _clean_key(value)

            if key:
                keys.append(key)
        except Exception:
            continue

    return keys


def _clear_target_file_fields(target, field_names: Iterable[str]) -> None:
    """
    Clear FileField/ImageField references when we keep the target row.

    This is used for edit/retry-safe cases where deleting the whole object
    would be too destructive.
    """
    if target is None:
        return

    update_fields: list[str] = []

    for field_name in field_names:
        try:
            if not hasattr(target, field_name):
                continue

            value = getattr(target, field_name, None)

            if value and getattr(value, "name", None):
                setattr(target, field_name, None)
                update_fields.append(field_name)
        except Exception:
            continue

    try:
        if hasattr(target, "is_converted") and target.is_converted:
            target.is_converted = False
            update_fields.append("is_converted")
    except Exception:
        pass

    if hasattr(target, "updated_at"):
        update_fields.append("updated_at")

    if not update_fields:
        return

    try:
        target.save(update_fields=list(dict.fromkeys(update_fields)))
    except Exception:
        logger.exception(
            "Failed clearing media fields for canceled target %s[%s]",
            target.__class__.__name__,
            getattr(target, "pk", None),
        )


# ---------------------------------------------------------------------
# Delete-target policy
# ---------------------------------------------------------------------
def _is_posts_model(job: MediaConversionJob, model_name: str) -> bool:
    try:
        return (
            job.content_type.app_label == "posts"
            and job.content_type.model == model_name
        )
    except Exception:
        return False


def _target_is_not_converted(target) -> bool:
    try:
        return getattr(target, "is_converted", False) is not True
    except Exception:
        return True


def _should_delete_unconverted_moment(
    job: MediaConversionJob,
    target,
) -> bool:
    """
    New unconverted Moment video cancel should remove the whole Moment.

    Existing converted Moment edits should not be destroyed.
    """
    if not _is_posts_model(job, "moment"):
        return False

    if job.field_name != "video":
        return False

    return _target_is_not_converted(target)


def _should_delete_unconverted_testimony(
    job: MediaConversionJob,
    target,
) -> bool:
    """
    New unconverted media Testimony cancel should remove the whole Testimony.

    Covers:
    - video testimony: delete video + user thumbnail + db row
    - audio testimony: delete audio + db row

    Written testimony has no conversion job here.
    Existing converted testimony edits should not be destroyed.
    """
    if not _is_posts_model(job, "testimony"):
        return False

    if job.field_name not in {"video", "audio"}:
        return False

    return _target_is_not_converted(target)


def _should_delete_unconverted_prayer(
    job: MediaConversionJob,
    target,
) -> bool:
    """
    New unconverted Prayer media cancel should remove the whole Prayer.

    Covers:
    - prayer video upload
    - prayer image conversion/upload when conversion job exists

    Existing converted Prayer edits should not be destroyed.
    """
    if not _is_posts_model(job, "prayer"):
        return False

    if job.field_name not in {"video", "image", "thumbnail"}:
        return False

    return _target_is_not_converted(target)


def _should_delete_unconverted_prayer_response(
    job: MediaConversionJob,
    target,
) -> bool:
    """
    New unconverted PrayerResponse media cancel should remove only the response.

    The parent Prayer remains.
    Existing converted response edits should not be destroyed.
    """
    if not _is_posts_model(job, "prayerresponse"):
        return False

    if job.field_name not in {"video", "image", "thumbnail"}:
        return False

    return _target_is_not_converted(target)


def _should_delete_unconverted_target(
    job: MediaConversionJob,
    target,
) -> bool:
    """
    Central policy for canceling newly-created conversion targets.
    """
    if target is None:
        return False

    if _should_delete_unconverted_moment(job, target):
        return True

    if _should_delete_unconverted_testimony(job, target):
        return True

    if _should_delete_unconverted_prayer(job, target):
        return True

    if _should_delete_unconverted_prayer_response(job, target):
        return True

    return False


# ---------------------------------------------------------------------
# Public cleanup
# ---------------------------------------------------------------------
def cleanup_canceled_media_job(
    job: MediaConversionJob | None,
    *,
    reason: str = "canceled",
    delete_job: bool = True,
    delete_unconverted_target: bool = True,
) -> None:
    """
    Root cleanup after cancel.

    Removes:
    - original source_path
    - output_path / HLS output folder
    - target video
    - target audio
    - target thumbnail
    - target image
    - unconverted Moment row for canceled video Moment
    - unconverted Testimony row for canceled video/audio Testimony
    - unconverted Prayer row for canceled prayer media
    - unconverted PrayerResponse row for canceled response media
    - MediaConversionJob row if delete_job=True
    """
    if not job:
        return

    try:
        job = (
            MediaConversionJob.objects
            .select_related("content_type")
            .filter(pk=job.pk)
            .first()
        )

        if not job:
            return

        target = _safe_get_target(job)

        # Collect keys before clearing or deleting the target row.
        # IMPORTANT:
        # - audio is included for audio testimony cleanup.
        # - image/thumbnail are included for prayer/response/testimony thumbnails.
        target_keys = _target_field_keys(
            target,
            field_names=[
                job.field_name,
                "video",
                "audio",
                "thumbnail",
                "image",
            ],
        )

        source_path = _clean_key(job.source_path)
        output_path = _clean_key(job.output_path)

        target_model_name = None
        target_pk = None

        if target is not None:
            target_model_name = target.__class__.__name__
            target_pk = getattr(target, "pk", None)

        should_delete_target = (
            delete_unconverted_target
            and _should_delete_unconverted_target(job, target)
        )

        with transaction.atomic():
            if should_delete_target and target is not None:
                target.delete()

                logger.info(
                    "🧹 Deleted unconverted target after cancel: %s[%s] reason=%s",
                    target_model_name,
                    target_pk,
                    reason,
                )

            else:
                _clear_target_file_fields(
                    target,
                    field_names=[
                        job.field_name,
                        "video",
                        "audio",
                        "thumbnail",
                        "image",
                    ],
                )

            if delete_job:
                job_pk = job.pk
                job.delete()

                logger.info(
                    "🧹 Deleted MediaConversionJob after cancel: id=%s reason=%s",
                    job_pk,
                    reason,
                )

        # Storage deletes outside DB transaction.
        _delete_storage_key(
            source_path,
            label="media_job.source",
        )

        _delete_storage_tree(
            output_path,
            label="media_job.output",
        )

        for key in set(target_keys):
            _delete_storage_tree(
                key,
                label="media_job.target_media",
            )

    except Exception:
        logger.exception(
            "cleanup_canceled_media_job failed job=%s reason=%s",
            getattr(job, "pk", None),
            reason,
        )