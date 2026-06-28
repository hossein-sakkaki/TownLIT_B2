# apps/media_conversion/tasks/image.py

import logging
import os

from celery import shared_task
from django.core.files.storage import default_storage
from django.db import close_old_connections
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
    get_instance,
    get_job_by_current_task,
    job_update,
    bind_converted_file,
    raise_if_job_canceled,
    MediaConversionCanceled,
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
    """
    close_old_connections()
    job = get_job_by_current_task()

    job_update(
        job,
        status=MediaJobStatus.PROCESSING,
        progress=1,
        message="Preparing image conversion",
        source_path=source_path,
        started=True,
    )

    try:
        raise_if_job_canceled(job)

        logger.info(
            "🖼️ Image conversion task started: %s[%s]",
            model_name,
            instance_id,
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
                finished=True,
            )

            logger.warning(
                "Target %s[%s] missing; canceling image task",
                model_name,
                instance_id,
            )
            return

        raise_if_job_canceled(job)

        upload = FileUpload(**fileupload)

        job_update(
            job,
            progress=10,
            message="Converting image to JPG",
        )

        relative_output_path = convert_image_to_jpg(
            source_path,
            instance,
            upload,
        )

        image_meta = image_metadata_from_storage(relative_output_path)

        variant_dir = os.path.dirname(relative_output_path)
        basename = os.path.splitext(os.path.basename(relative_output_path))[0]

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

        bind_converted_file(
            model_name=model_name,
            app_label=app_label,
            instance_id=instance_id,
            field_name=field_name,
            relative_path=relative_output_path,
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
            output_path=relative_output_path,
            finished=True,
        )

        logger.info(
            "✅ Image conversion completed: %s",
            relative_output_path,
        )

    except MediaConversionCanceled:
        job_update(
            job,
            status=MediaJobStatus.CANCELED,
            progress=100,
            message="Canceled",
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
    - mark Moment converted when all image items are web-safe
    - cancel-aware
    """
    close_old_connections()
    job = get_job_by_current_task()

    job_update(
        job,
        status=MediaJobStatus.PROCESSING,
        progress=1,
        message="Preparing Moment photo conversion",
        source_path=source_path,
        started=True,
    )

    try:
        raise_if_job_canceled(job)

        logger.info(
            "🖼️ Moment image item conversion started: %s[%s] %s",
            model_name,
            instance_id,
            field_name,
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
                finished=True,
            )

            logger.warning(
                "Target %s[%s] missing; canceling Moment image item task",
                model_name,
                instance_id,
            )
            return

        raise_if_job_canceled(job)

        if not field_name.startswith("image_items:"):
            raise ValueError(
                f"Invalid Moment image item field_name: {field_name}"
            )

        image_item_id = field_name.split(":", 1)[1].strip()
        if not image_item_id:
            raise ValueError("Missing image item id.")

        upload = FileUpload(**fileupload)

        job_update(
            job,
            progress=10,
            message="Converting Moment photo to JPG",
        )

        relative_output_path = convert_image_to_jpg(
            source_path,
            instance,
            upload,
        )

        image_meta = image_metadata_from_storage(relative_output_path)

        variant_dir = os.path.dirname(relative_output_path)
        basename = os.path.splitext(os.path.basename(relative_output_path))[0]

        variants = build_image_variants(
            source_key=relative_output_path,
            base_output_dir=f"{variant_dir}/variants",
            basename=basename,
        )
        
        raise_if_job_canceled(job)

        job_update(
            job,
            progress=80,
            message="Updating Moment image item",
        )

        items = getattr(instance, "image_items", None) or []
        if not isinstance(items, list):
            items = []

        updated_items = []
        matched = False

        try:
            output_size = default_storage.size(relative_output_path)
        except Exception:
            output_size = 0

        for item in items:
            if not isinstance(item, dict):
                continue

            current_id = str(item.get("id") or "")

            if current_id == image_item_id:
                matched = True
                item = {
                    **item,
                    "key": str(relative_output_path).lstrip("/"),
                    "file_name": os.path.basename(relative_output_path),
                    "mime_type": "image/jpeg",
                    "size": int(output_size or item.get("size") or 0),
                    "width": image_meta.get("width"),
                    "height": image_meta.get("height"),
                    "aspect_ratio": image_meta.get("aspect_ratio"),
                    "variants": variants,
                }

            updated_items.append(item)

        if not matched:
            raise ValueError(
                f"Moment image item not found: {image_item_id}"
            )

        final_extensions = (
            ".jpg",
            ".jpeg",
            ".png",
        )

        all_items_final = True

        for item in updated_items:
            key = str(item.get("key") or "").lower()

            if not key.endswith(final_extensions):
                all_items_final = False
                break

        cover_id = str(getattr(instance, "cover_image_id", "") or "")

        should_bind_legacy_image = False

        if cover_id == image_item_id:
            should_bind_legacy_image = True
        elif not cover_id and updated_items:
            first_id = str(updated_items[0].get("id") or "")
            should_bind_legacy_image = first_id == image_item_id

        update_fields = {
            "image_items": updated_items,
        }

        if hasattr(instance, "updated_at"):
            update_fields["updated_at"] = timezone.now()

        if should_bind_legacy_image:
            update_fields["image"] = relative_output_path

        if all_items_final:
            update_fields["is_converted"] = True

        raise_if_job_canceled(job)

        type(instance).objects.filter(pk=instance.pk).update(**update_fields)

        if str(source_path).lstrip("/") != str(relative_output_path).lstrip("/"):
            _safe_delete_storage_key(
                source_path,
                label=f"moment.image_item.{image_item_id}",
            )

        job_update(
            job,
            status=MediaJobStatus.DONE,
            progress=100,
            message="Moment photo conversion completed",
            output_path=relative_output_path,
            finished=True,
        )

        logger.info(
            "✅ Moment image item conversion completed: %s[%s] %s -> %s",
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
                    "Moment on_available failed after image item conversion: %s[%s]",
                    model_name,
                    instance_id,
                )

    except MediaConversionCanceled:
        job_update(
            job,
            status=MediaJobStatus.CANCELED,
            progress=100,
            message="Canceled",
            finished=True,
        )

        logger.info(
            "🚫 Moment image item conversion canceled: %s[%s] %s",
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
            message="Moment photo conversion failed",
            error=str(exc),
            finished=True,
        )

        logger.exception(
            "❌ Moment image item conversion failed for %s[%s] %s",
            model_name,
            instance_id,
            field_name,
        )
        raise