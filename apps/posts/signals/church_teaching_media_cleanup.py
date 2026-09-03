# apps/posts/signals/church_teaching_media_cleanup.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-31.
# Last Update by Hossein Sakkaki on 2026-08-31.
#

import logging

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from apps.content_safety.models import ContentSafetyJob
from apps.media_conversion.models import MediaConversionJob
from apps.media_conversion.services.storage_cleanup import (
    clean_storage_key,
    delete_job_output,
    delete_storage_key,
    delete_video_output,
)
from apps.posts.models.church_teaching import ChurchTeachingContent
from apps.subtitles.models import VideoTranscript


logger = logging.getLogger(__name__)


def _delete_field_file(field, *, label: str) -> None:
    if not field:
        return

    key = clean_storage_key(
        getattr(field, "name", None)
    )

    if not key:
        return

    storage = getattr(field, "storage", None)

    try:
        if key.lower().endswith(".m3u8"):
            delete_video_output(
                key,
                label=f"church-teaching.{label}.hls",
                storage=storage,
            )
        else:
            delete_storage_key(
                key,
                label=f"church-teaching.{label}",
                storage=storage,
            )

    except Exception:
        logger.exception(
            "church_teaching.cleanup.field_failed label=%s key=%s",
            label,
            key,
        )


def _cleanup_transcript(*, content_type, object_id: int) -> None:
    transcript = (
        VideoTranscript.objects
        .filter(
            content_type=content_type,
            object_id=object_id,
        )
        .first()
    )

    if transcript is None:
        return

    # Voice generation is prohibited for Organization teaching, but clean
    # unexpected legacy/corrupt rows defensively before deleting the transcript.
    for voice in transcript.voice_tracks.all():
        if voice.audio:
            _delete_field_file(
                voice.audio,
                label="unexpected-voice-track",
            )

    for track in transcript.subtitle_tracks.all():
        file_field = getattr(track, "file", None)
        if file_field:
            _delete_field_file(
                file_field,
                label="subtitle-track",
            )

    if transcript.stt_audio:
        _delete_field_file(
            transcript.stt_audio,
            label="stt-audio",
        )

    transcript.delete()


@receiver(
    post_delete,
    sender=ChurchTeachingContent,
    dispatch_uid="church.teaching.cleanup.media.delete.v1",
)
def church_teaching_cleanup_media_on_delete(
    sender,
    instance: ChurchTeachingContent,
    **kwargs,
):
    """Delete only storage generations owned by the deleted teaching object."""

    object_id = instance.pk

    def _cleanup():
        content_type = ContentType.objects.get_for_model(
            ChurchTeachingContent,
            for_concrete_model=False,
        )

        try:
            jobs_qs = MediaConversionJob.objects.filter(
                content_type=content_type,
                object_id=object_id,
            )

            jobs = list(jobs_qs)

            for job in jobs:
                delete_storage_key(
                    job.source_path,
                    label="church-teaching.job.source",
                )
                delete_job_output(
                    job.kind,
                    job.output_path,
                    label="church-teaching.job.output",
                )

            jobs_qs.delete()

        except Exception:
            logger.exception(
                "church_teaching.cleanup.media_jobs_failed object_id=%s",
                object_id,
            )

        try:
            ContentSafetyJob.objects.filter(
                content_type=content_type,
                object_id=object_id,
            ).delete()
        except Exception:
            logger.exception(
                "church_teaching.cleanup.safety_jobs_failed object_id=%s",
                object_id,
            )

        _delete_field_file(
            getattr(instance, "video", None),
            label="video",
        )
        _delete_field_file(
            getattr(instance, "thumbnail", None),
            label="thumbnail",
        )

        try:
            _cleanup_transcript(
                content_type=content_type,
                object_id=object_id,
            )
        except Exception:
            logger.exception(
                "church_teaching.cleanup.transcript_failed object_id=%s",
                object_id,
            )

    transaction.on_commit(_cleanup)
