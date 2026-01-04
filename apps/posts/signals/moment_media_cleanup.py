import logging
from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from apps.posts.models.moment import Moment

logger = logging.getLogger(__name__)


def _safe_delete_filefield(field, label: str):
    """
    Delete a FileField/ImageField from its storage (S3/local).
    Safe: no raise if missing or delete fails.
    """
    try:
        if not field:
            return
        name = getattr(field, "name", None)
        if not name:
            return

        # Deletes the underlying storage object (S3 key), not just DB pointer
        field.delete(save=False)

        logger.info("✅ Moment media deleted (%s): %s", label, name)
    except Exception:
        logger.exception("❌ Failed deleting Moment media (%s): %s", label, getattr(field, "name", None))


@receiver(post_delete, sender=Moment, dispatch_uid="moment.cleanup.media.v1")
def moment_cleanup_media_on_delete(sender, instance: Moment, **kwargs):
    """
    When a Moment row is deleted, also delete its media files from storage (S3).
    Use on_commit so if DB rollback happens, we won't delete S3 objects wrongly.
    """

    def _cleanup():
        _safe_delete_filefield(getattr(instance, "image", None), "image")
        _safe_delete_filefield(getattr(instance, "video", None), "video")
        _safe_delete_filefield(getattr(instance, "thumbnail", None), "thumbnail")

    transaction.on_commit(_cleanup)
