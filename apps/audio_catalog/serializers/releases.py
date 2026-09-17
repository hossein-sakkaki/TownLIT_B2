# apps/audio_catalog/serializers/releases.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-15.
# Last Update by Hossein Sakkaki on 2026-09-15.

from __future__ import annotations

from rest_framework import serializers

from apps.audio_catalog.models import (
    MusicRelease,
    MusicReleaseArtwork,
    MusicReleaseContributor,
    TrackContributor,
)
from apps.audio_catalog.selectors.releases import playable_release_tracks

from .catalog import (
    AudioContributorSerializer,
    CatalogSerializer,
    TrackListSerializer,
    asset_target,
)


def usable_release_artworks(release):
    prefetched = getattr(release, "public_artworks", None)

    if prefetched is not None:
        return list(prefetched)

    return list(
        release.artworks
        .filter(is_active=True, is_converted=True)
        .exclude(image="")
        .order_by("sort_order", "-is_primary", "id")
    )


def release_contributor_links(release):
    prefetched = getattr(release, "public_contributor_links", None)

    if prefetched is not None:
        return list(prefetched)

    return list(
        release.contributor_links
        .select_related("contributor")
        .order_by("sort_order", "role", "id")
    )


def primary_release_artist(release) -> str:
    link = next(
        (
            item
            for item in release_contributor_links(release)
            if item.role == TrackContributor.Role.PRIMARY_ARTIST
        ),
        None,
    )

    return (
        link.contributor.display_name
        if link is not None
        else "TownLIT Original"
    )


class ReleaseArtworkSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id")
    asset = serializers.SerializerMethodField()

    class Meta:
        model = MusicReleaseArtwork
        fields = (
            "id",
            "role",
            "label",
            "width",
            "height",
            "aspect_ratio",
            "dominant_color",
            "blurhash",
            "is_primary",
            "asset",
        )

    def get_asset(self, obj):
        return asset_target(obj, "image", "image")


class ReleaseCreditSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id")
    contributor = AudioContributorSerializer(read_only=True)

    class Meta:
        model = MusicReleaseContributor
        fields = (
            "id",
            "contributor",
            "role",
            "credit_text",
            "sort_order",
        )


class ReleaseTrackSerializer(TrackListSerializer):
    release_track_id = serializers.UUIDField(
        source="release_track_link_id",
        read_only=True,
    )
    disc_number = serializers.IntegerField(
        source="release_disc_number",
        read_only=True,
    )
    track_number = serializers.IntegerField(
        source="release_track_number",
        read_only=True,
    )

    class Meta(TrackListSerializer.Meta):
        fields = TrackListSerializer.Meta.fields + (
            "release_track_id",
            "disc_number",
            "track_number",
        )


class ReleaseListSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id")
    catalog = CatalogSerializer(read_only=True)
    artwork = serializers.SerializerMethodField()
    primary_artist = serializers.SerializerMethodField()

    class Meta:
        model = MusicRelease
        fields = (
            "id",
            "title",
            "slug",
            "subtitle",
            "release_type",
            "catalog",
            "primary_artist",
            "artwork",
            "language_code",
            "release_date",
            "version",
            "published_at",
        )

    def get_artwork(self, obj):
        artworks = usable_release_artworks(obj)

        artwork = next(
            (item for item in artworks if item.is_primary),
            artworks[0] if artworks else None,
        )

        if artwork is None:
            return None

        return ReleaseArtworkSerializer(
            artwork,
            context=self.context,
        ).data

    def get_primary_artist(self, obj):
        return primary_release_artist(obj)


class ReleaseDetailSerializer(ReleaseListSerializer):
    artworks = serializers.SerializerMethodField()
    credits = serializers.SerializerMethodField()
    tracks = serializers.SerializerMethodField()

    class Meta(ReleaseListSerializer.Meta):
        fields = ReleaseListSerializer.Meta.fields + (
            "description",
            "artworks",
            "credits",
            "tracks",
        )

    def get_artworks(self, obj):
        return ReleaseArtworkSerializer(
            usable_release_artworks(obj),
            many=True,
            context=self.context,
        ).data

    def get_credits(self, obj):
        return ReleaseCreditSerializer(
            release_contributor_links(obj),
            many=True,
            context=self.context,
        ).data

    def get_tracks(self, obj):
        return ReleaseTrackSerializer(
            playable_release_tracks(obj),
            many=True,
            context=self.context,
        ).data