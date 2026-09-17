# apps/audio_catalog/services/origin_policy.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-01.
# Last Update by Hossein Sakkaki on 2026-09-07.
#

from dataclasses import dataclass

from django.core.exceptions import ObjectDoesNotExist


@dataclass(frozen=True)
class TrackOriginAvailability:
    allowed: bool
    reason: str = ""


def current_track_origin_availability(
    *,
    track,
    rights,
    at=None,
):
    try:
        contribution = track.organization_music_contribution
    except ObjectDoesNotExist:
        contribution = None

    # Non-Organization tracks keep the existing Audio Catalog behavior.
    if contribution is None:
        return TrackOriginAvailability(True)

    try:
        from apps.organizations.modules.worship.services.availability import (
            validate_organization_music_origin,
        )

        result = validate_organization_music_origin(
            track=track,
            rights=rights,
            contribution=contribution,
            at=at,
        )
    except Exception:
        return TrackOriginAvailability(
            False,
            "Organization music origin validation failed.",
        )

    return TrackOriginAvailability(
        bool(result.allowed),
        result.reason,
    )