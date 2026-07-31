# apps/audio_catalog/services/availability.py

from __future__ import annotations

from dataclasses import dataclass

from django.utils import timezone

from apps.audio_catalog.models import (
    MusicRightsRecord,
    MusicTrack,
)


@dataclass(frozen=True)
class TrackAvailability:
    allowed: bool
    reason: str = ""


def can_use_track(
    track,
    country_code: str = "",
    at=None,
    require_external_export: bool = False,
) -> TrackAvailability:
    """
    Validate whether a track may be assigned to content.
    """

    now = at or timezone.now()

    # -------------------------------------------------
    # Track availability
    # -------------------------------------------------
    if track.status != MusicTrack.Status.PUBLISHED:
        return TrackAvailability(
            False,
            "Track is not published.",
        )

    if track.is_test_asset:
        return TrackAvailability(
            False,
            "Test assets are not available.",
        )

    catalog = getattr(
        track,
        "catalog",
        None,
    )

    if (
        catalog is None
        or not getattr(
            catalog,
            "is_active",
            False,
        )
    ):
        return TrackAvailability(
            False,
            "Music catalog is not active.",
        )

    if (
        not track.allow_ugc
        or not track.allow_streaming
    ):
        return TrackAvailability(
            False,
            "Track use is restricted.",
        )

    # -------------------------------------------------
    # Required assets
    # -------------------------------------------------
    primary_artwork_ready = (
        track.artworks
        .filter(
            is_primary=True,
            is_active=True,
            is_converted=True,
        )
        .exists()
    )

    if not primary_artwork_ready:
        return TrackAvailability(
            False,
            "Primary artwork is not ready.",
        )

    default_variant_ready = (
        track.variants
        .filter(
            is_default=True,
            is_active=True,
            is_converted=True,
            is_streamable=True,
        )
        .exists()
    )

    if not default_variant_ready:
        return TrackAvailability(
            False,
            "Default playback variant is not ready.",
        )

    # -------------------------------------------------
    # Rights
    # -------------------------------------------------
    try:
        rights = track.rights

    except MusicRightsRecord.DoesNotExist:
        return TrackAvailability(
            False,
            "Rights record is missing.",
        )

    if (
        rights.status
        != MusicRightsRecord.Status.CLEARED
    ):
        return TrackAvailability(
            False,
            "Rights are not cleared.",
        )

    if (
        rights.effective_from
        and rights.effective_from > now
    ):
        return TrackAvailability(
            False,
            "Rights are not active yet.",
        )

    if (
        rights.effective_until
        and rights.effective_until <= now
    ):
        return TrackAvailability(
            False,
            "Rights have expired.",
        )

    required_rights = (
        rights.ugc_use_allowed,
        rights.streaming_allowed,
        rights.synchronization_allowed,
        rights.clipping_allowed,
        rights.hosting_allowed,
        rights.sublicensing_to_end_users_allowed,
    )

    if not all(required_rights):
        return TrackAvailability(
            False,
            "Required usage rights are missing.",
        )

    if (
        require_external_export
        and not rights.external_export_allowed
    ):
        return TrackAvailability(
            False,
            "External export is not allowed.",
        )

    # -------------------------------------------------
    # Territory
    # -------------------------------------------------
    country = str(
        country_code or ""
    ).strip().upper()

    territories = {
        str(value).strip().upper()
        for value in (
            rights.territory_codes
            or []
        )
        if str(value).strip()
    }

    if (
        rights.territory_mode
        == MusicRightsRecord
        .TerritoryMode.ALLOW_LIST
    ):
        if not country:
            return TrackAvailability(
                False,
                "Country is required for territory validation.",
            )

        if country not in territories:
            return TrackAvailability(
                False,
                "Territory is not licensed.",
            )

    if (
        rights.territory_mode
        == MusicRightsRecord
        .TerritoryMode.DENY_LIST
        and country
        and country in territories
    ):
        return TrackAvailability(
            False,
            "Territory is restricted.",
        )

    return TrackAvailability(
        True,
    )