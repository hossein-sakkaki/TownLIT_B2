# apps/posts/signals/testimony_media_cleanup.py

import logging

from django.db import transaction
from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType

from apps.media_conversion.models import MediaConversionJob
from apps.media_conversion.services.storage_cleanup import (
    clean_storage_key,
    delete_job_output,
    delete_storage_key,
    delete_video_output,
)
from apps.posts.models.testimony import Testimony
from apps.subtitles.models import VideoTranscript

logger = logging.getLogger(__name__)


def _safe_delete_fieldfile(field, label: str):
    try:
        if not field:
            return

        key = clean_storage_key(getattr(field, "name", None))
        storage = getattr(field, "storage", None)

        if not key:
            return

        if label == "video" and key.lower().endswith(".m3u8"):
            delete_video_output(
                key,
                label="testimony.video-hls",
                storage=storage,
            )
        else:
            delete_storage_key(
                key,
                label=f"testimony.{label}",
                storage=storage,
            )

    except Exception:
        logger.exception(
            "❌ Failed deleting Testimony media (%s): %s",
            label,
            getattr(field, "name", None),
        )


def _cleanup_subtitles_for_testimony(testimony):
    try:
        ct = ContentType.objects.get_for_model(Testimony)

        transcript = VideoTranscript.objects.filter(
            content_type=ct,
            object_id=testimony.pk,
        ).first()

        if not transcript:
            return

        for voice in transcript.voice_tracks.all():
            if voice.audio:
                _safe_delete_fieldfile(
                    voice.audio,
                    "voice-track-audio",
                )

        for track in transcript.subtitle_tracks.all():
            if hasattr(track, "file") and track.file:
                _safe_delete_fieldfile(
                    track.file,
                    "subtitle-track",
                )

        if transcript.stt_audio:
            _safe_delete_fieldfile(
                transcript.stt_audio,
                "stt-audio",
            )

        transcript.delete()

    except Exception:
        logger.exception(
            "❌ Failed cleaning subtitles/voices for testimony %s",
            testimony.pk,
        )


@receiver(
    pre_save,
    sender=Testimony,
    dispatch_uid="testimony.cleanup.media.replace.v2",
)
def testimony_cleanup_media_on_replace(sender, instance: Testimony, **kwargs):
    if not instance.pk:
        return

    try:
        old = Testimony.objects.filter(pk=instance.pk).first()

        if not old:
            return

        to_delete = []

        old_audio = getattr(old.audio, "name", None)
        new_audio = getattr(instance.audio, "name", None)
        if old_audio and old_audio != new_audio:
            to_delete.append(("audio", old.audio))

        old_video = getattr(old.video, "name", None)
        new_video = getattr(instance.video, "name", None)
        if old_video and old_video != new_video:
            to_delete.append(("video", old.video))

        old_thumb = getattr(old.thumbnail, "name", None)
        new_thumb = getattr(instance.thumbnail, "name", None)
        if old_thumb and old_thumb != new_thumb:
            to_delete.append(("thumbnail", old.thumbnail))

        old_artwork = getattr(old.audio_artwork, "name", None)
        new_artwork = getattr(instance.audio_artwork, "name", None)

        if old_artwork and old_artwork != new_artwork:
            to_delete.append(("audio-artwork", old.audio_artwork))

        if not to_delete:
            return

        def _cleanup():
            for label, field in to_delete:
                _safe_delete_fieldfile(field, label)

        transaction.on_commit(_cleanup)

    except Exception:
        logger.exception("🔥 Testimony pre_save cleanup failed")


@receiver(
    post_delete,
    sender=Testimony,
    dispatch_uid="testimony.cleanup.media.delete.v2",
)
def testimony_cleanup_media_on_delete(sender, instance: Testimony, **kwargs):
    def _cleanup():
        try:
            ct = ContentType.objects.get_for_model(Testimony)

            jobs_qs = MediaConversionJob.objects.filter(
                content_type=ct,
                object_id=instance.pk,
            )

            jobs = list(jobs_qs)

            for job in jobs:
                delete_storage_key(
                    job.source_path,
                    label="testimony.job.source",
                )

                delete_job_output(
                    job.kind,
                    job.output_path,
                    label="testimony.job.output",
                )

            jobs_qs.delete()

        except Exception:
            logger.exception(
                "❌ Failed deleting MediaConversionJob paths for testimony %s",
                instance.pk,
            )

        _safe_delete_fieldfile(
            getattr(instance, "audio", None),
            "audio",
        )
        _safe_delete_fieldfile(
            getattr(instance, "video", None),
            "video",
        )
        _safe_delete_fieldfile(
            getattr(instance, "thumbnail", None),
            "thumbnail",
        )
        _safe_delete_fieldfile(
            getattr(instance, "audio_artwork", None),
            "audio-artwork",
        )

        _cleanup_subtitles_for_testimony(instance)

    transaction.on_commit(_cleanup)