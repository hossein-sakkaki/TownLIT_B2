# apps/creative_editor/tasks/sticker.py

from __future__ import annotations

import logging

from celery import shared_task
from django.core.files.storage import default_storage
from django.db import close_old_connections

from apps.media_conversion.models import MediaJobStatus
from apps.media_conversion.services.media_manifest import (
    build_asset_payload,
    update_instance_media_asset,
)
from apps.media_conversion.services.media_metadata import (
    image_metadata_from_storage,
)
from apps.media_conversion.tasks.base import (
    MediaConversionCanceled,
    bind_converted_file,
    get_instance,
    get_job_by_current_task,
    job_update,
    raise_if_job_canceled,
)
from utils.common.sticker_utils import convert_sticker_to_png
from utils.common.utils import FileUpload


logger = logging.getLogger(__name__)


def _safe_delete_source(
    source_path: str,
    output_path: str,
) -> None:
    """
    Delete replaced raw sticker.
    """

    source_key = str(source_path or "").lstrip("/")
    output_key = str(output_path or "").lstrip("/")

    if not source_key or source_key == output_key:
        return

    try:
        if default_storage.exists(source_key):
            default_storage.delete(source_key)
    except Exception:
        logger.exception(
            "creative_editor.sticker_source_delete.failed",
            extra={
                "source_path": source_key,
            },
        )


@shared_task(queue="video")
def convert_sticker_to_png_task(
    model_name: str,
    app_label: str,
    instance_id: int,
    field_name: str,
    source_path: str,
    fileupload: dict,
):
    """
    Convert a static sticker while preserving alpha.
    """

    close_old_connections()

    job = get_job_by_current_task()

    job_update(
        job,
        status=MediaJobStatus.PROCESSING,
        progress=1,
        message="Preparing sticker conversion",
        source_path=source_path,
        started=True,
    )

    try:
        raise_if_job_canceled(job)

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
                message="Canceled: sticker no longer exists",
                finished=True,
            )
            return

        upload = FileUpload(**fileupload)

        job_update(
            job,
            progress=15,
            message="Converting sticker to PNG",
        )

        output_path = convert_sticker_to_png(
            source_path,
            instance,
            upload,
        )

        raise_if_job_canceled(job)

        metadata = image_metadata_from_storage(output_path)

        # Sticker variants also preserve PNG alpha.
        asset_payload = build_asset_payload(
            key=output_path,
            metadata=metadata,
            variants={},
            extra={
                "mime_type": "image/png",
                "supports_alpha": True,
            },
        )

        job_update(
            job,
            progress=85,
            message="Publishing sticker",
        )

        bind_converted_file(
            model_name=model_name,
            app_label=app_label,
            instance_id=instance_id,
            field_name=field_name,
            relative_path=output_path,
            mark_converted=True,
        )

        refreshed = get_instance(
            app_label,
            model_name,
            instance_id,
        )

        update_instance_media_asset(
            instance=refreshed,
            field_name=field_name,
            payload=asset_payload,
        )

        _safe_delete_source(
            source_path,
            output_path,
        )

        job_update(
            job,
            status=MediaJobStatus.DONE,
            progress=100,
            message="Sticker conversion completed",
            output_path=output_path,
            finished=True,
        )

    except MediaConversionCanceled:
        job_update(
            job,
            status=MediaJobStatus.CANCELED,
            progress=100,
            message="Canceled",
            finished=True,
        )

    except Exception as exc:
        job_update(
            job,
            status=MediaJobStatus.FAILED,
            progress=100,
            message="Sticker conversion failed",
            error=str(exc),
            finished=True,
        )

        logger.exception(
            "creative_editor.sticker_conversion.failed",
            extra={
                "instance_id": instance_id,
                "field_name": field_name,
            },
        )

        raise