# apps/audio_catalog/serializers/catalog.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-14.
# Last Update by Hossein Sakkaki on 2026-09-17.

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from rest_framework.reverse import reverse
from rest_framework import serializers

from apps.audio_catalog.models import (
    AudioCatalog,
    AudioContributor,
    MusicArtwork,
    MusicRightsRecord,
    MusicTrack,
    MusicTrackVariant,
    TrackContributor,
)



TRENDING_SCORE_QUANTUM = Decimal("0.000001")


def asset_target(
    obj,
    field_name: str,
    kind: str,
) -> dict:
    """
    Build an Asset Delivery target.
    """

    return {
        "app_label": obj._meta.app_label,
        "model": obj._meta.model_name,
        "object_id": obj.pk,
        "field_name": field_name,
        "kind": kind,
    }


def normalize_trending_score(
    value,
) -> Decimal:
    """
    Normalize every score to the public six-decimal contract.
    """

    if value is None:
        return Decimal("0.000000")

    try:
        decimal_value = Decimal(
            str(value)
        )
    except (
        InvalidOperation,
        TypeError,
        ValueError,
    ):
        return Decimal("0.000000")

    if not decimal_value.is_finite():
        return Decimal("0.000000")

    return decimal_value.quantize(
        TRENDING_SCORE_QUANTUM,
        rounding=ROUND_HALF_UP,
    )


def usable_track_artworks(
    track,
) -> list[MusicArtwork]:
    """
    Return artwork records that can be delivered to clients.
    """

    return [
        artwork
        for artwork in track.artworks.all()
        if artwork.image
    ]


def usable_track_variants(
    track,
) -> list[MusicTrackVariant]:
    """
    Return playback variants that are ready for client use.
    """

    return [
        variant
        for variant in track.variants.all()
        if (
            variant.is_active
            and variant.is_converted
            and variant.is_streamable
            and variant.audio_file
        )
    ]


def primary_track_artwork(
    track,
) -> MusicArtwork | None:
    """
    Resolve one deterministic primary artwork.
    """

    artworks = usable_track_artworks(
        track
    )

    primary = next(
        (
            artwork
            for artwork in artworks
            if artwork.is_primary
        ),
        None,
    )

    if primary is not None:
        return primary

    return (
        artworks[0]
        if artworks
        else None
    )


def default_track_variant(
    track,
) -> MusicTrackVariant | None:
    """
    Resolve one deterministic playable variant.
    """

    variants = usable_track_variants(
        track
    )

    default_variant = next(
        (
            variant
            for variant in variants
            if variant.is_default
        ),
        None,
    )

    if default_variant is not None:
        return default_variant

    if not variants:
        return None

    return min(
        variants,
        key=lambda variant: (
            variant.sort_order,
            variant.id,
        ),
    )


def primary_track_artist(
    track,
) -> str:
    """
    Resolve the primary artist without additional queries.
    """

    link = next(
        (
            item
            for item in track.contributor_links.all()
            if (
                item.role
                == TrackContributor.Role.PRIMARY_ARTIST
            )
        ),
        None,
    )

    if link is None:
        return "TownLIT Original"

    return link.contributor.display_name


def track_rights(
    track,
) -> MusicRightsRecord | None:
    """
    Resolve the track rights record safely.
    """

    try:
        return track.rights
    except MusicRightsRecord.DoesNotExist:
        return None


def track_offline_available(
    track,
) -> bool:
    """
    Resolve whether the default playback variant may be stored
    privately for in-app offline playback.

    ALLOW_LIST territory rights fail closed until Asset Delivery
    receives country context for offline requests.
    """

    variant = default_track_variant(
        track
    )
    rights = track_rights(
        track
    )

    if variant is None or rights is None:
        return False

    if (
        rights.territory_mode
        == MusicRightsRecord.TerritoryMode.ALLOW_LIST
    ):
        return False

    return bool(
        track.allow_offline_playback
        and rights.status
        == MusicRightsRecord.Status.CLEARED
        and rights.streaming_allowed
        and rights.offline_playback_allowed
        and variant.is_offline_eligible
    )


def track_engagement_payload(
    track,
) -> dict:
    """
    Build one canonical engagement payload for every endpoint.
    """

    metric = getattr(
        track,
        "analytics_metric",
        None,
    )

    resolved_score = getattr(
        track,
        "resolved_trending_score",
        None,
    )

    if metric is None:
        return {
            "qualified_plays": 0,
            "usages": 0,
            "trending_score":
                normalize_trending_score(
                    resolved_score
                ),
        }

    if resolved_score is None:
        resolved_score = (
            metric.trending_score
        )

    return {
        "qualified_plays":
            int(
                metric.total_qualified_plays
                or 0
            ),
        "usages":
            int(
                metric.total_usages
                or 0
            ),
        "trending_score":
            normalize_trending_score(
                resolved_score
            ),
    }


def track_share_reference(
    track,
) -> dict | None:
    """
    Build the canonical share reference for a client-visible track.

    Private catalogs intentionally fail closed.
    Sharing a link does not grant media or catalog access.
    """

    if (
        track.catalog.visibility
        == AudioCatalog.Visibility.PRIVATE
    ):
        return None

    return {
        "kind": "music_track",
        "canonical_path":
            f"/music/{track.public_id}",
    }


class TaxonomySerializer(
    serializers.Serializer
):
    id = serializers.UUIDField(
        source="public_id"
    )

    name = serializers.CharField()
    slug = serializers.CharField()


class CatalogSerializer(
    serializers.ModelSerializer
):
    id = serializers.UUIDField(
        source="public_id"
    )

    class Meta:
        model = AudioCatalog

        fields = (
            "id",
            "name",
            "slug",
            "description",
        )


class AudioContributorSerializer(
    serializers.ModelSerializer
):
    id = serializers.UUIDField(
        source="public_id"
    )

    class Meta:
        model = AudioContributor

        fields = (
            "id",
            "display_name",
            "kind",
        )


class TrackCreditSerializer(
    serializers.ModelSerializer
):
    id = serializers.UUIDField(
        source="public_id"
    )

    contributor = (
        AudioContributorSerializer(
            read_only=True
        )
    )

    class Meta:
        model = TrackContributor

        fields = (
            "id",
            "contributor",
            "role",
            "credit_text",
            "sort_order",
        )


class ArtworkSerializer(
    serializers.ModelSerializer
):
    id = serializers.UUIDField(
        source="public_id"
    )

    asset = (
        serializers.SerializerMethodField()
    )

    class Meta:
        model = MusicArtwork

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

    def get_asset(
        self,
        obj,
    ):
        return asset_target(
            obj,
            "image",
            "image",
        )


class VariantSerializer(
    serializers.ModelSerializer
):
    id = serializers.UUIDField(
        source="public_id"
    )

    playback_asset = (
        serializers.SerializerMethodField()
    )

    waveform_asset = (
        serializers.SerializerMethodField()
    )

    class Meta:
        model = MusicTrackVariant

        fields = (
            "id",
            "variant_type",
            "label",
            "locale",
            "duration_ms",
            "source_start_ms",
            "source_end_ms",
            "mime_type",
            "codec",
            "container",
            "bitrate_kbps",
            "sample_rate_hz",
            "channels",
            "is_default",
            "is_offline_eligible",
            "playback_asset",
            "waveform_asset",
        )

    def get_playback_asset(
        self,
        obj,
    ):
        return asset_target(
            obj,
            "audio_file",
            "audio",
        )

    def get_waveform_asset(
        self,
        obj,
    ):
        if not obj.waveform_file:
            return None

        return asset_target(
            obj,
            "waveform_file",
            "file",
        )


class TrackEngagementSerializer(
    serializers.Serializer
):
    """
    Canonical public engagement contract.

    Decimal values are rendered as JSON numbers, never strings.
    """

    qualified_plays = (
        serializers.IntegerField(
            min_value=0
        )
    )

    usages = (
        serializers.IntegerField(
            min_value=0
        )
    )

    trending_score = (
        serializers.DecimalField(
            max_digits=20,
            decimal_places=6,
            coerce_to_string=False,
        )
    )


class TrackShareReferenceSerializer(
    serializers.Serializer
):
    """
    Stable client-facing reference for sharing a music track.

    This contract contains routing metadata only.
    It never exposes media delivery targets or rights internals.
    """

    kind = serializers.CharField()
    canonical_path = serializers.CharField()


class TrackSharePreviewSerializer(
    serializers.Serializer
):
    """
    Public metadata used only for external link previews.

    This contract intentionally exposes no playback, rights,
    library, analytics, lyrics or private catalog data.
    """

    id = serializers.UUIDField(
        source="public_id"
    )

    kind = serializers.SerializerMethodField()
    title = serializers.CharField()
    artist = serializers.SerializerMethodField()
    canonical_path = serializers.SerializerMethodField()
    artwork = serializers.SerializerMethodField()

    def get_kind(
        self,
        obj,
    ) -> str:
        return "music_track"

    def get_artist(
        self,
        obj,
    ) -> str:
        return primary_track_artist(
            obj
        )

    def get_canonical_path(
        self,
        obj,
    ) -> str:
        return (
            f"/music/{obj.public_id}"
        )

    def get_artwork(
        self,
        obj,
    ) -> dict | None:
        artwork = primary_track_artwork(
            obj
        )

        if (
            artwork is None
            or not artwork.is_available()
        ):
            return None

        request = self.context.get(
            "request"
        )

        if request is None:
            return None

        image_url = reverse(
            "audio_catalog:tracks-share-preview-image",
            kwargs={
                "public_id":
                    obj.public_id,
            },
            request=request,
        )

        return {
            "url": image_url,
            "width": artwork.width,
            "height": artwork.height,
            "alt": (
                f"{obj.title} artwork"
            ),
        }

class TrackListSerializer(
    serializers.ModelSerializer
):
    id = serializers.UUIDField(
        source="public_id"
    )

    catalog = CatalogSerializer(
        read_only=True
    )

    categories = TaxonomySerializer(
        many=True,
        read_only=True,
    )

    genres = TaxonomySerializer(
        many=True,
        read_only=True,
    )

    moods = TaxonomySerializer(
        many=True,
        read_only=True,
    )

    tags = TaxonomySerializer(
        many=True,
        read_only=True,
    )

    primary_artist = (
        serializers.SerializerMethodField()
    )

    share = (
        serializers.SerializerMethodField()
    )

    artwork = (
        serializers.SerializerMethodField()
    )

    playback = (
        serializers.SerializerMethodField()
    )

    engagement = (
        serializers.SerializerMethodField()
    )

    offline_available = (
        serializers.SerializerMethodField()
    )

    allow_ugc = serializers.BooleanField(
        read_only=True
    )

    allow_streaming = (
        serializers.BooleanField(
            read_only=True
        )
    )

    min_clip_duration_ms = (
        serializers.IntegerField(
            read_only=True
        )
    )

    max_clip_duration_ms = (
        serializers.IntegerField(
            read_only=True
        )
    )

    class Meta:
        model = MusicTrack

        fields = (
            "id",
            "title",
            "slug",
            "subtitle",
            "catalog",
            "duration_ms",
            "bpm",
            "musical_key",
            "is_instrumental",
            "has_vocals",
            "categories",
            "genres",
            "moods",
            "tags",
            "primary_artist",
            "share",
            "artwork",
            "playback",
            "engagement",
            "allow_ugc",
            "allow_streaming",
            "offline_available",
            "min_clip_duration_ms",
            "max_clip_duration_ms",
            "version",
            "published_at",
        )

    def get_primary_artist(
        self,
        obj,
    ):
        return primary_track_artist(
            obj
        )

    def get_share(
        self,
        obj,
    ):
        payload = (
            track_share_reference(
                obj
            )
        )

        if payload is None:
            return None

        return (
            TrackShareReferenceSerializer(
                instance=payload
            )
            .data
        )

    def get_artwork(
        self,
        obj,
    ):
        artwork = primary_track_artwork(
            obj
        )

        if artwork is None:
            return None

        return ArtworkSerializer(
            artwork,
            context=self.context,
        ).data

    def get_playback(
        self,
        obj,
    ):
        variant = default_track_variant(
            obj
        )

        if variant is None:
            return None

        return VariantSerializer(
            variant,
            context=self.context,
        ).data

    def get_engagement(
        self,
        obj,
    ):
        payload = (
            track_engagement_payload(
                obj
            )
        )

        return (
            TrackEngagementSerializer(
                instance=payload
            )
            .data
        )

    def get_offline_available(
        self,
        obj,
    ):
        return track_offline_available(
            obj
        )


class TrackDetailSerializer(
    TrackListSerializer
):
    artworks = (
        serializers.SerializerMethodField()
    )

    variants = (
        serializers.SerializerMethodField()
    )

    credits = TrackCreditSerializer(
        source="contributor_links",
        many=True,
        read_only=True,
    )

    rights_summary = (
        serializers.SerializerMethodField()
    )

    class Meta(
        TrackListSerializer.Meta
    ):
        fields = (
            TrackListSerializer.Meta.fields
            + (
                "description",
                "source_type",
                "language_code",
                "allow_external_export",
                "artworks",
                "variants",
                "credits",
                "rights_summary",
            )
        )

    def get_artworks(
        self,
        obj,
    ):
        return ArtworkSerializer(
            usable_track_artworks(
                obj
            ),
            many=True,
            context=self.context,
        ).data

    def get_variants(
        self,
        obj,
    ):
        return VariantSerializer(
            usable_track_variants(
                obj
            ),
            many=True,
            context=self.context,
        ).data

    def get_rights_summary(
        self,
        obj,
    ):
        rights = track_rights(
            obj
        )

        if rights is None:
            return None

        return {
            "status":
                rights.status,
            "attribution_required":
                rights.attribution_required,
            "attribution_text":
                rights.attribution_text,
            "external_export_allowed":
                rights.external_export_allowed,
            "effective_until":
                rights.effective_until,
        }