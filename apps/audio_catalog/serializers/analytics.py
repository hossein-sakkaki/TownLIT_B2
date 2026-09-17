# apps/audio_catalog/serializers/analytics.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-14.
# Last Update by Hossein Sakkaki on 2026-09-14.

from __future__ import annotations

from rest_framework import serializers

from apps.audio_catalog.analytics.constants import (
    HEARTBEAT_INTERVAL_SECONDS,
)
from apps.audio_catalog.models import (
    AudioPlaybackSession,
    PlaybackEndReason,
    PlaybackSurface,
)


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