# apps/media_conversion/tasks/video.py

import logging

from celery import shared_task
from celery.exceptions import Retry
from django.core.files.storage import default_storage
from django.db import close_old_connections

from apps.media_conversion.models import MediaJobStatus
from apps.media_conversion.services.progress import touch_job
from apps.media_conversion.services.cancellation import cleanup_canceled_media_job

from apps.subtitles.services.transcript_builder import get_or_create_transcript_for_object
from apps.subtitles.services.audio_asset import build_stt_audio_from_source_video
from apps.subtitles.tasks import build_transcript_for_video

from utils.common.utils import FileUpload
from utils.common.video_utils import convert_video_to_multi_hls

from .base import (
    get_instance,
    get_job_by_current_task,
    job_update,
    can_autogen_thumbnail,
    extract_video_thumbnail,
    bind_converted_file,
    raise_if_job_canceled,
    is_job_canceled,
    MediaConversionCanceled,
)

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    queue="video",
    max_retries=5,
    default_retry_delay=2,
)
def convert_video_to_multi_hls_task(
    self,
    model_name: str,
    app_label: str,
    instance_id: int,
    field_name: str,
    source_path: str,
    fileupload: dict,
):
    """
    Celery task:
    - optional thumbnail
    - video -> multi-bitrate HLS
    - bind result to model
    - cancel-aware
    - cleanup-aware
    """
    close_old_connections()
    job = get_job_by_current_task()

    job_update(
        job,
        status=MediaJobStatus.PROCESSING,
        progress=max(int(getattr(job, "progress", 0) or 0), 1),
        message="Preparing video conversion",
        source_path=source_path,
        started=True,
    )

    try:
        raise_if_job_canceled(job)

        logger.info(
            "🎬 Video conversion task started: %s[%s] retry=%s/%s",
            model_name,
            instance_id,
            self.request.retries,
            self.max_retries,
        )

        # -------------------------------------------------
        # Fetch target instance
        # -------------------------------------------------
        try:
            instance = get_instance(
                app_label,
                model_name,
                instance_id,
            )

        except Exception as exc:
            current_retry = int(getattr(self.request, "retries", 0) or 0)
            max_retries = int(getattr(self, "max_retries", 0) or 0)

            if current_retry < max_retries:
                logger.warning(
                    "⏳ Target %s[%s] not visible yet; retrying %s/%s",
                    model_name,
                    instance_id,
                    current_retry + 1,
                    max_retries,
                )

                touch_job(
                    job,
                    message=(
                        "Waiting for target object visibility "
                        f"(retry {current_retry + 1}/{max_retries})…"
                    ),
                )

                raise self.retry(exc=exc)

            job_update(
                job,
                status=MediaJobStatus.CANCELED,
                progress=100,
                message="Canceled: target object not found after retries",
                finished=True,
            )

            cleanup_canceled_media_job(
                job,
                reason="target-not-found-after-retries",
            )

            logger.warning(
                "🚫 Target %s[%s] still missing after %s retries; canceling video task",
                model_name,
                instance_id,
                max_retries,
            )
            return

        raise_if_job_canceled(job)

        upload = FileUpload(**fileupload)

        # -------------------------------------------------
        # Optional thumbnail generation
        # -------------------------------------------------
        try:
            touch_job(job, message="Checking thumbnail…")
            raise_if_job_canceled(job)

            if (
                getattr(instance, "AUTO_THUMBNAIL_FROM_VIDEO", False)
                and can_autogen_thumbnail(instance)
            ):
                thumbnail_path = extract_video_thumbnail(
                    instance,
                    source_path,
                )

                raise_if_job_canceled(job)

                if thumbnail_path:
                    bind_converted_file(
                        model_name=model_name,
                        app_label=app_label,
                        instance_id=instance_id,
                        field_name="thumbnail",
                        relative_path=thumbnail_path,
                        mark_converted=False,
                    )

                    logger.info(
                        "🖼️ Thumbnail generated: %s",
                        thumbnail_path,
                    )

        except MediaConversionCanceled:
            raise

        except Exception as exc:
            logger.warning(
                "Thumbnail generation skipped for %s[%s]: %s",
                model_name,
                instance_id,
                exc,
            )

        # -------------------------------------------------
        # Video -> HLS
        # -------------------------------------------------
        raise_if_job_canceled(job)

        touch_job(job, message="Starting video encoding…")

        relative_output_path = convert_video_to_multi_hls(
            source_path=source_path,
            instance=instance,
            fileupload=upload,
            job=job,
            field_name=field_name,
        )

        raise_if_job_canceled(job)

        # Store output_path early so cleanup can remove HLS output if cancel
        # happens after conversion but before final DONE.
        job_update(
            job,
            output_path=relative_output_path,
            message="Binding converted output…",
        )

        # -------------------------------------------------
        # Bind converted output
        # -------------------------------------------------
        bind_converted_file(
            model_name=model_name,
            app_label=app_label,
            instance_id=instance_id,
            field_name=field_name,
            relative_path=relative_output_path,
            mark_converted=False,
        )

        raise_if_job_canceled(job)

        # -------------------------------------------------
        # Finalize conversion
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
            "✅ Video conversion completed: %s",
            relative_output_path,
        )

        # -------------------------------------------------
        # Testimony STT audio
        # -------------------------------------------------
        try:
            if model_name == "Testimony" and field_name == "video":
                from django.db import transaction

                raise_if_job_canceled(job)

                instance = get_instance(
                    app_label,
                    model_name,
                    instance_id,
                )

                transcript = get_or_create_transcript_for_object(instance)
                stt_source_path = relative_output_path or source_path

                if not stt_source_path or not default_storage.exists(stt_source_path):
                    raise FileNotFoundError(
                        f"STT source missing: {stt_source_path}"
                    )

                output_audio_path = (
                    f"posts/audios/testimony/stt/{instance_id}/audio.wav"
                )

                audio_path = build_stt_audio_from_source_video(
                    source_path=stt_source_path,
                    out_rel_path=output_audio_path,
                )

                transcript.stt_audio.name = audio_path
                transcript.stt_audio_format = "wav"
                transcript.save(
                    update_fields=[
                        "stt_audio",
                        "stt_audio_format",
                        "updated_at",
                    ]
                )

                logger.info(
                    "🎧 STT audio persisted: transcript=%s path=%s",
                    transcript.id,
                    transcript.stt_audio.name,
                )

                transaction.on_commit(
                    lambda: build_transcript_for_video.delay(transcript.id)
                )

        except MediaConversionCanceled:
            raise

        except Exception as exc:
            logger.warning(
                "STT audio build skipped: %s",
                exc,
                exc_info=True,
            )

        # -------------------------------------------------
        # Cleanup original uploaded video after success
        # -------------------------------------------------
        try:
            if source_path and default_storage.exists(source_path):
                default_storage.delete(source_path)

                logger.info(
                    "🗑️ Deleted original uploaded video: %s",
                    source_path,
                )
        except Exception:
            logger.warning(
                "Could not delete original uploaded video: %s",
                source_path,
            )

    except MediaConversionCanceled:
        cleanup_canceled_media_job(
            job,
            reason="worker-cancel-checkpoint",
        )

        job_update(
            job,
            status=MediaJobStatus.CANCELED,
            progress=100,
            message="Canceled",
            finished=True,
        )

        logger.info(
            "🚫 Video conversion canceled: %s[%s]",
            model_name,
            instance_id,
        )
        return

    except Retry:
        raise

    except Exception as exc:
        # If API cancel happened while ffmpeg/storage code was running,
        # do not overwrite CANCELED with FAILED.
        if is_job_canceled(job):
            cleanup_canceled_media_job(
                job,
                reason="worker-exception-after-cancel",
            )

            job_update(
                job,
                status=MediaJobStatus.CANCELED,
                progress=100,
                message="Canceled",
                finished=True,
            )

            logger.info(
                "🚫 Video conversion stopped after cancel: %s[%s]",
                model_name,
                instance_id,
            )
            return

        job_update(
            job,
            status=MediaJobStatus.FAILED,
            progress=100,
            message="Conversion failed",
            error=str(exc),
            finished=True,
        )

        logger.exception(
            "❌ Video conversion failed for %s[%s]",
            model_name,
            instance_id,
        )
        raise