# apps/media_conversion/services/cancellation.py

from __future__ import annotations

import logging
import os
import uuid
from typing import Iterable

from django.core.files.storage import default_storage
from django.db import transaction
from django.utils import timezone

from apps.media_conversion.models import (
    MediaConversionJob,
    MediaJobKind,
    MediaJobStatus,
)
from apps.media_conversion.services.image_variants import (
    IMAGE_VARIANT_WIDTHS,
)

logger = logging.getLogger(__name__)


class MediaConversionCanceled(Exception):
    pass


def raise_if_job_canceled(
    job: MediaConversionJob | None,
) -> None:
    if not job:
        return

    try:
        job.refresh_from_db(
            fields=[
                "status",
            ]
        )

    except MediaConversionJob.DoesNotExist:
        raise MediaConversionCanceled(
            "Media conversion job no longer exists."
        )

    except Exception:
        logger.warning(
            "Could not refresh media job cancellation state: %s",
            getattr(
                job,
                "pk",
                None,
            ),
            exc_info=True,
        )
        return

    if job.status == MediaJobStatus.CANCELED:
        raise MediaConversionCanceled(
            "Media conversion was canceled."
        )


# ---------------------------------------------------------------------
# Storage key helpers
# ---------------------------------------------------------------------
def _clean_key(
    value,
) -> str | None:
    if not value:
        return None

    raw = getattr(
        value,
        "name",
        value,
    )

    if not raw:
        return None

    cleaned = str(
        raw
    ).strip().lstrip("/")

    return cleaned or None


def _normalize_protected_keys(
    values: Iterable[str | None] | None,
) -> set[str]:
    result: set[str] = set()

    for value in values or []:
        key = _clean_key(
            value
        )

        if key:
            result.add(
                key
            )

    return result


def _delete_storage_key(
    key: str | None,
    *,
    label: str,
    protected_keys: Iterable[str | None] | None = None,
) -> None:
    """
    Delete exactly one storage object.

    This helper never performs prefix or parent-directory cleanup.
    """

    key = _clean_key(
        key
    )

    if not key:
        return

    protected = _normalize_protected_keys(
        protected_keys
    )

    if key in protected:
        logger.debug(
            "Skipped protected storage key %s: %s",
            label,
            key,
        )
        return

    try:
        if not default_storage.exists(
            key
        ):
            return

        default_storage.delete(
            key
        )

        logger.info(
            "🧹 Deleted %s: %s",
            label,
            key,
        )

    except Exception:
        logger.exception(
            "Failed deleting %s: %s",
            label,
            key,
        )


def _storage_key_exists(
    key: str | None,
) -> bool | None:
    """
    Return None when storage availability cannot be determined.
    """

    key = _clean_key(
        key
    )

    if not key:
        return False

    try:
        return bool(
            default_storage.exists(
                key
            )
        )

    except Exception:
        logger.warning(
            (
                "Could not verify storage key "
                "during cancellation: %s"
            ),
            key,
            exc_info=True,
        )
        return None


# ---------------------------------------------------------------------
# Explicit recursive cleanup
# ---------------------------------------------------------------------
def _is_uuid_segment(
    value: str,
) -> bool:
    value = str(
        value
        or ""
    ).strip()

    if not value:
        return False

    try:
        uuid.UUID(
            value
        )
        return True

    except (
        TypeError,
        ValueError,
        AttributeError,
    ):
        return False


def _is_uuid_scoped_prefix(
    prefix: str | None,
) -> bool:
    """
    Recursive deletion is allowed only for a UUID-owned directory.
    """

    prefix = _clean_key(
        prefix
    )

    if not prefix:
        return False

    leaf = os.path.basename(
        prefix.rstrip("/")
    )

    return _is_uuid_segment(
        leaf
    )


def _delete_prefix_recursive_unchecked(
    prefix: str,
    *,
    label: str,
    protected_keys: Iterable[str | None] | None = None,
) -> None:
    """
    Internal recursive implementation.

    Callers must validate the root prefix before entering this helper.
    """

    prefix = str(
        prefix
        or ""
    ).strip().strip("/")

    if not prefix:
        return

    protected = _normalize_protected_keys(
        protected_keys
    )

    try:
        directories, files = (
            default_storage.listdir(
                prefix
            )
        )

    except Exception:
        logger.warning(
            "Could not list storage prefix %s: %s",
            label,
            prefix,
            exc_info=True,
        )
        return

    for filename in files:
        _delete_storage_key(
            f"{prefix}/{filename}",
            label=f"{label}.file",
            protected_keys=protected,
        )

    for directory in directories:
        _delete_prefix_recursive_unchecked(
            f"{prefix}/{directory}",
            label=f"{label}.dir",
            protected_keys=protected,
        )


def _delete_uuid_scoped_tree(
    prefix: str | None,
    *,
    label: str,
    protected_keys: Iterable[str | None] | None = None,
) -> None:
    """
    Delete one explicitly supplied UUID-scoped directory.

    No parent path is ever inferred here.
    """

    prefix = _clean_key(
        prefix
    )

    if not prefix:
        return

    if not _is_uuid_scoped_prefix(
        prefix
    ):
        logger.error(
            (
                "Blocked unsafe recursive storage cleanup "
                "label=%s prefix=%s"
            ),
            label,
            prefix,
        )
        return

    _delete_prefix_recursive_unchecked(
        prefix,
        label=label,
        protected_keys=protected_keys,
    )


def _delete_hls_output_tree(
    master_path: str | None,
    *,
    label: str,
    protected_keys: Iterable[str | None] | None = None,
) -> None:
    """
    Delete a conversion-owned HLS tree.

    The exact master object may always be deleted.
    Recursive cleanup is allowed only when its direct parent is a
    UUID-scoped conversion directory.
    """

    master_path = _clean_key(
        master_path
    )

    if not master_path:
        return

    _delete_storage_key(
        master_path,
        label=label,
        protected_keys=protected_keys,
    )

    if not master_path.lower().endswith(
        ".m3u8"
    ):
        return

    prefix = os.path.dirname(
        master_path
    ).strip("/")

    if not prefix:
        return

    _delete_uuid_scoped_tree(
        prefix,
        label=label,
        protected_keys=protected_keys,
    )


# ---------------------------------------------------------------------
# Image output cleanup
# ---------------------------------------------------------------------
def _image_variant_keys_for_output(
    output_path: str | None,
) -> set[str]:
    """
    Derive only the known variants belonging to one generated image.

    No directory listing or broad prefix deletion is used.
    """

    output_path = _clean_key(
        output_path
    )

    if not output_path:
        return set()

    directory = os.path.dirname(
        output_path
    ).strip("/")

    filename = os.path.basename(
        output_path
    )

    basename, extension = os.path.splitext(
        filename
    )

    if extension.lower() not in {
        ".jpg",
        ".jpeg",
    }:
        return set()

    # Generated image outputs use UUID identities.
    # If that invariant is not met, fail safely and delete exact key only.
    if not _is_uuid_segment(
        basename
    ):
        logger.warning(
            (
                "Skipped derived image-variant cleanup "
                "for non-UUID output: %s"
            ),
            output_path,
        )
        return set()

    variant_directory = (
        f"{directory}/variants"
        if directory
        else "variants"
    )

    return {
        (
            f"{variant_directory}/"
            f"{basename}_{variant_name}.jpg"
        )
        for variant_name in IMAGE_VARIANT_WIDTHS
    }


def _delete_image_output_bundle(
    output_path: str | None,
    *,
    label: str,
    protected_keys: Iterable[str | None] | None = None,
) -> None:
    """
    Delete one generated image and only its deterministic variants.
    """

    output_path = _clean_key(
        output_path
    )

    if not output_path:
        return

    _delete_storage_key(
        output_path,
        label=label,
        protected_keys=protected_keys,
    )

    for variant_key in _image_variant_keys_for_output(
        output_path
    ):
        _delete_storage_key(
            variant_key,
            label=f"{label}.variant",
            protected_keys=protected_keys,
        )


# ---------------------------------------------------------------------
# Media payload key extraction
# ---------------------------------------------------------------------
def _collect_payload_storage_keys(
    value,
) -> set[str]:
    """
    Collect explicit `key` values from media metadata.

    This never derives a parent directory.
    """

    result: set[str] = set()

    if isinstance(
        value,
        dict,
    ):
        key = _clean_key(
            value.get(
                "key"
            )
        )

        if key:
            result.add(
                key
            )

        for child in value.values():
            result.update(
                _collect_payload_storage_keys(
                    child
                )
            )

    elif isinstance(
        value,
        list,
    ):
        for child in value:
            result.update(
                _collect_payload_storage_keys(
                    child
                )
            )

    return result


# ---------------------------------------------------------------------
# Job ownership helpers
# ---------------------------------------------------------------------
def _normalized_task_id(
    value,
) -> str:
    return str(
        value
        or ""
    ).strip()


def _normalized_attempt(
    value,
) -> int:
    try:
        return int(
            value
            or 0
        )

    except (
        TypeError,
        ValueError,
    ):
        return 0


def _same_job_generation(
    *,
    snapshot: MediaConversionJob,
    authoritative: MediaConversionJob,
) -> bool:
    """
    MediaConversionJob rows may be reused by retries.

    Cleanup is valid only for the same task generation.
    """

    return (
        _normalized_task_id(
            snapshot.task_id
        )
        == _normalized_task_id(
            authoritative.task_id
        )
        and _normalized_attempt(
            snapshot.attempt
        )
        == _normalized_attempt(
            authoritative.attempt
        )
    )


def _job_hls_prefix(
    job: MediaConversionJob,
) -> str | None:
    if job.kind != MediaJobKind.VIDEO:
        return None

    output_path = _clean_key(
        job.output_path
    )

    if (
        not output_path
        or not output_path.lower().endswith(
            ".m3u8"
        )
    ):
        return None

    prefix = os.path.dirname(
        output_path
    ).strip("/")

    if not _is_uuid_scoped_prefix(
        prefix
    ):
        return None

    return prefix


def _key_belongs_to_job(
    job: MediaConversionJob,
    key: str | None,
) -> bool:
    """
    Return True only when a storage key can be tied to this job.
    """

    key = _clean_key(
        key
    )

    if not key:
        return False

    source_path = _clean_key(
        job.source_path
    )

    output_path = _clean_key(
        job.output_path
    )

    if key in {
        source_path,
        output_path,
    }:
        return True

    if job.kind == MediaJobKind.IMAGE:
        if key in _image_variant_keys_for_output(
            output_path
        ):
            return True

    hls_prefix = _job_hls_prefix(
        job
    )

    if (
        hls_prefix
        and key.startswith(
            f"{hls_prefix}/"
        )
    ):
        return True

    return False


# ---------------------------------------------------------------------
# Target helpers
# ---------------------------------------------------------------------
def _safe_get_target(
    job: MediaConversionJob,
):
    try:
        model_class = (
            job.content_type
            .model_class()
        )

        if model_class is None:
            return None

        return (
            model_class
            ._base_manager
            .filter(
                pk=job.object_id
            )
            .first()
        )

    except Exception:
        logger.warning(
            "Could not resolve media job target job=%s",
            getattr(
                job,
                "pk",
                None,
            ),
            exc_info=True,
        )
        return None


def _target_field_key(
    target,
    field_name: str,
) -> str | None:
    if target is None:
        return None

    try:
        if not hasattr(
            target,
            field_name,
        ):
            return None

        return _clean_key(
            getattr(
                target,
                field_name,
                None,
            )
        )

    except Exception:
        return None


def _moment_image_item_payload(
    target,
    field_name: str,
) -> dict | None:
    if target is None:
        return None

    if not field_name.startswith(
        "image_items:"
    ):
        return None

    image_item_id = (
        field_name
        .split(
            ":",
            1,
        )[1]
        .strip()
    )

    if not image_item_id:
        return None

    items = getattr(
        target,
        "image_items",
        None,
    )

    if not isinstance(
        items,
        list,
    ):
        return None

    for item in items:
        if not isinstance(
            item,
            dict,
        ):
            continue

        current_id = str(
            item.get(
                "id"
            )
            or ""
        ).strip()

        if current_id == image_item_id:
            return item

    return None


def _current_job_target_key(
    job: MediaConversionJob,
    target,
) -> str | None:
    field_name = str(
        job.field_name
        or ""
    ).strip()

    image_item = _moment_image_item_payload(
        target,
        field_name,
    )

    if image_item is not None:
        return _clean_key(
            image_item.get(
                "key"
            )
        )

    return _target_field_key(
        target,
        field_name,
    )


def _target_cleanup_keys(
    job: MediaConversionJob,
    target,
    *,
    whole_target: bool,
) -> set[str]:
    """
    Resolve explicit storage keys that are safe to clean.

    Whole-target deletion may clean all media referenced by that target.
    Otherwise only media proven to belong to this job is returned.
    """

    if target is None:
        return set()

    result: set[str] = set()

    if whole_target:
        for field_name in {
            str(
                job.field_name
                or ""
            ).strip(),
            "video",
            "audio",
            "thumbnail",
            "image",
        }:
            if not field_name:
                continue

            key = _target_field_key(
                target,
                field_name,
            )

            if key:
                result.add(
                    key
                )

        media_assets = getattr(
            target,
            "media_assets",
            None,
        )

        result.update(
            _collect_payload_storage_keys(
                media_assets
            )
        )

        image_items = getattr(
            target,
            "image_items",
            None,
        )

        result.update(
            _collect_payload_storage_keys(
                image_items
            )
        )

        return result

    field_name = str(
        job.field_name
        or ""
    ).strip()

    current_key = _current_job_target_key(
        job,
        target,
    )

    if (
        current_key
        and _key_belongs_to_job(
            job,
            current_key,
        )
    ):
        result.add(
            current_key
        )

    media_assets = getattr(
        target,
        "media_assets",
        None,
    )

    if isinstance(
        media_assets,
        dict,
    ):
        field_payload = media_assets.get(
            field_name
        )

        for key in _collect_payload_storage_keys(
            field_payload
        ):
            if _key_belongs_to_job(
                job,
                key,
            ):
                result.add(
                    key
                )

    image_item = _moment_image_item_payload(
        target,
        field_name,
    )

    if image_item is not None:
        for key in _collect_payload_storage_keys(
            image_item
        ):
            if _key_belongs_to_job(
                job,
                key,
            ):
                result.add(
                    key
                )

    return result


def _clear_target_job_field(
    target,
    job: MediaConversionJob,
) -> None:
    """
    Clear only a field still owned by this job generation.

    A newer target assignment is never cleared.
    """

    if target is None:
        return

    field_name = str(
        job.field_name
        or ""
    ).strip()

    if not field_name:
        return

    current_key = _current_job_target_key(
        job,
        target,
    )

    if (
        current_key
        and not _key_belongs_to_job(
            job,
            current_key,
        )
    ):
        logger.info(
            (
                "Skipped clearing superseded target field "
                "job=%s target=%s[%s] field=%s current=%s"
            ),
            job.pk,
            target.__class__.__name__,
            getattr(
                target,
                "pk",
                None,
            ),
            field_name,
            current_key,
        )
        return

    updates: dict = {}

    # Normal FileField/ImageField.
    if hasattr(
        target,
        field_name,
    ):
        try:
            value = getattr(
                target,
                field_name,
                None,
            )

            if (
                value
                and getattr(
                    value,
                    "name",
                    None,
                )
            ):
                updates[
                    field_name
                ] = None

        except Exception:
            pass

    # Virtual fields such as image_items:<id> do not have a direct DB
    # column here. Their JSON identity remains intact, but the target is
    # no longer globally considered converted.
    try:
        if (
            hasattr(
                target,
                "is_converted",
            )
            and getattr(
                target,
                "is_converted",
                False,
            )
        ):
            updates[
                "is_converted"
            ] = False

    except Exception:
        pass

    if not updates:
        return

    if hasattr(
        target,
        "updated_at",
    ):
        updates[
            "updated_at"
        ] = timezone.now()

    try:
        type(
            target
        )._base_manager.filter(
            pk=target.pk
        ).update(
            **updates
        )

    except Exception:
        logger.exception(
            (
                "Failed clearing canceled media field "
                "for target %s[%s] job=%s"
            ),
            target.__class__.__name__,
            getattr(
                target,
                "pk",
                None,
            ),
            job.pk,
        )


# ---------------------------------------------------------------------
# Creative Editor cancellation policy
# ---------------------------------------------------------------------
def _is_creative_composition_media_job(
    job: MediaConversionJob,
) -> bool:
    try:
        return (
            job.content_type.app_label
            == "creative_editor"
            and job.content_type.model
            == "creativecompositionmedia"
        )

    except Exception:
        return False


def _creative_conversion_flag_field(
    field_name: str,
) -> str | None:
    if field_name == "source_image":
        return "source_image_is_converted"

    if field_name == "source_video":
        return "source_video_is_converted"

    return None


def _delete_creative_output(
    job: MediaConversionJob,
    key: str | None,
    *,
    source_path: str | None,
) -> None:
    key = _clean_key(
        key
    )

    if (
        not key
        or key == source_path
    ):
        return

    protected_keys = {
        source_path
    } if source_path else set()

    if (
        job.kind == MediaJobKind.VIDEO
        and key.lower().endswith(
            ".m3u8"
        )
    ):
        _delete_hls_output_tree(
            key,
            label="creative_media.output",
            protected_keys=protected_keys,
        )
        return

    if job.kind == MediaJobKind.IMAGE:
        _delete_image_output_bundle(
            key,
            label="creative_media.output",
            protected_keys=protected_keys,
        )
        return

    _delete_storage_key(
        key,
        label="creative_media.output",
        protected_keys=protected_keys,
    )


def _cleanup_canceled_creative_media_job(
    job: MediaConversionJob,
    target,
    *,
    reason: str,
) -> None:
    """
    Preserve Creative Editor source identity and retryability.
    """

    source_path = _clean_key(
        job.source_path
    )

    output_path = _clean_key(
        job.output_path
    )

    field_name = str(
        job.field_name
        or ""
    ).strip()

    if field_name not in {
        "source_image",
        "source_video",
    }:
        logger.warning(
            (
                "Creative media cancel received "
                "unsupported field job=%s field=%s"
            ),
            job.pk,
            field_name,
        )
        return

    current_field_key: str | None = None
    source_exists: bool | None = None
    asset_keys: set[str] = set()

    if target is not None:
        current_field_key = _target_field_key(
            target,
            field_name,
        )

        assets = dict(
            getattr(
                target,
                "media_assets",
                None,
            )
            or {}
        )

        asset_payload = assets.get(
            field_name
        )

        asset_keys = _collect_payload_storage_keys(
            asset_payload
        )

        source_exists = _storage_key_exists(
            source_path
        )

        updates: dict = {}

        if (
            source_path
            and source_exists is True
            and current_field_key != source_path
        ):
            updates[
                field_name
            ] = source_path

        elif (
            source_exists is False
            and current_field_key
            and current_field_key != source_path
            and _key_belongs_to_job(
                job,
                current_field_key,
            )
        ):
            updates[
                field_name
            ] = None

        flag_field = _creative_conversion_flag_field(
            field_name
        )

        if (
            flag_field
            and hasattr(
                target,
                flag_field,
            )
        ):
            updates[
                flag_field
            ] = False

        if field_name in assets:
            assets.pop(
                field_name,
                None,
            )

            updates[
                "media_assets"
            ] = assets

        if (
            updates
            and hasattr(
                target,
                "updated_at",
            )
        ):
            updates[
                "updated_at"
            ] = timezone.now()

        if updates:
            try:
                type(
                    target
                )._base_manager.filter(
                    pk=target.pk
                ).update(
                    **updates
                )

            except Exception:
                logger.exception(
                    (
                        "Failed restoring canceled "
                        "CreativeCompositionMedia[%s]"
                    ),
                    getattr(
                        target,
                        "pk",
                        None,
                    ),
                )

    cleanup_candidates: set[str] = set()

    if output_path:
        cleanup_candidates.add(
            output_path
        )

    if (
        current_field_key
        and _key_belongs_to_job(
            job,
            current_field_key,
        )
    ):
        cleanup_candidates.add(
            current_field_key
        )

    for key in asset_keys:
        if _key_belongs_to_job(
            job,
            key,
        ):
            cleanup_candidates.add(
                key
            )

    for key in cleanup_candidates:
        _delete_creative_output(
            job,
            key,
            source_path=source_path,
        )

    logger.info(
        (
            "🧹 Preserved canceled CreativeCompositionMedia "
            "job=%s target=%s source=%s reason=%s"
        ),
        job.pk,
        getattr(
            target,
            "pk",
            None,
        ),
        source_path,
        reason,
    )


# ---------------------------------------------------------------------
# Delete-target policy
# ---------------------------------------------------------------------
def _is_posts_model(
    job: MediaConversionJob,
    model_name: str,
) -> bool:
    try:
        return (
            job.content_type.app_label
            == "posts"
            and job.content_type.model
            == model_name
        )

    except Exception:
        return False


def _target_is_not_converted(
    target,
) -> bool:
    try:
        return (
            getattr(
                target,
                "is_converted",
                False,
            )
            is not True
        )

    except Exception:
        return True


def _should_delete_unconverted_moment(
    job: MediaConversionJob,
    target,
) -> bool:
    return (
        _is_posts_model(
            job,
            "moment",
        )
        and job.field_name == "video"
        and _target_is_not_converted(
            target
        )
    )


def _should_delete_unconverted_testimony(
    job: MediaConversionJob,
    target,
) -> bool:
    return (
        _is_posts_model(
            job,
            "testimony",
        )
        and job.field_name in {
            "video",
            "audio",
        }
        and _target_is_not_converted(
            target
        )
    )


def _should_delete_unconverted_prayer(
    job: MediaConversionJob,
    target,
) -> bool:
    return (
        _is_posts_model(
            job,
            "prayer",
        )
        and job.field_name in {
            "video",
            "image",
            "thumbnail",
        }
        and _target_is_not_converted(
            target
        )
    )


def _should_delete_unconverted_prayer_response(
    job: MediaConversionJob,
    target,
) -> bool:
    return (
        _is_posts_model(
            job,
            "prayerresponse",
        )
        and job.field_name in {
            "video",
            "image",
            "thumbnail",
        }
        and _target_is_not_converted(
            target
        )
    )


def _should_delete_unconverted_target(
    job: MediaConversionJob,
    target,
) -> bool:
    if target is None:
        return False

    return any(
        (
            _should_delete_unconverted_moment(
                job,
                target,
            ),
            _should_delete_unconverted_testimony(
                job,
                target,
            ),
            _should_delete_unconverted_prayer(
                job,
                target,
            ),
            _should_delete_unconverted_prayer_response(
                job,
                target,
            ),
        )
    )


# ---------------------------------------------------------------------
# Storage execution
# ---------------------------------------------------------------------
def _delete_job_output(
    *,
    kind: str,
    output_path: str | None,
) -> None:
    output_path = _clean_key(
        output_path
    )

    if not output_path:
        return

    if kind == MediaJobKind.VIDEO:
        _delete_hls_output_tree(
            output_path,
            label="media_job.output",
        )
        return

    if kind == MediaJobKind.IMAGE:
        _delete_image_output_bundle(
            output_path,
            label="media_job.output",
        )
        return

    _delete_storage_key(
        output_path,
        label="media_job.output",
    )


def _delete_target_storage_key(
    key: str | None,
) -> None:
    """
    Delete one explicit target-owned artifact.

    HLS recursion is allowed only through the guarded UUID-scoped helper.
    Everything else is exact-key deletion.
    """

    key = _clean_key(
        key
    )

    if not key:
        return

    if key.lower().endswith(
        ".m3u8"
    ):
        _delete_hls_output_tree(
            key,
            label="media_job.target_media",
        )
        return

    _delete_storage_key(
        key,
        label="media_job.target_media",
    )


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
    Root cleanup after cancellation.

    Safety invariants:
    - authoritative state must still be CANCELED;
    - task id and attempt must still match the canceled generation;
    - no file key may be expanded to its parent directory;
    - recursive deletion is limited to UUID-scoped HLS directories;
    - a surviving target may only be changed when its current media still
      belongs to this job;
    - storage cleanup runs only after DB state commits.
    """

    if not job:
        return

    snapshot_pk = getattr(
        job,
        "pk",
        None,
    )

    if not snapshot_pk:
        return

    source_path: str | None = None
    output_path: str | None = None
    target_keys: set[str] = set()
    job_kind: str | None = None

    try:
        with transaction.atomic():
            authoritative_job = (
                MediaConversionJob.objects
                .select_for_update()
                .select_related(
                    "content_type"
                )
                .filter(
                    pk=snapshot_pk
                )
                .first()
            )

            if authoritative_job is None:
                return

            if (
                authoritative_job.status
                != MediaJobStatus.CANCELED
            ):
                logger.info(
                    (
                        "Skipped cancellation cleanup "
                        "for non-canceled job=%s "
                        "status=%s reason=%s"
                    ),
                    snapshot_pk,
                    authoritative_job.status,
                    reason,
                )
                return

            if not _same_job_generation(
                snapshot=job,
                authoritative=authoritative_job,
            ):
                logger.info(
                    (
                        "Skipped stale cancellation cleanup "
                        "job=%s expected_task=%s current_task=%s "
                        "expected_attempt=%s current_attempt=%s "
                        "reason=%s"
                    ),
                    snapshot_pk,
                    _normalized_task_id(
                        job.task_id
                    ),
                    _normalized_task_id(
                        authoritative_job.task_id
                    ),
                    _normalized_attempt(
                        job.attempt
                    ),
                    _normalized_attempt(
                        authoritative_job.attempt
                    ),
                    reason,
                )
                return

            job = authoritative_job

            target = _safe_get_target(
                job
            )

            # Creative Editor intentionally preserves its media row,
            # source upload and canceled job.
            if _is_creative_composition_media_job(
                job
            ):
                _cleanup_canceled_creative_media_job(
                    job,
                    target,
                    reason=reason,
                )
                return

            source_path = _clean_key(
                job.source_path
            )

            output_path = _clean_key(
                job.output_path
            )

            job_kind = job.kind

            should_delete_target = (
                delete_unconverted_target
                and _should_delete_unconverted_target(
                    job,
                    target,
                )
            )

            target_keys = _target_cleanup_keys(
                job,
                target,
                whole_target=should_delete_target,
            )

            if (
                should_delete_target
                and target is not None
            ):
                target_model_name = (
                    target.__class__.__name__
                )

                target_pk = getattr(
                    target,
                    "pk",
                    None,
                )

                target.delete()

                logger.info(
                    (
                        "🧹 Deleted unconverted target "
                        "after cancel: %s[%s] reason=%s"
                    ),
                    target_model_name,
                    target_pk,
                    reason,
                )

            else:
                _clear_target_job_field(
                    target,
                    job,
                )

            if delete_job:
                job_pk = job.pk

                job.delete()

                logger.info(
                    (
                        "🧹 Deleted MediaConversionJob "
                        "after cancel: id=%s reason=%s"
                    ),
                    job_pk,
                    reason,
                )

        # Storage I/O is intentionally outside the DB transaction.
        _delete_storage_key(
            source_path,
            label="media_job.source",
        )

        if job_kind:
            _delete_job_output(
                kind=job_kind,
                output_path=output_path,
            )

        for key in target_keys:
            _delete_target_storage_key(
                key
            )

    except Exception:
        logger.exception(
            (
                "cleanup_canceled_media_job failed "
                "job=%s reason=%s"
            ),
            snapshot_pk,
            reason,
        )