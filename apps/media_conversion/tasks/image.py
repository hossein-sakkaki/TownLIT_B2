# apps/media_conversion/tasks/image.py

import logging

from celery import shared_task
from django.db import close_old_connections

from apps.media_conversion.models import MediaJobStatus

from utils.common.utils import FileUpload
from utils.common.image_utils import convert_image_to_jpg

from .base import (
    get_instance,
    get_job_by_current_task,
    job_update,
    bind_converted_file,
)

logger = logging.getLogger(__name__)


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
    - image → JPG
    - bind result to model
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
        logger.info(
            "🖼️ Image conversion task started: %s[%s]",
            model_name,
            instance_id,
        )

        # -------------------------------------------------
        # Fetch instance (tolerant)
        # -------------------------------------------------
        try:
            instance = get_instance(app_label, model_name, instance_id)
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

        upload = FileUpload(**fileupload)

        # -------------------------------------------------
        # Convert image
        # -------------------------------------------------
        job_update(job, progress=10, message="Converting image to JPG")

        relative_output_path = convert_image_to_jpg(
            source_path,
            instance,
            upload,
        )

        # -------------------------------------------------
        # Bind output
        # -------------------------------------------------
        job_update(job, progress=90, message="Finalizing output")

        bind_converted_file(
            model_name=model_name,
            app_label=app_label,
            instance_id=instance_id,
            field_name=field_name,
            relative_path=relative_output_path,
        )

        # -------------------------------------------------
        # Finalize
        # -------------------------------------------------
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

    except Exception as e:
        job_update(
            job,
            status=MediaJobStatus.FAILED,
            progress=100,
            message="Conversion failed",
            error=str(e),
            finished=True,
        )
        logger.exception(
            "❌ Image conversion failed for %s[%s]",
            model_name,
            instance_id,
        )
        raise
