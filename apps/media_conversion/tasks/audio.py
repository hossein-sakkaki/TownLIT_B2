# apps/media_conversion/tasks/audio.py

from __future__ import annotations

import logging

from celery import shared_task
from django.apps import apps
from django.core.files.storage import default_storage
from django.db import close_old_connections

from apps.media_conversion.models import MediaJobStatus

from utils.common.audio_utils import (
    AudioConversionResult,
    convert_audio_to_mp3_with_metadata,
)
from utils.common.utils import FileUpload

from .base import (
    MediaConversionCanceled,
    MediaConversionSuperseded,
    bind_converted_file,
    get_instance,
    get_job_by_current_task,
    job_update,
    normalize_storage_key,
    raise_if_job_canceled,
    raise_if_source_superseded,
)


logger = logging.getLogger(__name__)


def _apply_audio_metadata(
    *,
    app_label: str,
    model_name: str,
    instance_id: int,
    result: AudioConversionResult,
) -> None:
    """
    Persist technical metadata only when the target model exposes the
    corresponding concrete fields.

    This keeps the shared conversion task compatible with models that
    do not store audio metadata while automatically hydrating models
    such as MusicTrackVariant.
    """

    model_class = apps.get_model(
        app_label=app_label,
        model_name=model_name,
    )

    concrete_fields = {
        field.name
        for field in model_class._meta.concrete_fields
    }

    candidate_values = {
        "duration_ms": result.duration_ms,
        "mime_type": result.mime_type,
        "codec": result.codec,
        "container": result.container,
        "bitrate_kbps": result.bitrate_kbps,
        "sample_rate_hz": result.sample_rate_hz,
        "channels": result.channels,
        "file_size_bytes": result.file_size_bytes,
        "checksum_sha256": result.checksum_sha256,
    }

    update_values = {
        field_name: value
        for field_name, value in candidate_values.items()
        if field_name in concrete_fields and value is not None
    }

    if not update_values:
        return

    model_class._base_manager.filter(
        pk=instance_id,
    ).update(
        **update_values
    )

    logger.info(
        "Updated audio metadata for %s[%s]: %s",
        model_name,
        instance_id,
        sorted(update_values.keys()),
    )


def _delete_storage_file_if_present(path: str | None) -> None:
    normalized_path = normalize_storage_key(path)

    if not normalized_path:
        return

    try:
        if default_storage.exists(normalized_path):
            default_storage.delete(normalized_path)
    except Exception:
        logger.exception(
            "Failed to delete audio storage object: %s",
            normalized_path,
        )


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
    Convert validated audio into the canonical TownLIT MP3 profile.

    Guarantees:
    - cancel-aware
    - stale-source aware
    - high-quality canonical MP3 output
    - real duration and technical metadata hydration when supported
    - original upload deleted only after successful guarded binding
    """

    close_old_connections()

    job = get_job_by_current_task()
    result: AudioConversionResult | None = None
    output_bound = False

    job_update(
        job,
        status=MediaJobStatus.PROCESSING,
        progress=1,
        message="Preparing audio conversion",
        source_path=source_path,
        started=True,
    )

    try:
        raise_if_job_canceled(job)

        logger.info(
            "Audio conversion task started: %s[%s].%s source=%s",
            model_name,
            instance_id,
            field_name,
            source_path,
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
                "Target %s[%s] missing; canceling audio task",
                model_name,
                instance_id,
            )
            return

        raise_if_job_canceled(job)

        # Stop obsolete work before spending CPU on FFmpeg.
        raise_if_source_superseded(
            instance=instance,
            model_name=model_name,
            instance_id=instance_id,
            field_name=field_name,
            expected_source_path=source_path,
        )

        upload = FileUpload(**fileupload)

        job_update(
            job,
            progress=10,
            message="Converting audio to canonical MP3",
        )

        result = convert_audio_to_mp3_with_metadata(
            source_path,
            instance,
            upload,
        )

        raise_if_job_canceled(job)

        job_update(
            job,
            progress=90,
            message="Validating and binding converted audio",
            output_path=result.storage_path,
        )

        # Guard the final bind with a row lock. If the admin/user
        # replaced the source during conversion, stale output cannot
        # overwrite the newer upload.
        bind_converted_file(
            model_name=model_name,
            app_label=app_label,
            instance_id=instance_id,
            field_name=field_name,
            relative_path=result.storage_path,
            expected_source_path=source_path,
        )

        output_bound = True

        # Hydrate duration/codec/sample-rate/etc. after the guarded
        # file bind. Models without these fields remain unaffected.
        _apply_audio_metadata(
            app_label=app_label,
            model_name=model_name,
            instance_id=instance_id,
            result=result,
        )

        source_key = normalize_storage_key(source_path)
        output_key = normalize_storage_key(result.storage_path)

        if source_key and source_key != output_key:
            _delete_storage_file_if_present(source_key)

            logger.info(
                "Deleted original uploaded audio after successful bind: %s",
                source_key,
            )

        job_update(
            job,
            status=MediaJobStatus.DONE,
            progress=100,
            message="Conversion completed",
            output_path=result.storage_path,
            finished=True,
        )

        logger.info(
            (
                "Audio conversion completed: %s "
                "duration_ms=%s sample_rate=%s channels=%s"
            ),
            result.storage_path,
            result.duration_ms,
            result.sample_rate_hz,
            result.channels,
        )

    except MediaConversionCanceled:
        if result is not None and not output_bound:
            _delete_storage_file_if_present(
                result.storage_path
            )

        job_update(
            job,
            status=MediaJobStatus.CANCELED,
            progress=100,
            message="Canceled",
            finished=True,
        )

        logger.info(
            "Audio conversion canceled: %s[%s]",
            model_name,
            instance_id,
        )

    except MediaConversionSuperseded as exc:
        if result is not None and not output_bound:
            _delete_storage_file_if_present(
                result.storage_path
            )

        job_update(
            job,
            status=MediaJobStatus.CANCELED,
            progress=100,
            message="Canceled: source was replaced",
            error=str(exc),
            finished=True,
        )

        logger.info(
            "Audio conversion superseded: %s[%s] %s",
            model_name,
            instance_id,
            exc,
        )

    except Exception as exc:
        if result is not None and not output_bound:
            _delete_storage_file_if_present(
                result.storage_path
            )

        job_update(
            job,
            status=MediaJobStatus.FAILED,
            progress=100,
            message="Conversion failed",
            error=str(exc),
            finished=True,
        )

        logger.exception(
            "Audio conversion failed for %s[%s]",
            model_name,
            instance_id,
        )

        raise

    finally:
        close_old_connections()