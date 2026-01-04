import logging
from django.db import transaction
from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver

from apps.posts.models.testimony import Testimony

logger = logging.getLogger(__name__)


def _safe_delete_fieldfile(field, label: str):
    """
    Deletes underlying object from storage (S3/local), safe-no-raise.
    """
    try:
        if not field:
            return
        name = getattr(field, "name", None)
        if not name:
            return

        field.delete(save=False)  # deletes from storage, doesn't touch DB
        logger.info("✅ Testimony media deleted (%s): %s", label, name)
    except Exception:
        logger.exception(
            "❌ Failed deleting Testimony media (%s): %s",
            label,
            getattr(field, "name", None),
        )


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


@receiver(post_delete, sender=Testimony, dispatch_uid="testimony.cleanup.media.delete.v1")
def testimony_cleanup_media_on_delete(sender, instance: Testimony, **kwargs):
    """
    When a Testimony row is deleted, also delete its media files from storage (S3).
    """
    def _cleanup():
        _safe_delete_fieldfile(getattr(instance, "audio", None), "audio")
        _safe_delete_fieldfile(getattr(instance, "video", None), "video")
        _safe_delete_fieldfile(getattr(instance, "thumbnail", None), "thumbnail")

    transaction.on_commit(_cleanup)
