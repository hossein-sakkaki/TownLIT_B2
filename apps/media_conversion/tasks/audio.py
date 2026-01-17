# apps/media_conversion/tasks/audio.py

import logging

from celery import shared_task
from django.core.files.storage import default_storage
from django.db import close_old_connections

from apps.media_conversion.models import MediaJobStatus

from utils.common.utils import FileUpload
from utils.common.audio_utils import convert_audio_to_mp3

from .base import (
    get_instance,
    get_job_by_current_task,
    job_update,
    bind_converted_file,
)

logger = logging.getLogger(__name__)


@shared_task(queue="video")
def convert_audio_to_mp3_task(
    model_name: str,
    app_label: str,
    instance_id: int,
    field_name: str,
    source_path: str,
    fileupload: dict,
):
    """
    Celery task:
    - audio → MP3
    - bind result to model
    - cleanup RAW
    """

    close_old_connections()
    job = get_job_by_current_task()

    job_update(
        job,
        status=MediaJobStatus.PROCESSING,
        progress=1,
        message="Preparing audio conversion",
        source_path=source_path,
        started=True,
    )

    try:
        logger.info(
            "🔊 Audio conversion task started: %s[%s]",
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
                "Target %s[%s] missing; canceling audio task",
                model_name,
                instance_id,
            )
            return

        upload = FileUpload(**fileupload)

        # -------------------------------------------------
        # Convert audio
        # -------------------------------------------------
        job_update(job, progress=10, message="Converting audio to MP3")

        relative_output_path = convert_audio_to_mp3(
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
        # Cleanup RAW
        # -------------------------------------------------
        if source_path and default_storage.exists(source_path):
            default_storage.delete(source_path)
            logger.info("🗑️ Deleted original uploaded audio: %s", source_path)

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
            "✅ Audio conversion completed: %s",
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
            "❌ Audio conversion failed for %s[%s]",
            model_name,
            instance_id,
        )
        raise
