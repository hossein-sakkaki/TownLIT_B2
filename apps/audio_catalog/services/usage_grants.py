# apps/audio_catalog/services/usage_grants.py

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.audio_catalog.models import (
    AudioUsageGrant,
)


@transaction.atomic
def revoke_audio_usage_grant(
    *,
    grant: AudioUsageGrant,
    reason: str = "",
) -> AudioUsageGrant:
    """
    Revoke one active usage grant safely.
    """

    locked = (
        AudioUsageGrant.objects
        .select_for_update()
        .get(
            pk=grant.pk,
        )
    )

    if (
        locked.status
        != AudioUsageGrant.Status.ACTIVE
    ):
        return locked

    locked.status = (
        AudioUsageGrant.Status.REVOKED
    )

    locked.revoked_at = timezone.now()

    locked.revoke_reason = (
        reason
        or ""
    )[:240]

    locked.save(
        update_fields=[
            "status",
            "revoked_at",
            "revoke_reason",
            "updated_at",
        ]
    )

    return locked


@transaction.atomic
def replace_audio_usage_grant(
    *,
    grant: AudioUsageGrant,
    reason: str = "",
) -> AudioUsageGrant:
    """
    Mark one active usage grant as replaced.
    """

    locked = (
        AudioUsageGrant.objects
        .select_for_update()
        .get(
            pk=grant.pk,
        )
    )

    if (
        locked.status
        != AudioUsageGrant.Status.ACTIVE
    ):
        return locked

    locked.status = (
        AudioUsageGrant.Status.REPLACED
    )

    locked.revoked_at = timezone.now()

    locked.revoke_reason = (
        reason
        or "Replaced by another music grant."
    )[:240]

    locked.save(
        update_fields=[
            "status",
            "revoked_at",
            "revoke_reason",
            "updated_at",
        ]
    )

    return locked