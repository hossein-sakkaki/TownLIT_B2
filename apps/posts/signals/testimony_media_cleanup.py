# apps/posts/signals/testimony_media_cleanup.py

import logging
import os

from django.db import transaction
from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from apps.media_conversion.models import MediaConversionJob
from django.core.files.storage import default_storage
from apps.posts.models.testimony import Testimony
from apps.subtitles.models import VideoTranscript

logger = logging.getLogger(__name__)


# ---------------------------------------------------------
# Helper: delete a FileField from its storage (S3/local).
# Safe: no raise if missing or delete fails.
# ---------------------------------------------------------
def _safe_delete_fieldfile(field, label: str):
    try:
        if not field:
            return
        name = getattr(field, "name", None)
        if not name:
            return

        storage = getattr(field, "storage", None)
        key = str(name).lstrip("/")

        # 1) delete the file itself (playlist/mp3/jpg/etc.)
        field.delete(save=False)
        logger.info("✅ Testimony media deleted (%s): %s", label, key)

        # 2) if this is HLS master, also delete its folder (segments + variants)
        if label == "video" and key.lower().endswith(".m3u8") and storage:
            prefix = os.path.dirname(key)  # folder containing m3u8 + ts
            _safe_delete_prefix(storage, prefix, "video-hls")

    except Exception:
        logger.exception("❌ Failed deleting Testimony media (%s): %s", label, getattr(field, "name", None))

# ---------------------------------------------------------
# Helper: delete ALL objects under a prefix on S3.
# ---------------------------------------------------------
def _safe_delete_prefix(storage, prefix: str, label: str):
    """
    Delete ALL objects under prefix on S3 (best-effort).
    Requires S3 permissions: s3:ListBucket + s3:DeleteObject/DeleteObjects
    """
    try:
        if not prefix:
            return

        # normalize
        prefix = prefix.lstrip("/")
        if not prefix.endswith("/"):
            prefix += "/"

        bucket = getattr(storage, "bucket", None)
        if not bucket:
            # not S3 storage (or no bucket handle)
            return

        # delete everything under that prefix
        bucket.objects.filter(Prefix=prefix).delete()
        logger.info("✅ Deleted S3 prefix (%s): %s", label, prefix)

    except Exception:
        logger.exception("❌ Failed deleting S3 prefix (%s): %s", label, prefix)


# ---------------------------------------------------------
# Helper: delete a key from its storage (S3/local).
# ---------------------------------------------------------
def _safe_delete_storage_key(key: str, label: str):
    try:
        if not key:
            return
        key = str(key).lstrip("/")
        if default_storage.exists(key):
            default_storage.delete(key)
            logger.info("✅ Deleted storage key (%s): %s", label, key)
    except Exception:
        logger.exception("❌ Failed deleting storage key (%s): %s", label, key)


def _cleanup_subtitles_for_testimony(testimony):
    try:
        ct = ContentType.objects.get_for_model(Testimony)

        transcript = VideoTranscript.objects.filter(
            content_type=ct,
            object_id=testimony.pk,
        ).first()

        if not transcript:
            return

        # -------------------------------------------------
        # 1) Delete VoiceTrack audio files (TTS)
        # -------------------------------------------------
        for voice in transcript.voice_tracks.all():
            if voice.audio:
                _safe_delete_fieldfile(voice.audio, "voice-track-audio")

        # -------------------------------------------------
        # 2) (Future-proof) subtitle files if stored as FileField
        # -------------------------------------------------
        for track in transcript.subtitle_tracks.all():
            if hasattr(track, "file") and track.file:
                _safe_delete_fieldfile(track.file, "subtitle-track")

        # -------------------------------------------------
        # 3) STT source audio
        # -------------------------------------------------
        if transcript.stt_audio:
            _safe_delete_fieldfile(transcript.stt_audio, "stt-audio")

        # -------------------------------------------------
        # 4) Delete transcript (segments + tracks cascade)
        # -------------------------------------------------
        transcript.delete()

        logger.info("✅ Deleted transcript + subtitles + voices for testimony %s", testimony.pk)

    except Exception:
        logger.exception("❌ Failed cleaning subtitles/voices for testimony %s", testimony.pk)



# ---------------------------------------------------------
# Signal handlers
# ---------------------------------------------------------
@receiver(pre_save, sender=Testimony, dispatch_uid="testimony.cleanup.media.replace.v1")
def testimony_cleanup_media_on_replace(sender, instance: Testimony, **kwargs):
    """
    If a media field is replaced (audio/video/thumbnail), delete the old file
    AFTER the DB commit (so we don't delete on failed save).
    """
    if not instance.pk:
        return

    try:
        old = Testimony.objects.filter(pk=instance.pk).first()
        if not old:
            return

        to_delete = []

        # audio replaced or cleared
        old_audio = getattr(old.audio, "name", None)
        new_audio = getattr(instance.audio, "name", None)
        if old_audio and old_audio != new_audio:
            to_delete.append(("audio", old.audio))

        # video replaced or cleared
        old_video = getattr(old.video, "name", None)
        new_video = getattr(instance.video, "name", None)
        if old_video and old_video != new_video:
            to_delete.append(("video", old.video))

        # thumbnail replaced or cleared
        old_thumb = getattr(old.thumbnail, "name", None)
        new_thumb = getattr(instance.thumbnail, "name", None)
        if old_thumb and old_thumb != new_thumb:
            to_delete.append(("thumbnail", old.thumbnail))

        if not to_delete:
            return

        def _cleanup():
            for label, field in to_delete:
                _safe_delete_fieldfile(field, label)

        transaction.on_commit(_cleanup)

    except Exception:
        logger.exception("🔥 Testimony pre_save cleanup failed")


# ---------------------------------------------------------
# Signal handlers (DELETE)
# ---------------------------------------------------------
@receiver(post_delete, sender=Testimony, dispatch_uid="testimony.cleanup.media.delete.v1")
def testimony_cleanup_media_on_delete(sender, instance: Testimony, **kwargs):

    def _cleanup():
        # ✅ 0) delete RAW/output paths recorded in MediaConversionJob (if any)
        try:
            ct = ContentType.objects.get_for_model(Testimony)
            jobs_qs = MediaConversionJob.objects.filter(content_type=ct, object_id=instance.pk)
            jobs = list(jobs_qs)  # freeze before delete

            for job in jobs: 
                # raw source
                if job.source_path:
                    _safe_delete_storage_key(job.source_path, label="job.source")

                # output directory (HLS folder etc.)
                if job.output_path:
                    out = (job.output_path or "").lstrip("/")
                    if out:
                        if os.path.splitext(out)[1]:
                            prefix = os.path.dirname(out)
                        else:
                            prefix = out.rstrip("/")
                        if prefix:
                            _safe_delete_prefix(default_storage, prefix, "job.output-prefix")

            # ✅ finally: cleanup DB rows
            jobs_qs.delete()
            logger.info("✅ Deleted MediaConversionJob rows for testimony %s", instance.pk)

        except Exception:
            logger.exception("❌ Failed deleting MediaConversionJob paths for testimony %s", instance.pk)

        # ✅ 1) delete model-linked fields
        _safe_delete_fieldfile(getattr(instance, "audio", None), "audio")
        _safe_delete_fieldfile(getattr(instance, "video", None), "video")
        _safe_delete_fieldfile(getattr(instance, "thumbnail", None), "thumbnail")

        # ✅ 2) cleanup subtitles + transcript
        _cleanup_subtitles_for_testimony(instance)
        
    transaction.on_commit(_cleanup)
