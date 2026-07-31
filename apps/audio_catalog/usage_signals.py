# apps/audio_catalog/usage_signals.py

from __future__ import annotations

from django.db import transaction
from django.db.models.signals import (
    post_save,
    pre_save,
)
from django.dispatch import receiver

from apps.audio_catalog.models import (
    AudioUsageGrant,
)


@receiver(
    pre_save,
    sender=AudioUsageGrant,
)
def cache_previous_usage_grant_status(
    sender,
    instance,
    **kwargs,
):
    """
    Cache the previous status before saving.
    """

    if not instance.pk:
        instance._previous_usage_status = None
        return

    instance._previous_usage_status = (
        sender._base_manager
        .filter(
            pk=instance.pk,
        )
        .values_list(
            "status",
            flat=True,
        )
        .first()
    )


@receiver(
    post_save,
    sender=AudioUsageGrant,
)
def enqueue_usage_grant_analytics(
    sender,
    instance,
    created,
    **kwargs,
):
    """
    Queue activation or revocation analytics.
    """

    previous_status = getattr(
        instance,
        "_previous_usage_status",
        None,
    )

    current_status = instance.status

    became_active = (
        current_status
        == AudioUsageGrant.Status.ACTIVE
        and (
            created
            or previous_status
            != AudioUsageGrant.Status.ACTIVE
        )
    )

    left_active = (
        not created
        and previous_status
        == AudioUsageGrant.Status.ACTIVE
        and current_status
        in {
            AudioUsageGrant.Status.REVOKED,
            AudioUsageGrant.Status.REPLACED,
        }
    )

    if became_active:
        grant_id = instance.pk
        actor_id = instance.granted_to_id

        def enqueue_activation():
            from apps.audio_catalog.analytics.tasks import (
                process_audio_usage_grant_activated,
            )

            process_audio_usage_grant_activated.delay(
                grant_id=grant_id,
                actor_id=actor_id,
            )

        transaction.on_commit(
            enqueue_activation
        )

    if left_active:
        grant_id = instance.pk

        def enqueue_revocation():
            from apps.audio_catalog.analytics.tasks import (
                process_audio_usage_grant_revoked,
            )

            process_audio_usage_grant_revoked.delay(
                grant_id=grant_id,
            )

        transaction.on_commit(
            enqueue_revocation
        )