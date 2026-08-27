# apps/media_conversion/services/storage_cleanup.py

from __future__ import annotations

import logging
import os
import uuid

from django.core.files.storage import default_storage

from apps.media_conversion.services.image_variants import IMAGE_VARIANT_WIDTHS

logger = logging.getLogger(__name__)


def clean_storage_key(value) -> str | None:
    if not value:
        return None

    raw = getattr(value, "name", value)
    key = str(raw or "").strip().lstrip("/")
    return key or None


def _get_storage(storage=None):
    return storage or default_storage


def _is_uuid_segment(value: str) -> bool:
    try:
        uuid.UUID(str(value))
        return True
    except (TypeError, ValueError, AttributeError):
        return False


def delete_storage_key(
    key: str | None,
    *,
    label: str,
    storage=None,
) -> None:
    """Delete exactly one storage object. Never expands to a parent prefix."""
    key = clean_storage_key(key)

    if not key:
        return

    storage = _get_storage(storage)

    try:
        if storage.exists(key):
            storage.delete(key)
            logger.info("🧹 Deleted %s: %s", label, key)
    except Exception:
        logger.exception("Failed deleting %s: %s", label, key)


def _delete_uuid_scoped_tree(
    prefix: str | None,
    *,
    label: str,
    storage=None,
) -> None:
    """
    Recursively delete only a UUID-owned directory.

    Example allowed:
        posts/videos/moment/2026/08/25/<uuid>/

    Example blocked:
        posts/videos/moment/2026/08/25/
    """
    prefix = clean_storage_key(prefix)

    if not prefix:
        return

    prefix = prefix.rstrip("/")
    leaf = os.path.basename(prefix)

    if not _is_uuid_segment(leaf):
        logger.error(
            "Blocked unsafe recursive storage cleanup label=%s prefix=%s",
            label,
            prefix,
        )
        return

    storage = _get_storage(storage)

    def _walk(current_prefix: str) -> None:
        try:
            directories, files = storage.listdir(current_prefix)
        except Exception:
            logger.warning(
                "Could not list storage prefix label=%s prefix=%s",
                label,
                current_prefix,
                exc_info=True,
            )
            return

        for filename in files:
            delete_storage_key(
                f"{current_prefix}/{filename}",
                label=f"{label}.file",
                storage=storage,
            )

        for directory in directories:
            _walk(f"{current_prefix}/{directory}")

    _walk(prefix)


def delete_video_output(
    path: str | None,
    *,
    label: str,
    storage=None,
) -> None:
    """
    Delete a video output safely.

    - master.m3u8: exact delete + UUID-parent subtree only.
    - UUID directory path: UUID subtree.
    - anything else: exact key only.
    """
    path = clean_storage_key(path)

    if not path:
        return

    storage = _get_storage(storage)

    if path.lower().endswith(".m3u8"):
        delete_storage_key(path, label=label, storage=storage)

        prefix = os.path.dirname(path).strip("/")

        if prefix:
            _delete_uuid_scoped_tree(
                prefix,
                label=label,
                storage=storage,
            )
        return

    candidate = path.rstrip("/")

    if _is_uuid_segment(os.path.basename(candidate)):
        _delete_uuid_scoped_tree(
            candidate,
            label=label,
            storage=storage,
        )
        return

    delete_storage_key(path, label=label, storage=storage)


def delete_image_output_bundle(
    path: str | None,
    *,
    label: str,
    storage=None,
) -> None:
    """
    Delete one generated image and its deterministic variants only.

    Variant expansion is allowed only when the generated basename is UUID.
    """
    path = clean_storage_key(path)

    if not path:
        return

    storage = _get_storage(storage)

    delete_storage_key(path, label=label, storage=storage)

    directory = os.path.dirname(path)
    basename = os.path.splitext(os.path.basename(path))[0]

    if not _is_uuid_segment(basename):
        return

    variant_dir = f"{directory}/variants" if directory else "variants"

    for variant_name in IMAGE_VARIANT_WIDTHS:
        delete_storage_key(
            f"{variant_dir}/{basename}_{variant_name}.jpg",
            label=f"{label}.variant",
            storage=storage,
        )


def delete_media_path(
    path: str | None,
    *,
    label: str,
    storage=None,
) -> None:
    """
    Generic safe media cleanup.

    HLS playlists may clean only their UUID-owned directory.
    All other paths are exact-key only.
    """
    path = clean_storage_key(path)

    if not path:
        return

    if path.lower().endswith(".m3u8"):
        delete_video_output(path, label=label, storage=storage)
    else:
        delete_storage_key(path, label=label, storage=storage)


def delete_job_output(
    kind,
    path: str | None,
    *,
    label: str,
    storage=None,
) -> None:
    """Delete one MediaConversionJob output according to its media kind."""
    kind = str(kind or "").strip().lower()

    if kind == "video":
        delete_video_output(path, label=label, storage=storage)
        return

    if kind == "image":
        delete_image_output_bundle(path, label=label, storage=storage)
        return

    delete_storage_key(path, label=label, storage=storage)