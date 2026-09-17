# apps/audio_catalog/selectors/releases.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-15.
# Last Update by Hossein Sakkaki on 2026-09-15.

from __future__ import annotations

from django.db.models import Exists, F, OuterRef, Prefetch
from django.utils import timezone

from apps.audio_catalog.models import (
    MusicRelease,
    MusicReleaseArtwork,
    MusicReleaseContributor,
)
from apps.audio_catalog.querysets import published_tracks


def published_releases():
    now = timezone.now()

    artworks = (
        MusicReleaseArtwork.objects
        .filter(is_active=True, is_converted=True)
        .exclude(image="")
        .order_by("sort_order", "-is_primary", "id")
    )

    contributors = (
        MusicReleaseContributor.objects
        .select_related("contributor")
        .order_by("sort_order", "role", "id")
    )

    playable_track = (
        published_tracks()
        .filter(release_links__release_id=OuterRef("pk"))
        .values("pk")
    )

    return (
        MusicRelease.objects
        .filter(
            status=MusicRelease.Status.PUBLISHED,
            published_at__lte=now,
            release_date__lte=now.date(),
            catalog__is_active=True,
        )
        .annotate(has_playable_track=Exists(playable_track))
        .filter(has_playable_track=True)
        .select_related("catalog")
        .prefetch_related(
            Prefetch(
                "artworks",
                queryset=artworks,
                to_attr="public_artworks",
            ),
            Prefetch(
                "contributor_links",
                queryset=contributors,
                to_attr="public_contributor_links",
            ),
        )
        .order_by("-release_date", "-published_at", "-id")
    )


def playable_release_tracks(release):
    return (
        published_tracks()
        .filter(release_links__release=release)
        .annotate(
            release_track_link_id=F("release_links__public_id"),
            release_disc_number=F("release_links__disc_number"),
            release_track_number=F("release_links__track_number"),
        )
        .order_by(
            "release_disc_number",
            "release_track_number",
            "release_links__id",
        )
    )