# apps/audio_catalog/services/origin_policy.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-01.
# Last Update by Hossein Sakkaki on 2026-09-01.
#

from dataclasses import dataclass


@dataclass(frozen=True)
class TrackOriginAvailability:
    allowed: bool
    reason: str = ""


def current_track_origin_availability(*, track, rights, at=None):
    restrictions = rights.restrictions if isinstance(rights.restrictions, dict) else {}
    origin = restrictions.get("townlit_origin")
    if not isinstance(origin, dict) or origin.get("type") != "organization_contribution":
        return TrackOriginAvailability(True)
    try:
        from apps.organizations.modules.worship.services.availability import validate_organization_music_origin
        result = validate_organization_music_origin(track=track, rights=rights, origin=origin, at=at)
    except Exception:
        return TrackOriginAvailability(False, "Organization music origin validation failed.")
    return TrackOriginAvailability(bool(result.allowed), result.reason)
