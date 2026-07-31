# apps/audio_catalog/serializers.py

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from rest_framework import serializers

from apps.audio_catalog.analytics.constants import (
    HEARTBEAT_INTERVAL_SECONDS,
)
from apps.audio_catalog.models import (
    AudioCatalog,
    AudioPlaybackSession,
    MusicArtwork,
    MusicTrack,
    MusicTrackVariant,
    PlaybackEndReason,
    PlaybackSurface,
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


def normalize_trending_score(value) -> Decimal:
    """
    Normalize every score to the public six-decimal contract.
    """

    if value is None:
        return Decimal("0.000000")

    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0.000000")

    if not decimal_value.is_finite():
        return Decimal("0.000000")

    return decimal_value.quantize(
        TRENDING_SCORE_QUANTUM,
        rounding=ROUND_HALF_UP,
    )


def usable_track_artworks(track) -> list[MusicArtwork]:
    """
    Return artwork records that can be delivered to clients.
    """

    return [
        artwork
        for artwork in track.artworks.all()
        if artwork.image
    ]


def usable_track_variants(track) -> list[MusicTrackVariant]:
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


def primary_track_artwork(track) -> MusicArtwork | None:
    """
    Resolve one deterministic primary artwork.
    """

    artworks = usable_track_artworks(track)

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

    return artworks[0] if artworks else None


def default_track_variant(track) -> MusicTrackVariant | None:
    """
    Resolve one deterministic playable variant.
    """

    variants = usable_track_variants(track)

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


def primary_track_artist(track) -> str:
    """
    Resolve the primary artist without additional queries.
    """

    link = next(
        (
            item
            for item in track.contributor_links.all()
            if item.role == "primary_artist"
        ),
        None,
    )

    if link is None:
        return "TownLIT Original"

    return link.contributor.display_name


def track_engagement_payload(track) -> dict:
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
            "trending_score": normalize_trending_score(
                resolved_score
            ),
        }

    if resolved_score is None:
        resolved_score = metric.trending_score

    return {
        "qualified_plays": int(
            metric.total_qualified_plays or 0
        ),
        "usages": int(
            metric.total_usages or 0
        ),
        "trending_score": normalize_trending_score(
            resolved_score
        ),
    }


class TaxonomySerializer(serializers.Serializer):
    id = serializers.UUIDField(source="public_id")
    name = serializers.CharField()
    slug = serializers.CharField()


class CatalogSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id")

    class Meta:
        model = AudioCatalog
        fields = (
            "id",
            "name",
            "slug",
            "description",
        )


class ArtworkSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id")
    asset = serializers.SerializerMethodField()

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

    def get_asset(self, obj):
        return asset_target(
            obj,
            "image",
            "image",
        )


class VariantSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id")
    playback_asset = serializers.SerializerMethodField()
    waveform_asset = serializers.SerializerMethodField()

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
            "playback_asset",
            "waveform_asset",
        )

    def get_playback_asset(self, obj):
        return asset_target(
            obj,
            "audio_file",
            "audio",
        )

    def get_waveform_asset(self, obj):
        if not obj.waveform_file:
            return None

        return asset_target(
            obj,
            "waveform_file",
            "file",
        )


class TrackEngagementSerializer(serializers.Serializer):
    """
    Canonical public engagement contract.

    Decimal values are rendered as JSON numbers, never strings.
    """

    qualified_plays = serializers.IntegerField(min_value=0)
    usages = serializers.IntegerField(min_value=0)

    trending_score = serializers.DecimalField(
        max_digits=20,
        decimal_places=6,
        coerce_to_string=False,
    )


class TrackListSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id")

    catalog = CatalogSerializer(read_only=True)
    categories = TaxonomySerializer(many=True, read_only=True)
    genres = TaxonomySerializer(many=True, read_only=True)
    moods = TaxonomySerializer(many=True, read_only=True)
    tags = TaxonomySerializer(many=True, read_only=True)

    artwork = serializers.SerializerMethodField()
    playback = serializers.SerializerMethodField()
    primary_artist = serializers.SerializerMethodField()
    engagement = serializers.SerializerMethodField()

    allow_ugc = serializers.BooleanField(read_only=True)
    allow_streaming = serializers.BooleanField(read_only=True)
    min_clip_duration_ms = serializers.IntegerField(read_only=True)
    max_clip_duration_ms = serializers.IntegerField(read_only=True)

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
            "artwork",
            "playback",
            "engagement",
            "allow_ugc",
            "allow_streaming",
            "min_clip_duration_ms",
            "max_clip_duration_ms",
            "version",
            "published_at",
        )

    def get_artwork(self, obj):
        artwork = primary_track_artwork(obj)

        if artwork is None:
            return None

        return ArtworkSerializer(
            artwork,
            context=self.context,
        ).data

    def get_playback(self, obj):
        variant = default_track_variant(obj)

        if variant is None:
            return None

        return VariantSerializer(
            variant,
            context=self.context,
        ).data

    def get_primary_artist(self, obj):
        return primary_track_artist(obj)

    def get_engagement(self, obj):
        payload = track_engagement_payload(obj)

        return TrackEngagementSerializer(
            instance=payload
        ).data


class TrackDetailSerializer(TrackListSerializer):
    artworks = serializers.SerializerMethodField()
    variants = serializers.SerializerMethodField()
    rights_summary = serializers.SerializerMethodField()

    class Meta(TrackListSerializer.Meta):
        fields = TrackListSerializer.Meta.fields + (
            "description",
            "source_type",
            "language_code",
            "allow_external_export",
            "artworks",
            "variants",
            "rights_summary",
        )

    def get_artworks(self, obj):
        return ArtworkSerializer(
            usable_track_artworks(obj),
            many=True,
            context=self.context,
        ).data

    def get_variants(self, obj):
        return VariantSerializer(
            usable_track_variants(obj),
            many=True,
            context=self.context,
        ).data

    def get_rights_summary(self, obj):
        rights = getattr(
            obj,
            "rights",
            None,
        )

        if rights is None:
            return None

        return {
            "status": rights.status,
            "attribution_required": rights.attribution_required,
            "attribution_text": rights.attribution_text,
            "external_export_allowed": rights.external_export_allowed,
            "effective_until": rights.effective_until,
        }


class PlaybackStartSerializer(serializers.Serializer):
    session_id = serializers.UUIDField()
    track_id = serializers.UUIDField()

    variant_id = serializers.UUIDField(
        required=False,
        allow_null=True,
    )

    surface = serializers.ChoiceField(
        choices=PlaybackSurface.choices,
        default=PlaybackSurface.OTHER,
    )

    source_context = serializers.JSONField(
        required=False,
        default=dict,
    )

    client_platform = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=24,
    )

    client_version = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=40,
    )


class PlaybackHeartbeatSerializer(serializers.Serializer):
    session_id = serializers.UUIDField()

    sequence = serializers.IntegerField(
        min_value=1,
    )

    position_ms = serializers.IntegerField(
        min_value=0,
    )

    listened_delta_ms = serializers.IntegerField(
        min_value=0,
    )

    is_playing = serializers.BooleanField(default=True)
    is_foreground = serializers.BooleanField(default=True)


class PlaybackEndSerializer(serializers.Serializer):
    session_id = serializers.UUIDField()

    sequence = serializers.IntegerField(
        min_value=1,
    )

    position_ms = serializers.IntegerField(
        min_value=0,
    )

    reason = serializers.ChoiceField(
        choices=PlaybackEndReason.choices,
    )


class PlaybackSessionResponseSerializer(
    serializers.ModelSerializer
):
    id = serializers.UUIDField(source="public_id")

    track_id = serializers.UUIDField(
        source="track.public_id",
    )

    variant_id = serializers.UUIDField(
        source="variant.public_id",
        allow_null=True,
    )

    heartbeat_interval_seconds = serializers.SerializerMethodField()

    class Meta:
        model = AudioPlaybackSession
        fields = (
            "id",
            "session_id",
            "track_id",
            "variant_id",
            "listened_ms",
            "max_position_ms",
            "qualified_play",
            "completed",
            "early_skipped",
            "is_active",
            "end_reason",
            "heartbeat_interval_seconds",
        )

    def get_heartbeat_interval_seconds(self, obj):
        return HEARTBEAT_INTERVAL_SECONDS