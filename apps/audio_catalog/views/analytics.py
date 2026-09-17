# apps/audio_catalog/views/analytics.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-14.
# Last Update by Hossein Sakkaki on 2026-09-14.

from __future__ import annotations

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.audio_catalog.analytics.services import (
    end_playback,
    heartbeat_playback,
    start_playback,
)
from apps.audio_catalog.serializers import (
    PlaybackEndSerializer,
    PlaybackHeartbeatSerializer,
    PlaybackSessionResponseSerializer,
    PlaybackStartSerializer,
)


class AudioPlaybackAnalyticsViewSet(viewsets.ViewSet):
    """
    Playback analytics endpoints.
    """

    permission_classes = [IsAuthenticated]

    @action(
        detail=False,
        methods=["post"],
        url_path="start",
    )
    def start(self, request):
        serializer = PlaybackStartSerializer(
            data=request.data
        )
        serializer.is_valid(
            raise_exception=True
        )

        data = serializer.validated_data

        result = start_playback(
            user=request.user,
            session_id=data["session_id"],
            track_public_id=data["track_id"],
            variant_public_id=data.get(
                "variant_id"
            ),
            surface=data["surface"],
            source_context=data.get(
                "source_context",
                {},
            ),
            client_platform=data.get(
                "client_platform",
                "",
            ),
            client_version=data.get(
                "client_version",
                "",
            ),
            raw_device_id=request.headers.get(
                "X-Device-ID",
                "",
            ),
        )

        response = PlaybackSessionResponseSerializer(
            result.session
        ).data

        response["accepted"] = True
        response["duplicate"] = result.duplicate

        return Response(
            response,
            status=(
                status.HTTP_200_OK
                if result.duplicate
                else status.HTTP_201_CREATED
            ),
        )

    @action(
        detail=False,
        methods=["post"],
        url_path="heartbeat",
    )
    def heartbeat(self, request):
        serializer = PlaybackHeartbeatSerializer(
            data=request.data
        )
        serializer.is_valid(
            raise_exception=True
        )

        data = serializer.validated_data

        result = heartbeat_playback(
            user=request.user,
            session_id=data["session_id"],
            sequence=data["sequence"],
            position_ms=data["position_ms"],
            listened_delta_ms=data[
                "listened_delta_ms"
            ],
            is_playing=data["is_playing"],
            is_foreground=data[
                "is_foreground"
            ],
        )

        response = PlaybackSessionResponseSerializer(
            result.session
        ).data

        response["accepted_delta_ms"] = (
            result.accepted_delta_ms
        )
        response["duplicate"] = result.duplicate

        return Response(
            response,
            status=status.HTTP_200_OK,
        )

    @action(
        detail=False,
        methods=["post"],
        url_path="end",
    )
    def end(self, request):
        serializer = PlaybackEndSerializer(
            data=request.data
        )
        serializer.is_valid(
            raise_exception=True
        )

        data = serializer.validated_data

        result = end_playback(
            user=request.user,
            session_id=data["session_id"],
            sequence=data["sequence"],
            position_ms=data["position_ms"],
            reason=data["reason"],
        )

        response = PlaybackSessionResponseSerializer(
            result.session
        ).data

        response["duplicate"] = result.duplicate

        return Response(
            response,
            status=status.HTTP_200_OK,
        )