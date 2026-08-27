# apps/media_conversion/tasks/video.py

import logging
import os
import uuid

from celery import shared_task
from celery.exceptions import Retry
from django.core.files.storage import default_storage
from django.db import close_old_connections

from apps.media_conversion.models import MediaJobStatus
from apps.media_conversion.services.progress import touch_job
from apps.media_conversion.services.cancellation import cleanup_canceled_media_job
from apps.media_conversion.services.media_manifest import (
    build_asset_payload,
    update_instance_media_asset,
)

from apps.subtitles.services.transcript_builder import get_or_create_transcript_for_object
from apps.subtitles.services.audio_asset import build_stt_audio_from_source_video
from apps.subtitles.tasks import build_transcript_for_video
from apps.media_conversion.services.media_metadata import image_metadata_from_storage

from utils.common.utils import FileUpload
from utils.common.video_utils import convert_video_to_multi_hls

from .base import (
    MediaConversionCanceled,
    MediaConversionSuperseded,
    MediaConversionTaskSuperseded,
    bind_converted_file,
    can_autogen_thumbnail,
    extract_video_thumbnail,
    get_instance,
    get_job_by_current_task,
    is_job_canceled,
    is_job_current_task,
    job_update,
    normalize_storage_key,
    raise_if_job_canceled,
    raise_if_source_superseded,
)

logger = logging.getLogger(__name__)

def _safe_delete_video_output(
    master_path: str | None,
) -> None:
    """
    Remove one unbound HLS output tree created by this worker.

    Safety:
    - Never infer or recursively delete a shared date/model directory.
    - Recursive cleanup is allowed only when master_path is an HLS playlist
      whose direct parent directory is UUID-scoped.
    - Unsafe or malformed paths fall back to exact-key deletion only.
    """

    normalized_path = normalize_storage_key(
        master_path
    )

    if not normalized_path:
        return

    def _delete_exact(
        key: str,
    ) -> None:
        try:
            if default_storage.exists(
                key
            ):
                default_storage.delete(
                    key
                )

                logger.info(
                    "🧹 Deleted stale video output: %s",
                    key,
                )

        except Exception:
            logger.warning(
                "Could not delete stale video output: %s",
                key,
                exc_info=True,
            )

    # Never recurse from a non-playlist file path.
    if not normalized_path.lower().endswith(
        ".m3u8"
    ):
        logger.error(
            (
                "Blocked recursive video cleanup for "
                "non-HLS path: %s"
            ),
            normalized_path,
        )

        _delete_exact(
            normalized_path
        )

        return

    prefix = os.path.dirname(
        normalized_path
    ).strip("/")

    if not prefix:
        logger.error(
            (
                "Blocked recursive video cleanup "
                "with empty prefix: %s"
            ),
            normalized_path,
        )

        _delete_exact(
            normalized_path
        )

        return

    prefix_leaf = os.path.basename(
        prefix
    )

    try:
        uuid.UUID(
            prefix_leaf
        )

    except (
        TypeError,
        ValueError,
        AttributeError,
    ):
        logger.error(
            (
                "Blocked unsafe recursive video cleanup: "
                "master=%s prefix=%s "
                "reason=parent_not_uuid_scoped"
            ),
            normalized_path,
            prefix,
        )

        # Exact master deletion is safe.
        _delete_exact(
            normalized_path
        )

        return

    def _delete_prefix(
        current_prefix: str,
    ) -> None:
        try:
            directories, files = (
                default_storage.listdir(
                    current_prefix
                )
            )

        except Exception:
            logger.warning(
                (
                    "Could not list stale video "
                    "output prefix: %s"
                ),
                current_prefix,
                exc_info=True,
            )

            return

        for filename in files:
            _delete_exact(
                (
                    f"{current_prefix}/"
                    f"{filename}"
                )
            )

        for directory in directories:
            _delete_prefix(
                (
                    f"{current_prefix}/"
                    f"{directory}"
                )
            )

    logger.info(
        (
            "🧹 Cleaning UUID-scoped stale "
            "HLS output tree: %s"
        ),
        prefix,
    )

    _delete_prefix(
        prefix
    )

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
    Convert one authoritative uploaded video to canonical HLS.

    Guarantees:
    - cancellation-aware
    - source-identity-aware
    - task-ownership-aware
    - stale workers never bind or mutate newer jobs
    - unbound stale HLS output is removed
    """

    close_old_connections()

    job = get_job_by_current_task()

    normalized_source_path = (
        normalize_storage_key(
            source_path
        )
    )

    conversion_result = None
    output_bound = False

    job_update(
        job,
        status=MediaJobStatus.PROCESSING,
        progress=max(
            int(
                getattr(
                    job,
                    "progress",
                    0,
                )
                or 0
            ),
            1,
        ),
        message="Preparing video conversion",
        source_path=normalized_source_path,
        started=True,
    )

    try:
        raise_if_job_canceled(
            job
        )

        # -------------------------------------------------
        # Fetch target
        # -------------------------------------------------
        try:
            instance = get_instance(
                app_label,
                model_name,
                instance_id,
            )

        except Exception as exc:
            # A deleted job means API cancellation already
            # removed the authoritative lifecycle.
            raise_if_job_canceled(
                job
            )

            current_retry = int(
                getattr(
                    self.request,
                    "retries",
                    0,
                )
                or 0
            )

            max_retries = int(
                getattr(
                    self,
                    "max_retries",
                    0,
                )
                or 0
            )

            if current_retry < max_retries:
                logger.warning(
                    (
                        "⏳ Target %s[%s] not visible yet; "
                        "retrying %s/%s"
                    ),
                    model_name,
                    instance_id,
                    current_retry + 1,
                    max_retries,
                )

                touch_job(
                    job,
                    message=(
                        "Waiting for target object visibility "
                        f"(retry {current_retry + 1}/"
                        f"{max_retries})…"
                    ),
                )

                raise self.retry(
                    exc=exc
                )

            job_update(
                job,
                status=MediaJobStatus.CANCELED,
                progress=100,
                message=(
                    "Canceled: target object "
                    "not found after retries"
                ),
                finished=True,
            )

            cleanup_canceled_media_job(
                job,
                reason=(
                    "target-not-found-after-retries"
                ),
            )

            logger.warning(
                (
                    "🚫 Target %s[%s] still missing after "
                    "%s retries; canceling video task"
                ),
                model_name,
                instance_id,
                max_retries,
            )

            return

        raise_if_job_canceled(
            job
        )

        # Never spend CPU on a source that has already
        # been removed or replaced.
        raise_if_source_superseded(
            instance=instance,
            model_name=model_name,
            instance_id=instance_id,
            field_name=field_name,
            expected_source_path=(
                normalized_source_path
            ),
        )

        upload = FileUpload(
            **fileupload
        )

        # -------------------------------------------------
        # Optional thumbnail
        # -------------------------------------------------
        try:
            touch_job(
                job,
                message="Checking thumbnail…",
            )

            raise_if_job_canceled(
                job
            )

            if (
                getattr(
                    instance,
                    "AUTO_THUMBNAIL_FROM_VIDEO",
                    False,
                )
                and can_autogen_thumbnail(
                    instance
                )
            ):
                thumbnail_path = (
                    extract_video_thumbnail(
                        instance,
                        normalized_source_path,
                    )
                )

                raise_if_job_canceled(
                    job
                )

                refreshed_source = get_instance(
                    app_label,
                    model_name,
                    instance_id,
                )

                raise_if_source_superseded(
                    instance=refreshed_source,
                    model_name=model_name,
                    instance_id=instance_id,
                    field_name=field_name,
                    expected_source_path=(
                        normalized_source_path
                    ),
                )

                if thumbnail_path:
                    bind_converted_file(
                        model_name=model_name,
                        app_label=app_label,
                        instance_id=instance_id,
                        field_name="thumbnail",
                        relative_path=thumbnail_path,
                        mark_converted=False,
                    )

                    try:
                        refreshed_for_thumbnail = (
                            get_instance(
                                app_label,
                                model_name,
                                instance_id,
                            )
                        )

                        thumbnail_meta = (
                            image_metadata_from_storage(
                                thumbnail_path
                            )
                        )

                        thumbnail_asset = (
                            build_asset_payload(
                                key=thumbnail_path,
                                metadata=thumbnail_meta,
                            )
                        )

                        update_instance_media_asset(
                            instance=(
                                refreshed_for_thumbnail
                            ),
                            field_name="thumbnail",
                            payload=thumbnail_asset,
                        )

                    except Exception:
                        logger.warning(
                            (
                                "Thumbnail metadata update "
                                "skipped for %s[%s]"
                            ),
                            model_name,
                            instance_id,
                            exc_info=True,
                        )

                    logger.info(
                        "🖼️ Thumbnail generated: %s",
                        thumbnail_path,
                    )

        except (
            MediaConversionCanceled,
            MediaConversionSuperseded,
            MediaConversionTaskSuperseded,
        ):
            raise

        except Exception as exc:
            logger.warning(
                (
                    "Thumbnail generation skipped "
                    "for %s[%s]: %s"
                ),
                model_name,
                instance_id,
                exc,
            )

        # -------------------------------------------------
        # Video -> HLS
        # -------------------------------------------------
        raise_if_job_canceled(
            job
        )

        # Re-check immediately before the expensive encoder.
        refreshed_before_encoding = (
            get_instance(
                app_label,
                model_name,
                instance_id,
            )
        )

        raise_if_source_superseded(
            instance=refreshed_before_encoding,
            model_name=model_name,
            instance_id=instance_id,
            field_name=field_name,
            expected_source_path=(
                normalized_source_path
            ),
        )

        touch_job(
            job,
            message="Starting video encoding…",
        )

        conversion_result = (
            convert_video_to_multi_hls(
                source_path=normalized_source_path,
                instance=refreshed_before_encoding,
                fileupload=upload,
                job=job,
                field_name=field_name,
            )
        )

        relative_output_path = (
            conversion_result.master_path
        )

        # Cancellation or retry/source replacement may
        # have happened while FFmpeg was running.
        raise_if_job_canceled(
            job
        )

        refreshed_before_bind = get_instance(
            app_label,
            model_name,
            instance_id,
        )

        raise_if_source_superseded(
            instance=refreshed_before_bind,
            model_name=model_name,
            instance_id=instance_id,
            field_name=field_name,
            expected_source_path=(
                normalized_source_path
            ),
        )

        video_asset = build_asset_payload(
            key=relative_output_path,
            metadata={
                "width": (
                    conversion_result.width
                ),
                "height": (
                    conversion_result.height
                ),
                "aspect_ratio": (
                    conversion_result.aspect_ratio
                ),
                "duration_ms": (
                    conversion_result.duration_ms
                ),
                "mime_type": (
                    "application/vnd.apple.mpegurl"
                ),
                "size": 0,
            },
            extra={
                "qualities": (
                    conversion_result.variants
                ),
                "preview": (
                    conversion_result.preview
                ),
            },
        )

        job_update(
            job,
            output_path=relative_output_path,
            message="Binding converted output…",
        )

        raise_if_job_canceled(
            job
        )

        # -------------------------------------------------
        # Atomic guarded bind
        # -------------------------------------------------
        bind_converted_file(
            model_name=model_name,
            app_label=app_label,
            instance_id=instance_id,
            field_name=field_name,
            relative_path=relative_output_path,
            mark_converted=False,
            expected_source_path=(
                normalized_source_path
            ),
        )

        output_bound = True

        refreshed_instance = get_instance(
            app_label,
            model_name,
            instance_id,
        )

        update_instance_media_asset(
            instance=refreshed_instance,
            field_name=field_name,
            payload=video_asset,
        )

        raise_if_job_canceled(
            job
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
            "✅ Video conversion completed: %s",
            relative_output_path,
        )

        # -------------------------------------------------
        # Testimony STT
        # -------------------------------------------------
        try:
            if (
                model_name == "Testimony"
                and field_name == "video"
            ):
                from django.db import transaction

                raise_if_job_canceled(
                    job
                )

                instance = get_instance(
                    app_label,
                    model_name,
                    instance_id,
                )

                transcript = (
                    get_or_create_transcript_for_object(
                        instance
                    )
                )

                stt_source_path = (
                    relative_output_path
                    or normalized_source_path
                )

                if (
                    not stt_source_path
                    or not default_storage.exists(
                        stt_source_path
                    )
                ):
                    raise FileNotFoundError(
                        (
                            "STT source missing: "
                            f"{stt_source_path}"
                        )
                    )

                output_audio_path = (
                    "posts/audios/testimony/"
                    f"stt/{instance_id}/audio.wav"
                )

                audio_path = (
                    build_stt_audio_from_source_video(
                        source_path=stt_source_path,
                        out_rel_path=output_audio_path,
                    )
                )

                transcript.stt_audio.name = (
                    audio_path
                )

                transcript.stt_audio_format = (
                    "wav"
                )

                transcript.save(
                    update_fields=[
                        "stt_audio",
                        "stt_audio_format",
                        "updated_at",
                    ]
                )

                logger.info(
                    (
                        "🎧 STT audio persisted: "
                        "transcript=%s path=%s"
                    ),
                    transcript.id,
                    transcript.stt_audio.name,
                )

                transaction.on_commit(
                    lambda: (
                        build_transcript_for_video.delay(
                            transcript.id
                        )
                    )
                )

        except (
            MediaConversionCanceled,
            MediaConversionTaskSuperseded,
        ):
            raise

        except Exception as exc:
            logger.warning(
                "STT audio build skipped: %s",
                exc,
                exc_info=True,
            )

        # -------------------------------------------------
        # Delete original only after authoritative success
        # -------------------------------------------------
        try:
            if (
                normalized_source_path
                and default_storage.exists(
                    normalized_source_path
                )
            ):
                default_storage.delete(
                    normalized_source_path
                )

                logger.info(
                    (
                        "🗑️ Deleted original uploaded "
                        "video: %s"
                    ),
                    normalized_source_path,
                )

        except Exception:
            logger.warning(
                (
                    "Could not delete original "
                    "uploaded video: %s"
                ),
                normalized_source_path,
                exc_info=True,
            )

    except MediaConversionTaskSuperseded as exc:
        if (
            conversion_result is not None
            and not output_bound
        ):
            _safe_delete_video_output(
                conversion_result.master_path
            )

        # Never mutate or clean the authoritative newer job.
        logger.info(
            (
                "Video worker superseded by newer task: "
                "%s[%s].%s %s"
            ),
            model_name,
            instance_id,
            field_name,
            exc,
        )

        return

    except MediaConversionSuperseded as exc:
        if (
            conversion_result is not None
            and not output_bound
        ):
            _safe_delete_video_output(
                conversion_result.master_path
            )

        job_update(
            job,
            status=MediaJobStatus.CANCELED,
            progress=100,
            message="Canceled: source was replaced",
            error="",
            finished=True,
        )

        logger.info(
            (
                "Video conversion superseded: "
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
        if (
            conversion_result is not None
            and not output_bound
        ):
            _safe_delete_video_output(
                conversion_result.master_path
            )

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
            (
                "🚫 Video conversion canceled: "
                "%s[%s]"
            ),
            model_name,
            instance_id,
        )

        return

    except Retry:
        raise

    except Exception as exc:
        if not is_job_current_task(
            job
        ):
            if (
                conversion_result is not None
                and not output_bound
            ):
                _safe_delete_video_output(
                    conversion_result.master_path
                )

            logger.info(
                (
                    "Video worker exited after losing "
                    "job ownership: %s[%s]"
                ),
                model_name,
                instance_id,
            )

            return

        if is_job_canceled(
            job
        ):
            if (
                conversion_result is not None
                and not output_bound
            ):
                _safe_delete_video_output(
                    conversion_result.master_path
                )

            cleanup_canceled_media_job(
                job,
                reason=(
                    "worker-exception-after-cancel"
                ),
            )

            job_update(
                job,
                status=MediaJobStatus.CANCELED,
                progress=100,
                message="Canceled",
                finished=True,
            )

            logger.info(
                (
                    "🚫 Video conversion stopped "
                    "after cancel: %s[%s]"
                ),
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
            (
                "❌ Video conversion failed "
                "for %s[%s]"
            ),
            model_name,
            instance_id,
        )

        raise

    finally:
        close_old_connections()