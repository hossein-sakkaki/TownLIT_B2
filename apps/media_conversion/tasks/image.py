# apps/media_conversion/tasks/image.py

import logging
import os

from celery import shared_task
from django.core.files.storage import default_storage
from django.db import (
    close_old_connections,
    transaction,
)
from django.utils import timezone

from apps.media_conversion.models import MediaJobStatus

from utils.common.utils import FileUpload
from utils.common.image_utils import convert_image_to_jpg
from apps.media_conversion.services.media_metadata import image_metadata_from_storage
from apps.media_conversion.services.image_variants import build_image_variants
from apps.media_conversion.services.media_manifest import (
    build_asset_payload,
    update_instance_media_asset,
)
from .base import (
    MediaConversionCanceled,
    MediaConversionSuperseded,
    bind_converted_file,
    get_instance,
    get_job_by_current_task,
    job_update,
    raise_if_job_canceled,
    raise_if_source_superseded,
)

logger = logging.getLogger(__name__)


def _safe_delete_storage_key(
    key: str | None,
    *,
    label: str = "source",
):
    """
    Best-effort delete for original uploaded media.
    """
    try:
        if not key:
            return

        key = str(key).lstrip("/")

        if default_storage.exists(key):
            default_storage.delete(key)
            logger.info(
                "🧹 Deleted original %s file: %s",
                label,
                key,
            )

    except Exception:
        logger.exception(
            "❌ Failed deleting original %s file: %s",
            label,
            key,
        )


class MomentImageItemSuperseded(Exception):
    """
    Raised when a Moment image-item task no longer matches current JSON state.
    """

    def __init__(
        self,
        *,
        image_item_id: str,
        expected_source_path: str,
        current_source_path: str,
        reason: str,
    ):
        self.image_item_id = image_item_id
        self.expected_source_path = expected_source_path
        self.current_source_path = current_source_path
        self.reason = reason

        super().__init__(
            (
                "Moment image item conversion was superseded: "
                f"item_id={image_item_id!r} "
                f"expected={expected_source_path!r} "
                f"current={current_source_path!r} "
                f"reason={reason}"
            )
        )


def _normalize_moment_storage_key(
    value,
) -> str:
    """
    Normalize one Moment image-item storage key.
    """

    return str(
        value
        or ""
    ).strip().lstrip("/")


def _find_moment_image_item(
    instance,
    image_item_id: str,
) -> dict | None:
    """
    Find one current JSON-backed Moment image item.
    """

    items = (
        getattr(
            instance,
            "image_items",
            None,
        )
        or []
    )

    if not isinstance(items, list):
        return None

    for item in items:
        if not isinstance(item, dict):
            continue

        current_id = str(
            item.get("id")
            or ""
        ).strip()

        if current_id == image_item_id:
            return item

    return None


def _raise_if_moment_image_item_superseded(
    *,
    instance,
    image_item_id: str,
    expected_source_path: str,
) -> dict:
    """
    Ensure the current item still references the source queued by this task.
    """

    expected_key = (
        _normalize_moment_storage_key(
            expected_source_path
        )
    )

    item = _find_moment_image_item(
        instance,
        image_item_id,
    )

    if item is None:
        raise MomentImageItemSuperseded(
            image_item_id=image_item_id,
            expected_source_path=expected_key,
            current_source_path="",
            reason="image_item_removed",
        )

    current_key = (
        _normalize_moment_storage_key(
            item.get("key")
        )
    )

    if current_key != expected_key:
        raise MomentImageItemSuperseded(
            image_item_id=image_item_id,
            expected_source_path=expected_key,
            current_source_path=current_key,
            reason="source_replaced",
        )

    return item


def _moment_image_item_requires_conversion(
    item: dict,
) -> bool:
    """
    Mirror Moment._image_item_requires_conversion without relying
    on a potentially stale model instance.
    """

    key = str(
        item.get("key")
        or ""
    ).strip().lower()

    if not key:
        return True

    is_web_safe = key.endswith(
        (
            ".jpg",
            ".jpeg",
            ".png",
        )
    )

    has_dimensions = bool(
        item.get("width")
        and item.get("height")
        and item.get("aspect_ratio")
    )

    variants = item.get("variants")

    has_variants = (
        isinstance(variants, dict)
        and bool(
            variants.get("thumb")
            and variants.get("grid")
            and variants.get("feed")
        )
    )

    return (
        not is_web_safe
        or not has_dimensions
        or not has_variants
    )
    
@shared_task(queue="video")
def convert_image_to_jpg_task(
    model_name: str,
    app_label: str,
    instance_id: int,
    field_name: str,
    source_path: str,
    fileupload: dict,
):
    """
    Celery task:
    - image -> JPG
    - bind result to model
    - cancel-aware
    - stale-source-aware
    """

    close_old_connections()
    job = get_job_by_current_task()

    normalized_source_path = str(
        source_path or ""
    ).strip().lstrip("/")

    job_update(
        job,
        status=MediaJobStatus.PROCESSING,
        progress=1,
        message="Preparing image conversion",
        source_path=normalized_source_path,
        started=True,
    )

    try:
        raise_if_job_canceled(job)

        logger.info(
            "🖼️ Image conversion task started: %s[%s].%s source=%s",
            model_name,
            instance_id,
            field_name,
            normalized_source_path,
        )

        try:
            instance = get_instance(
                app_label,
                model_name,
                instance_id,
            )
        except Exception:
            job_update(
                job,
                status=MediaJobStatus.CANCELED,
                progress=100,
                message="Canceled: target object no longer exists",
                error="",
                finished=True,
            )

            logger.warning(
                "Target %s[%s] missing; canceling image task",
                model_name,
                instance_id,
            )
            return

        raise_if_job_canceled(job)

        # Guard 1:
        # Do not open or convert a source that is no longer attached
        # to the current model field.
        raise_if_source_superseded(
            instance=instance,
            model_name=model_name,
            instance_id=instance_id,
            field_name=field_name,
            expected_source_path=normalized_source_path,
        )

        upload = FileUpload(**fileupload)

        job_update(
            job,
            progress=10,
            message="Converting image to JPG",
        )

        relative_output_path = convert_image_to_jpg(
            normalized_source_path,
            instance,
            upload,
        )

        raise_if_job_canceled(job)

        # Guard 2:
        # The source may have been replaced while Pillow was converting it.
        refreshed_before_finalize = get_instance(
            app_label,
            model_name,
            instance_id,
        )

        raise_if_source_superseded(
            instance=refreshed_before_finalize,
            model_name=model_name,
            instance_id=instance_id,
            field_name=field_name,
            expected_source_path=normalized_source_path,
        )

        image_meta = image_metadata_from_storage(
            relative_output_path
        )

        variant_dir = os.path.dirname(
            relative_output_path
        )

        basename = os.path.splitext(
            os.path.basename(relative_output_path)
        )[0]

        variants = build_image_variants(
            source_key=relative_output_path,
            base_output_dir=f"{variant_dir}/variants",
            basename=basename,
        )

        image_asset = build_asset_payload(
            key=relative_output_path,
            metadata=image_meta,
            variants=variants,
            extra={
                "mime_type": "image/jpeg",
            },
        )

        raise_if_job_canceled(job)

        job_update(
            job,
            progress=90,
            message="Finalizing output",
        )

        mark_model_converted = not (
            model_name == "Testimony"
            and field_name in {
                "thumbnail",
                "audio_artwork",
            }
        )

        # Guard 3:
        # bind_converted_file performs an atomic row-locked comparison.
        # A stale task can never overwrite a newer source assignment.
        bind_converted_file(
            model_name=model_name,
            app_label=app_label,
            instance_id=instance_id,
            field_name=field_name,
            relative_path=relative_output_path,
            mark_converted=mark_model_converted,
            expected_source_path=normalized_source_path,
        )

        refreshed_instance = get_instance(
            app_label,
            model_name,
            instance_id,
        )

        update_instance_media_asset(
            instance=refreshed_instance,
            field_name=field_name,
            payload=image_asset,
        )

        raise_if_job_canceled(job)

        job_update(
            job,
            status=MediaJobStatus.DONE,
            progress=100,
            message="Conversion completed",
            error="",
            output_path=relative_output_path,
            finished=True,
        )

        logger.info(
            "✅ Image conversion completed: %s[%s].%s -> %s",
            model_name,
            instance_id,
            field_name,
            relative_output_path,
        )

    except MediaConversionSuperseded as exc:
        job_update(
            job,
            status=MediaJobStatus.CANCELED,
            progress=100,
            message="Canceled: source was replaced",
            error="",
            finished=True,
        )

        logger.warning(
            (
                "Image conversion skipped because source changed: "
                "%s[%s].%s expected=%s current=%s"
            ),
            model_name,
            instance_id,
            field_name,
            exc.expected_source_path,
            exc.current_source_path,
        )

        return

    except MediaConversionCanceled:
        job_update(
            job,
            status=MediaJobStatus.CANCELED,
            progress=100,
            message="Canceled",
            error="",
            finished=True,
        )

        logger.info(
            "🚫 Image conversion canceled: %s[%s]",
            model_name,
            instance_id,
        )

        return

    except Exception as exc:
        job_update(
            job,
            status=MediaJobStatus.FAILED,
            progress=100,
            message="Conversion failed",
            error=str(exc),
            finished=True,
        )

        logger.exception(
            "❌ Image conversion failed for %s[%s]",
            model_name,
            instance_id,
        )

        raise

    finally:
        close_old_connections()


@shared_task(queue="video")
def convert_moment_image_item_to_jpg_task(
    model_name: str,
    app_label: str,
    instance_id: int,
    field_name: str,
    source_path: str,
    fileupload: dict,
):
    """
    Celery task:
    - Moment image_items:<id> image -> JPG
    - update matching JSON image item
    - mark Moment converted only when all items are complete
    - cancel-aware
    - stale-source-aware
    - concurrent-update-safe
    """

    close_old_connections()
    job = get_job_by_current_task()

    normalized_source_path = (
        _normalize_moment_storage_key(
            source_path
        )
    )

    job_update(
        job,
        status=MediaJobStatus.PROCESSING,
        progress=1,
        message="Preparing Moment photo conversion",
        source_path=normalized_source_path,
        started=True,
    )

    try:
        raise_if_job_canceled(job)

        logger.info(
            (
                "🖼️ Moment image item conversion started: "
                "%s[%s] %s source=%s"
            ),
            model_name,
            instance_id,
            field_name,
            normalized_source_path,
        )

        try:
            instance = get_instance(
                app_label,
                model_name,
                instance_id,
            )
        except Exception:
            job_update(
                job,
                status=MediaJobStatus.CANCELED,
                progress=100,
                message=(
                    "Canceled: target object "
                    "no longer exists"
                ),
                error="",
                finished=True,
            )

            logger.warning(
                (
                    "Target %s[%s] missing; "
                    "canceling Moment image item task"
                ),
                model_name,
                instance_id,
            )

            return

        raise_if_job_canceled(job)

        if not field_name.startswith(
            "image_items:"
        ):
            raise ValueError(
                (
                    "Invalid Moment image item "
                    f"field_name: {field_name}"
                )
            )

        image_item_id = (
            field_name
            .split(":", 1)[1]
            .strip()
        )

        if not image_item_id:
            raise ValueError(
                "Missing image item id."
            )

        # Guard before opening S3.
        _raise_if_moment_image_item_superseded(
            instance=instance,
            image_item_id=image_item_id,
            expected_source_path=normalized_source_path,
        )

        upload = FileUpload(
            **fileupload
        )

        job_update(
            job,
            progress=10,
            message="Converting Moment photo to JPG",
        )

        relative_output_path = (
            convert_image_to_jpg(
                normalized_source_path,
                instance,
                upload,
            )
        )

        raise_if_job_canceled(job)

        refreshed_before_finalize = get_instance(
            app_label,
            model_name,
            instance_id,
        )

        # Source may have changed while Pillow was processing.
        _raise_if_moment_image_item_superseded(
            instance=refreshed_before_finalize,
            image_item_id=image_item_id,
            expected_source_path=normalized_source_path,
        )

        image_meta = (
            image_metadata_from_storage(
                relative_output_path
            )
        )

        variant_dir = os.path.dirname(
            relative_output_path
        )

        basename = os.path.splitext(
            os.path.basename(
                relative_output_path
            )
        )[0]

        variants = build_image_variants(
            source_key=relative_output_path,
            base_output_dir=(
                f"{variant_dir}/variants"
            ),
            basename=basename,
        )

        raise_if_job_canceled(job)

        job_update(
            job,
            progress=80,
            message="Updating Moment image item",
        )

        try:
            output_size = default_storage.size(
                relative_output_path
            )
        except Exception:
            output_size = 0

        model_class = type(
            refreshed_before_finalize
        )

        # Final read-modify-write is row-locked so parallel photo
        # conversions cannot overwrite each other's JSON updates.
        with transaction.atomic():
            locked_instance = (
                model_class._base_manager
                .select_for_update()
                .get(pk=instance_id)
            )

            _raise_if_moment_image_item_superseded(
                instance=locked_instance,
                image_item_id=image_item_id,
                expected_source_path=normalized_source_path,
            )

            current_items = (
                getattr(
                    locked_instance,
                    "image_items",
                    None,
                )
                or []
            )

            if not isinstance(
                current_items,
                list,
            ):
                current_items = []

            updated_items = []
            matched = False

            for item in current_items:
                if not isinstance(
                    item,
                    dict,
                ):
                    continue

                current_id = str(
                    item.get("id")
                    or ""
                ).strip()

                if current_id == image_item_id:
                    matched = True

                    item = {
                        **item,
                        "key": str(
                            relative_output_path
                        ).lstrip("/"),
                        "file_name": os.path.basename(
                            relative_output_path
                        ),
                        "mime_type": "image/jpeg",
                        "size": int(
                            output_size
                            or item.get("size")
                            or 0
                        ),
                        "width": image_meta.get(
                            "width"
                        ),
                        "height": image_meta.get(
                            "height"
                        ),
                        "aspect_ratio": image_meta.get(
                            "aspect_ratio"
                        ),
                        "variants": variants,
                    }

                updated_items.append(
                    item
                )

            if not matched:
                raise MomentImageItemSuperseded(
                    image_item_id=image_item_id,
                    expected_source_path=normalized_source_path,
                    current_source_path="",
                    reason="image_item_removed",
                )

            all_items_final = bool(
                updated_items
            ) and not any(
                _moment_image_item_requires_conversion(
                    item
                )
                for item in updated_items
                if isinstance(item, dict)
            )

            cover_id = str(
                getattr(
                    locked_instance,
                    "cover_image_id",
                    "",
                )
                or ""
            )

            should_bind_legacy_image = False

            if cover_id == image_item_id:
                should_bind_legacy_image = True

            elif (
                not cover_id
                and updated_items
            ):
                first_id = str(
                    updated_items[0].get("id")
                    or ""
                )

                should_bind_legacy_image = (
                    first_id
                    == image_item_id
                )

            update_values = {
                "image_items": updated_items,
                "is_converted": all_items_final,
            }

            if hasattr(
                locked_instance,
                "updated_at",
            ):
                update_values["updated_at"] = (
                    timezone.now()
                )

            if should_bind_legacy_image:
                update_values["image"] = (
                    relative_output_path
                )

            model_class._base_manager.filter(
                pk=locked_instance.pk
            ).update(
                **update_values
            )

        if (
            normalized_source_path
            != str(
                relative_output_path
            ).lstrip("/")
        ):
            _safe_delete_storage_key(
                normalized_source_path,
                label=(
                    "moment.image_item."
                    f"{image_item_id}"
                ),
            )

        job_update(
            job,
            status=MediaJobStatus.DONE,
            progress=100,
            message=(
                "Moment photo conversion completed"
            ),
            error="",
            output_path=relative_output_path,
            finished=True,
        )

        logger.info(
            (
                "✅ Moment image item conversion completed: "
                "%s[%s] %s -> %s"
            ),
            model_name,
            instance_id,
            field_name,
            relative_output_path,
        )

        if all_items_final:
            try:
                refreshed = get_instance(
                    app_label,
                    model_name,
                    instance_id,
                )

                refreshed.on_available()

            except Exception:
                logger.exception(
                    (
                        "Moment on_available failed after "
                        "image item conversion: %s[%s]"
                    ),
                    model_name,
                    instance_id,
                )

    except MomentImageItemSuperseded as exc:
        job_update(
            job,
            status=MediaJobStatus.CANCELED,
            progress=100,
            message=(
                "Canceled: Moment photo "
                "was removed or replaced"
            ),
            error="",
            finished=True,
        )

        logger.warning(
            (
                "Moment image conversion skipped because "
                "source changed: %s[%s] item=%s "
                "expected=%s current=%s reason=%s"
            ),
            model_name,
            instance_id,
            exc.image_item_id,
            exc.expected_source_path,
            exc.current_source_path,
            exc.reason,
        )

        return

    except MediaConversionCanceled:
        job_update(
            job,
            status=MediaJobStatus.CANCELED,
            progress=100,
            message="Canceled",
            error="",
            finished=True,
        )

        logger.info(
            (
                "🚫 Moment image item conversion "
                "canceled: %s[%s] %s"
            ),
            model_name,
            instance_id,
            field_name,
        )

        return

    except Exception as exc:
        job_update(
            job,
            status=MediaJobStatus.FAILED,
            progress=100,
            message=(
                "Moment photo conversion failed"
            ),
            error=str(exc),
            finished=True,
        )

        logger.exception(
            (
                "❌ Moment image item conversion "
                "failed for %s[%s] %s"
            ),
            model_name,
            instance_id,
            field_name,
        )

        raise

    finally:
        close_old_connections()