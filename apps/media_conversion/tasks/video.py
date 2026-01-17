# apps/media_conversion/tasks/video.py

import logging

from celery import shared_task
from django.core.files.storage import default_storage
from django.db import close_old_connections

from apps.media_conversion.models import MediaJobStatus
from apps.media_conversion.services.progress import touch_job

from utils.common.utils import FileUpload
from utils.common.video_utils import convert_video_to_multi_hls

from .base import (
    get_instance,
    get_job_by_current_task,
    job_update,
    can_autogen_thumbnail,
    extract_video_thumbnail,
    bind_converted_file,
)

logger = logging.getLogger(__name__)


@shared_task(queue="video")
def convert_video_to_multi_hls_task(
    model_name: str,
    app_label: str,
    instance_id: int,
    field_name: str,
    source_path: str,
    fileupload: dict,
):
    """
    Celery task:
    - optional thumbnail (NOT part of weighted timeline)
    - video → multi-bitrate HLS (weighted virtual timeline lives in video_utils)
    - bind result to model
    """

    close_old_connections()
    job = get_job_by_current_task()

    # -------------------------------------------------
    # Start lifecycle (do NOT micro-manage progress here)
    # Weighted progress is owned by video_utils via touch_job.
    # -------------------------------------------------
    job_update(
        job,
        status=MediaJobStatus.PROCESSING,
        progress=max(int(getattr(job, "progress", 0) or 0), 1),
        message="Preparing video conversion",
        source_path=source_path,
        started=True,
    )

    try:
        logger.info("🎬 Video conversion task started: %s[%s]", model_name, instance_id)

        # -------------------------------------------------
        # Fetch instance (tolerant to deletion)
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
            logger.warning("Target %s[%s] missing; canceling video task", model_name, instance_id)
            return

        upload = FileUpload(**fileupload)

        # -------------------------------------------------
        # Optional thumbnail (best-effort; not part of weighted stages)
        # -------------------------------------------------
        try:
            touch_job(job, message="Checking thumbnail…")  # keep alive, UI-friendly
            if (
                getattr(instance, "AUTO_THUMBNAIL_FROM_VIDEO", False)
                and can_autogen_thumbnail(instance)
            ):
                thumb_path = extract_video_thumbnail(instance, source_path)
                if thumb_path:
                    bind_converted_file(
                        model_name=model_name,
                        app_label=app_label,
                        instance_id=instance_id,
                        field_name="thumbnail",
                        relative_path=thumb_path,
                        mark_converted=False,   # 🔐 CRITICAL
                    )
                    logger.info("🖼️ Thumbnail generated: %s", thumb_path)
        except Exception as e:
            logger.warning("Thumbnail generation skipped for %s[%s]: %s", model_name, instance_id, e)

        # -------------------------------------------------
        # Video → HLS (AUTHORITATIVE weighted timeline happens inside)
        # video_utils will:
        # - set stage_plan (1080/720/480/finalize)
        # - update stage_progress + stage_completed_weight + ETA
        # -------------------------------------------------
        touch_job(job, message="Starting video encoding…")

        relative_output_path = convert_video_to_multi_hls(
            source_path=source_path,
            instance=instance,
            fileupload=upload,
            job=job,
        )

        # -------------------------------------------------
        # Bind output to target model field (fast final step)
        # Keep this separate from encoding stages.
        # -------------------------------------------------
        touch_job(job, message="Binding converted output…")

        bind_converted_file(
            model_name=model_name,
            app_label=app_label,
            instance_id=instance_id,
            field_name=field_name,
            relative_path=relative_output_path,
            mark_converted=False,  
        )

        # -------------------------------------------------
        # Finalize job (terminal)
        # -------------------------------------------------
        job_update(
            job,
            status=MediaJobStatus.DONE,
            progress=100,
            message="Conversion completed",
            output_path=relative_output_path,
            finished=True,
        )

        logger.info("✅ Video conversion completed: %s", relative_output_path)

        # -------------------------------------------------
        # Cleanup original upload (best-effort)
        # -------------------------------------------------
        try:
            if source_path and default_storage.exists(source_path):
                default_storage.delete(source_path)
                logger.info("🗑️ Deleted original uploaded video: %s", source_path)
        except Exception:
            logger.warning("Could not delete original uploaded video: %s", source_path)

    except Exception as e:
        job_update(
            job,
            status=MediaJobStatus.FAILED,
            progress=100,
            message="Conversion failed",
            error=str(e),
            finished=True,
        )
        logger.exception("❌ Video conversion failed for %s[%s]", model_name, instance_id)
        raise
