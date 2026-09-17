# apps/audio_catalog/views/lyrics.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-14.
# Last Update by Hossein Sakkaki on 2026-09-14.

from __future__ import annotations

from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audio_catalog.querysets import published_tracks
from apps.audio_catalog.serializers.lyrics import (
    MusicLyricsQuerySerializer,
    MusicLyricsSerializer,
    MusicLyricsSummarySerializer,
)
from apps.audio_catalog.services.lyrics import (
    published_lyrics_for_track,
    select_published_lyrics,
)


class MusicTrackLyricsView(APIView):
    """
    Read lyrics independently from existing track/Journey payloads.

    Tracks without published lyrics return selected=None so lyrics remain
    optional for existing playback and content flows.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, public_id):
        track = get_object_or_404(
            published_tracks(),
            public_id=public_id,
        )

        query = MusicLyricsQuerySerializer(
            data=request.query_params,
        )
        query.is_valid(
            raise_exception=True
        )

        language_code = (
            query.validated_data.get(
                "language",
                "",
            )
        )

        kind = query.validated_data.get(
            "kind",
            "",
        )

        documents = published_lyrics_for_track(
            track
        )

        selected = select_published_lyrics(
            documents,
            track_language_code=(
                track.language_code
            ),
            language_code=language_code,
            kind=kind,
        )

        return Response(
            {
                "track_id": track.public_id,
                "track_duration_ms": (
                    track.duration_ms
                ),
                "selected": (
                    MusicLyricsSerializer(
                        selected
                    ).data
                    if selected is not None
                    else None
                ),
                "available": (
                    MusicLyricsSummarySerializer(
                        documents,
                        many=True,
                    ).data
                ),
            },
            status=status.HTTP_200_OK,
        )