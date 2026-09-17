# apps/audio_catalog/services/availability.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-01.
# Last Update by Hossein Sakkaki on 2026-09-15.

from __future__ import annotations

from dataclasses import dataclass

from django.utils import timezone

from apps.audio_catalog.models import MusicRightsRecord, MusicTrack
from .origin_policy import current_track_origin_availability


@dataclass(frozen=True)
class TrackAvailability:
    allowed: bool
    reason: str = ""


def _deny(reason: str) -> TrackAvailability:
    return TrackAvailability(False, reason)


def _rights_for(track):
    try:
        return track.rights
    except (MusicRightsRecord.DoesNotExist, AttributeError):
        return None


def _territory_allowed(rights, country_code: str) -> TrackAvailability:
    country = str(country_code or "").strip().upper()
    territories = {
        str(value).strip().upper()
        for value in (rights.territory_codes or [])
        if str(value).strip()
    }

    if rights.territory_mode == MusicRightsRecord.TerritoryMode.ALLOW_LIST:
        if not country:
            return _deny("Country is required for territory validation.")
        if country not in territories:
            return _deny("Territory is not licensed.")

    if (
        rights.territory_mode == MusicRightsRecord.TerritoryMode.DENY_LIST
        and country
        and country in territories
    ):
        return _deny("Territory is restricted.")

    return TrackAvailability(True)


def can_stream_track(
    track,
    country_code: str = "",
    at=None,
) -> TrackAvailability:
    now = at or timezone.now()

    if track.status != MusicTrack.Status.PUBLISHED:
        return _deny("Track is not published.")

    if track.published_at and track.published_at > now:
        return _deny("Track is not published yet.")

    if track.is_test_asset:
        return _deny("Test assets are not available.")

    if track.is_explicit:
        return _deny("Explicit tracks are not publicly available.")

    catalog = getattr(track, "catalog", None)
    if catalog is None or not getattr(catalog, "is_active", False):
        return _deny("Music catalog is not active.")

    if not track.allow_streaming:
        return _deny("Track streaming is disabled.")

    rights = _rights_for(track)
    if rights is None:
        return _deny("Rights record is missing.")

    if rights.status != MusicRightsRecord.Status.CLEARED:
        return _deny("Rights are not cleared.")

    if rights.effective_from and rights.effective_from > now:
        return _deny("Rights are not active yet.")

    if rights.effective_until and rights.effective_until <= now:
        return _deny("Rights have expired.")

    if not rights.streaming_allowed:
        return _deny("Streaming rights are missing.")

    territory = _territory_allowed(rights, country_code)
    if not territory.allowed:
        return territory

    origin = current_track_origin_availability(
        track=track,
        rights=rights,
        at=now,
    )
    if not origin.allowed:
        return _deny(origin.reason)

    return TrackAvailability(True)


def _has_primary_artwork(track) -> bool:
    return track.artworks.filter(
        is_primary=True,
        is_active=True,
        is_converted=True,
    ).exclude(image="").exists()


def _default_playback_variant(track):
    return (
        track.variants
        .filter(
            is_default=True,
            is_active=True,
            is_converted=True,
            is_streamable=True,
        )
        .exclude(audio_file="")
        .order_by("sort_order", "id")
        .first()
    )


def can_publish_track(
    track,
    country_code: str = "",
    at=None,
) -> TrackAvailability:
    result = can_stream_track(
        track,
        country_code=country_code,
        at=at,
    )
    if not result.allowed:
        return result

    if not _has_primary_artwork(track):
        return _deny("Primary artwork is not ready.")

    if _default_playback_variant(track) is None:
        return _deny("Default playback variant is not ready.")

    return TrackAvailability(True)


def can_use_track(
    track,
    country_code: str = "",
    at=None,
    require_external_export: bool = False,
) -> TrackAvailability:
    result = can_publish_track(
        track,
        country_code=country_code,
        at=at,
    )
    if not result.allowed:
        return result

    if not track.allow_ugc:
        return _deny("Track use in user content is disabled.")

    rights = _rights_for(track)

    required = (
        rights.ugc_use_allowed,
        rights.synchronization_allowed,
        rights.clipping_allowed,
        rights.hosting_allowed,
        rights.sublicensing_to_end_users_allowed,
    )
    if not all(required):
        return _deny("Required content-usage rights are missing.")

    if require_external_export and not rights.external_export_allowed:
        return _deny("External export is not allowed.")

    return TrackAvailability(True)


def can_download_track(
    track,
    variant=None,
    country_code: str = "",
    at=None,
) -> TrackAvailability:
    result = can_stream_track(
        track,
        country_code=country_code,
        at=at,
    )
    if not result.allowed:
        return result

    rights = _rights_for(track)

    if not track.allow_standalone_download:
        return _deny("Standalone download is disabled.")

    if not rights.standalone_download_allowed:
        return _deny("Standalone download rights are missing.")

    variant = variant or _default_playback_variant(track)
    if variant is None or not variant.is_downloadable:
        return _deny("This audio variant is not downloadable.")

    return TrackAvailability(True)


def can_offline_play_track(
    track,
    variant=None,
    country_code: str = "",
    at=None,
) -> TrackAvailability:
    result = can_stream_track(
        track,
        country_code=country_code,
        at=at,
    )
    if not result.allowed:
        return result

    rights = _rights_for(track)

    if not track.allow_offline_playback:
        return _deny("Offline playback is disabled.")

    if not rights.offline_playback_allowed:
        return _deny("Offline playback rights are missing.")

    variant = variant or _default_playback_variant(track)
    if variant is None or not variant.is_offline_eligible:
        return _deny("This audio variant is not available offline.")

    return TrackAvailability(True)