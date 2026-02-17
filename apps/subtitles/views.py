# apps/subtitles/views.py

from __future__ import annotations

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status as drf_status
from django.http import HttpResponse, FileResponse

from apps.subtitles.models import (
    VideoTranscript,
    SubtitleTrack,
    VoiceTrack,
    SubtitleFormat,
)
from apps.subtitles.serializers import (
    SubtitleTrackMiniSerializer,
    VoiceTrackMiniSerializer,
)
from apps.subtitles.services.ensure import ensure_subtitle_track
from apps.subtitles.services.ensure_voice import ensure_voice_track
from apps.subtitles.selectors import get_tracks_for_transcript
from apps.translations.services.language_codes import normalize_language_code
from apps.subtitles.constants import (
    VOICE_ENABLED_LANGUAGES,
    DEFAULT_VOICE_BY_LANGUAGE,
    DEFAULT_SAFE_VOICE,
)

# -----------------------------------------------------------------------------
# Subtitle Tracks
# -----------------------------------------------------------------------------
class SubtitleTrackViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Subtitle tracks API (ensure, list, content).
    """

    queryset = SubtitleTrack.objects.all()
    serializer_class = SubtitleTrackMiniSerializer
    permission_classes = [AllowAny]  # Visibility can be added later

    @action(
        detail=False,
        methods=["post"],
        url_path="ensure",
        permission_classes=[IsAuthenticated],
    )
    def ensure(self, request):
        """
        POST /subtitles/tracks/ensure/
        body: { transcript_id, target_language, fmt?, force_retry_failed? }
        """
        transcript_id = request.data.get("transcript_id")
        target_language = request.data.get("target_language")
        fmt = request.data.get("fmt") or SubtitleFormat.VTT
        force_retry_failed = bool(request.data.get("force_retry_failed", False))

        if not transcript_id or not target_language:
            return Response(
                {"detail": "transcript_id and target_language are required"},
                status=drf_status.HTTP_400_BAD_REQUEST,
            )

        try:
            transcript = VideoTranscript.objects.get(pk=int(transcript_id))
        except VideoTranscript.DoesNotExist:
            return Response(
                {"detail": "Transcript not found"},
                status=drf_status.HTTP_404_NOT_FOUND,
            )

        try:
            track = ensure_subtitle_track(
                transcript=transcript,
                target_language=str(target_language),
                fmt=str(fmt),
                force_retry_failed=force_retry_failed,
            )
        except Exception as exc:
            return Response(
                {"detail": str(exc)},
                status=drf_status.HTTP_400_BAD_REQUEST,
            )

        return Response(self.get_serializer(track).data)

    @action(detail=True, methods=["get"], url_path="content")
    def content(self, request, pk=None):
        """
        GET /subtitles/tracks/{id}/content/
        Returns raw VTT/SRT text.
        """
        track = self.get_object()

        if not track.content:
            return Response(
                {"detail": "Content not ready"},
                status=drf_status.HTTP_409_CONFLICT,
            )

        content_type = (
            "text/vtt; charset=utf-8"
            if track.fmt == SubtitleFormat.VTT
            else "text/plain; charset=utf-8"
        )

        return HttpResponse(track.content, content_type=content_type)

    @action(
        detail=False,
        methods=["get"],
        url_path="by-transcript/(?P<transcript_id>[^/.]+)",
    )
    def by_transcript(self, request, transcript_id=None):
        """
        GET /subtitles/tracks/by-transcript/{transcript_id}/
        """
        qs = get_tracks_for_transcript(int(transcript_id))
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)


# -----------------------------------------------------------------------------
# Voice Tracks (TTS)
# -----------------------------------------------------------------------------
class VoiceTrackViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Voice tracks API (ensure, content).
    """

    queryset = VoiceTrack.objects.all()
    serializer_class = VoiceTrackMiniSerializer
    permission_classes = [AllowAny]

    @action(
        detail=False,
        methods=["post"],
        url_path="ensure",
        permission_classes=[IsAuthenticated],
    )
    def ensure(self, request):
        """
        POST /subtitles/voices/ensure/
        body: { subtitle_track_id, provider?, voice_id?, force_retry_failed? }

        Policy:
        - voice_id from client is NOT trusted (prevents mismatch + duplicates)
        - voice_id is resolved by backend using (language + owner_gender)
        """
        subtitle_track_id = request.data.get("subtitle_track_id")
        provider = request.data.get("provider") or "openai"
        force_retry_failed = bool(request.data.get("force_retry_failed", False))

        if not subtitle_track_id:
            return Response(
                {"detail": "subtitle_track_id is required"},
                status=drf_status.HTTP_400_BAD_REQUEST,
            )

        try:
            subtitle = SubtitleTrack.objects.select_related("transcript").get(pk=int(subtitle_track_id))
        except SubtitleTrack.DoesNotExist:
            return Response(
                {"detail": "SubtitleTrack not found"},
                status=drf_status.HTTP_404_NOT_FOUND,
            )

        # Best-effort gender resolution (your helper)
        from apps.subtitles.services.ownership import resolve_owner_gender_from_transcript
        owner_gender = resolve_owner_gender_from_transcript(subtitle.transcript)  # "Male"/"Female"/None

        try:
            track = ensure_voice_track(
                subtitle_track=subtitle,
                provider=provider,
                voice_id=None,                 # ignored by service anyway
                owner_gender=owner_gender,
                force_retry_failed=force_retry_failed,
            )
        except Exception as exc:
            return Response(
                {"detail": str(exc)},
                status=drf_status.HTTP_400_BAD_REQUEST,
            )

        return Response(self.get_serializer(track).data)


    @action(detail=True, methods=["get"], url_path="content")
    def content(self, request, pk=None):
        """
        GET /subtitles/voices/{id}/content/
        Returns audio file (mp3).
        """
        track = self.get_object()

        if not track.audio:
            return Response(
                {"detail": "Audio not ready"},
                status=drf_status.HTTP_409_CONFLICT,
            )

        return FileResponse(
            track.audio.open("rb"),
            content_type="audio/mpeg",
        )


    @action(
        detail=False,
        methods=["get"],
        url_path="languages",
        permission_classes=[AllowAny],
    )
    def languages(self, request):
        """
        GET /subtitles/voices/languages/

        Returns backend-approved voice languages only.
        NOTE: We intentionally do NOT return default_voice_id.
            Backend resolves voice_id deterministically using (language + owner_gender).
        """
        langs = [normalize_language_code(x) for x in VOICE_ENABLED_LANGUAGES]
        langs = [x for x in langs if x]

        out = [{"code": code} for code in langs]
        return Response({"languages": out})
