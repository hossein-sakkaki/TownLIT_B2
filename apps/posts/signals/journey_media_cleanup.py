# apps/posts/signals/journey_media_cleanup.py

from __future__ import annotations

import logging

from django.db import transaction
from django.db.models.signals import post_delete, pre_delete
from django.dispatch import receiver

from apps.posts.models.journey import JourneyEntry
from apps.posts.services.journeys.audio_usage import revoke_journey_audio_usage
from apps.posts.services.journeys.storage import delete_storage_asset


logger = logging.getLogger(__name__)


@receiver(
    pre_delete,
    sender=JourneyEntry,
    dispatch_uid="journey.cleanup.audio.revoke.v1",
)
def journey_entry_revoke_audio_before_delete(
    sender,
    instance: JourneyEntry,
    **kwargs,
):
    """
    Revoke active music grants before deleting the entry.
    """

    try:
        revoke_journey_audio_usage(
            entry=instance,
            reason="Journey entry was deleted.",
        )
    except Exception:
        logger.exception(
            "Failed revoking Journey audio grants: entry=%s",
            instance.pk,
        )

        # Do not delete content while an active grant may remain.
        raise


@receiver(
    post_delete,
    sender=JourneyEntry,
    dispatch_uid="journey.cleanup.media.delete.v2",
)
def journey_entry_cleanup_media(
    sender,
    instance: JourneyEntry,
    **kwargs,
):
    """
    Delete immutable Journey media after DB commit.
    """

    rendered_key = getattr(instance.rendered_image, "name", "")
    thumbnail_key = getattr(instance.thumbnail, "name", "")

    def cleanup():
        delete_storage_asset(rendered_key)
        delete_storage_asset(thumbnail_key)

    transaction.on_commit(cleanup)


