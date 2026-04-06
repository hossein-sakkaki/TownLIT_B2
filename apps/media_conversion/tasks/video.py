# apps/media_conversion/tasks/video.py

import logging

from celery import shared_task
from celery.exceptions import Retry
from django.core.files.storage import default_storage
from django.db import close_old_connections

from apps.media_conversion.models import MediaJobStatus
from apps.media_conversion.services.progress import touch_job

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
    - optional thumbnail (NOT part of weighted timeline)
    - video → multi-bitrate HLS (weighted virtual timeline lives in video_utils)
    - bind result to model

    Retry policy:
    - if target instance is not yet visible (transaction / replica lag),
      retry a few times before canceling.
    """

    close_old_connections()
    job = get_job_by_current_task()

    # -------------------------------------------------
    # Start lifecycle
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
        logger.info(
            "🎬 Video conversion task started: %s[%s] (retry=%s/%s)",
            model_name,
            instance_id,
            self.request.retries,
            self.max_retries,
        )

        # -------------------------------------------------
        # Fetch instance
        # Retry first, cancel only after retry budget is exhausted.
        # -------------------------------------------------
        try:
            instance = get_instance(app_label, model_name, instance_id)

        except Exception as exc:
            current_retry = int(getattr(self.request, "retries", 0) or 0)
            max_retries = int(getattr(self, "max_retries", 0) or 0)

            if current_retry < max_retries:
                logger.warning(
                    "⏳ Target %s[%s] not visible yet; retrying (%s/%s)...",
                    model_name,
                    instance_id,
                    current_retry + 1,
                    max_retries,
                )

                touch_job(
                    job,
                    message=f"Waiting for target object visibility (retry {current_retry + 1}/{max_retries})…",
                )

                raise self.retry(exc=exc)

            job_update(
                job,
                status=MediaJobStatus.CANCELED,
                progress=100,
                message="Canceled: target object not found after retries",
                finished=True,
            )

            logger.warning(
                "🚫 Target %s[%s] still missing after %s retries; canceling video task",
                model_name,
                instance_id,
                max_retries,
            )
            return

        upload = FileUpload(**fileupload)

        # -------------------------------------------------
        # Optional thumbnail (best-effort; not part of weighted stages)
        # -------------------------------------------------
        try:
            touch_job(job, message="Checking thumbnail…")

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
                        mark_converted=False,
                    )
                    logger.info("🖼️ Thumbnail generated: %s", thumb_path)

        except Exception as e:
            logger.warning(
                "Thumbnail generation skipped for %s[%s]: %s",
                model_name,
                instance_id,
                e,
            )

        # -------------------------------------------------
        # Video → HLS
        # Weighted timeline is handled inside video_utils.
        # -------------------------------------------------
        touch_job(job, message="Starting video encoding…")

        relative_output_path = convert_video_to_multi_hls(
            source_path=source_path,
            instance=instance,
            fileupload=upload,
            job=job,
        )

        # -------------------------------------------------
        # Bind output to target model field
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
        # Finalize job
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
        # Build & persist STT audio BEFORE cleanup
        # -------------------------------------------------
        try:
            logger.info(
                "STT CHECK: model_name=%s field_name=%s instance_id=%s source_path=%s output_path=%s",
                model_name,
                field_name,
                instance_id,
                source_path,
                relative_output_path,
            )

            # Short English comment: keep STT audio for subtitles / dubbing
            if model_name == "Testimony" and field_name == "video":
                from django.db import transaction

                # Refresh instance to ensure fields are updated
                instance = get_instance(app_label, model_name, instance_id)
                transcript = get_or_create_transcript_for_object(instance)

                # Prefer HLS output (stable) instead of original upload
                stt_source_path = relative_output_path or source_path

                logger.info(
                    "STT SOURCE EXISTS? %s -> %s",
                    stt_source_path,
                    default_storage.exists(stt_source_path),
                )

                if not stt_source_path or not default_storage.exists(stt_source_path):
                    raise FileNotFoundError(f"STT source missing: {stt_source_path}")

                # Stable storage path for STT audio
                out_audio_rel = f"posts/audios/testimony/stt/{instance_id}/audio.wav"

                audio_rel = build_stt_audio_from_source_video(
                    source_path=stt_source_path,
                    out_rel_path=out_audio_rel,
                )

                # Do NOT re-save the file again.
                # Just point FileField to the already-saved storage path.
                transcript.stt_audio.name = audio_rel
                transcript.stt_audio_format = "wav"
                transcript.save(update_fields=["stt_audio", "stt_audio_format", "updated_at"])

                logger.info(
                    "🎧 STT audio persisted: transcript=%s path=%s",
                    transcript.id,
                    transcript.stt_audio.name,
                )

                # Enqueue STT only after DB commit
                transaction.on_commit(
                    lambda: build_transcript_for_video.delay(transcript.id)
                )

        except Exception as e:
            logger.warning("STT audio build skipped: %s", e, exc_info=True)

        # -------------------------------------------------
        # Cleanup original upload (best-effort)
        # -------------------------------------------------
        try:
            if source_path and default_storage.exists(source_path):
                default_storage.delete(source_path)
                logger.info("🗑️ Deleted original uploaded video: %s", source_path)
        except Exception:
            logger.warning("Could not delete original uploaded video: %s", source_path)

    except Retry:
        # Celery retry is not a failure; let Celery handle it.
        raise

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