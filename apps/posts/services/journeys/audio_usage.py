# apps/posts/services/journeys/audio_usage.py

from __future__ import annotations

from django.contrib.contenttypes.models import ContentType

from apps.audio_catalog.models import AudioUsageGrant
from apps.audio_catalog.services.usage_grants import (
    revoke_audio_usage_grant,
)


def journey_audio_usage_grants(
    *,
    entry,
):
    """
    Return all audio grants for one Journey entry.
    """

    if not entry or not entry.pk:
        return AudioUsageGrant.objects.none()

    content_type = ContentType.objects.get_for_model(
        entry,
        for_concrete_model=False,
    )

    return AudioUsageGrant.objects.filter(
        content_type=content_type,
        object_id=entry.pk,
    )


def revoke_journey_audio_usage(
    *,
    entry,
    reason: str,
) -> list[AudioUsageGrant]:
    """
    Revoke active grants while preserving audit records.
    """

    active_grants = list(
        journey_audio_usage_grants(entry=entry)
        .filter(
            status=AudioUsageGrant.Status.ACTIVE,
        )
        .order_by("id")
    )

    revoked = []

    for grant in active_grants:
        revoked.append(
            revoke_audio_usage_grant(
                grant=grant,
                reason=reason,
            )
        )

    return revoked