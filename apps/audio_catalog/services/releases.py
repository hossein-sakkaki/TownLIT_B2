# apps/audio_catalog/services/releases.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-15.
# Last Update by Hossein Sakkaki on 2026-09-15.

from __future__ import annotations

from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.audio_catalog.models import (
    MusicRelease,
    MusicReleaseTrack,
    TrackContributor,
)
from apps.audio_catalog.querysets import published_tracks


class ReleaseReadinessCode:
    INVALID_STATUS = "invalid_status"
    MISSING_RELEASE_DATE = "missing_release_date"
    INACTIVE_CATALOG = "inactive_catalog"
    NO_TRACKS = "no_tracks"
    SINGLE_TRACK_COUNT = "single_track_count"
    TRACK_CATALOG_MISMATCH = "track_catalog_mismatch"
    TRACK_NOT_AVAILABLE = "track_not_available"
    MISSING_PRIMARY_ARTWORK = "missing_primary_artwork"
    MISSING_PRIMARY_ARTIST = "missing_primary_artist"


READINESS_MESSAGES = {
    ReleaseReadinessCode.INVALID_STATUS:
        "Only Draft or Review releases can be published.",
    ReleaseReadinessCode.MISSING_RELEASE_DATE:
        "Release date is required.",
    ReleaseReadinessCode.INACTIVE_CATALOG:
        "Audio Catalog is not active.",
    ReleaseReadinessCode.NO_TRACKS:
        "Release must contain at least one track.",
    ReleaseReadinessCode.SINGLE_TRACK_COUNT:
        "A Single release must contain exactly one track.",
    ReleaseReadinessCode.TRACK_CATALOG_MISMATCH:
        "All release tracks must belong to the release Audio Catalog.",
    ReleaseReadinessCode.TRACK_NOT_AVAILABLE:
        "All release tracks must be currently available for playback.",
    ReleaseReadinessCode.MISSING_PRIMARY_ARTWORK:
        "Release requires a converted active primary artwork.",
    ReleaseReadinessCode.MISSING_PRIMARY_ARTIST:
        "Release requires at least one primary artist credit.",
}


@dataclass(frozen=True)
class MusicReleaseReadiness:
    blockers: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return not self.blockers

    @property
    def messages(self) -> tuple[str, ...]:
        return tuple(
            READINESS_MESSAGES.get(code, code)
            for code in self.blockers
        )


def _release_track_links(release):
    return list(
        release.track_links
        .select_related("track")
        .order_by("disc_number", "track_number", "id")
    )


def _available_track_ids(track_ids):
    if not track_ids:
        return set()

    return set(
        published_tracks()
        .filter(pk__in=track_ids)
        .values_list("pk", flat=True)
    )


def _has_primary_artwork(release) -> bool:
    return (
        release.artworks
        .filter(
            is_primary=True,
            is_active=True,
            is_converted=True,
            primary_slot=1,
        )
        .exclude(image="")
        .exists()
    )


def _has_primary_artist(release) -> bool:
    return release.contributor_links.filter(
        role=TrackContributor.Role.PRIMARY_ARTIST,
    ).exists()


def evaluate_music_release_readiness(release) -> MusicReleaseReadiness:
    blockers = []

    if release.status not in {
        MusicRelease.Status.DRAFT,
        MusicRelease.Status.REVIEW,
    }:
        blockers.append(ReleaseReadinessCode.INVALID_STATUS)

    if release.release_date is None:
        blockers.append(ReleaseReadinessCode.MISSING_RELEASE_DATE)

    if not getattr(release.catalog, "is_active", False):
        blockers.append(ReleaseReadinessCode.INACTIVE_CATALOG)

    links = _release_track_links(release)

    if not links:
        blockers.append(ReleaseReadinessCode.NO_TRACKS)
        return MusicReleaseReadiness(tuple(blockers))

    if (
        release.release_type == MusicRelease.ReleaseType.SINGLE
        and len(links) != 1
    ):
        blockers.append(ReleaseReadinessCode.SINGLE_TRACK_COUNT)

    if any(link.track.catalog_id != release.catalog_id for link in links):
        blockers.append(ReleaseReadinessCode.TRACK_CATALOG_MISMATCH)

    track_ids = [link.track_id for link in links]
    available_ids = _available_track_ids(track_ids)

    if any(track_id not in available_ids for track_id in track_ids):
        blockers.append(ReleaseReadinessCode.TRACK_NOT_AVAILABLE)

    if not _has_primary_artwork(release):
        blockers.append(ReleaseReadinessCode.MISSING_PRIMARY_ARTWORK)

    if not _has_primary_artist(release):
        blockers.append(ReleaseReadinessCode.MISSING_PRIMARY_ARTIST)

    return MusicReleaseReadiness(tuple(blockers))


def _publish_music_release_instance(release, *, actor=None):
    if release.status == MusicRelease.Status.PUBLISHED:
        return release

    readiness = evaluate_music_release_readiness(release)

    if not readiness.ready:
        raise ValidationError({"release": list(readiness.messages)})

    release.status = MusicRelease.Status.PUBLISHED
    release.published_at = release.published_at or timezone.now()
    release.suspended_at = None
    release.archived_at = None
    release.updated_by = actor

    release.clean()
    release.save(
        update_fields=(
            "status",
            "published_at",
            "suspended_at",
            "archived_at",
            "updated_by",
            "updated_at",
        )
    )

    return release


@transaction.atomic
def publish_music_release(*, release, actor=None):
    locked = (
        MusicRelease.objects
        .select_for_update()
        .select_related("catalog")
        .get(pk=release.pk)
    )

    if locked.status == MusicRelease.Status.PUBLISHED:
        return locked

    # Stabilize the current ordered membership while publishing.
    list(
        MusicReleaseTrack.objects
        .select_for_update()
        .filter(release=locked)
        .values_list("pk", flat=True)
    )

    return _publish_music_release_instance(
        locked,
        actor=actor,
    )