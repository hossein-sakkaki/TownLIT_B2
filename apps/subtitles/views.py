# apps/subtitles/views.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-09.
# Last Update by Hossein Sakkaki on 2026-11-09.

from __future__ import annotations

import logging

from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status as drf_status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed, NotFound, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.subtitles.models import (
    SubtitleFormat,
    SubtitleJobStatus,
    SubtitleTrack,
    VideoTranscript,
    VoiceJobStatus,
    VoiceTrack,
)
from apps.subtitles.serializers import (
    SubtitleTrackMiniSerializer,
    VoiceTrackMiniSerializer,
)
from apps.subtitles.services.access import can_view_transcript
from apps.subtitles.services.ensure import ensure_subtitle_track
from apps.subtitles.services.ensure_voice import ensure_voice_track
from apps.subtitles.services.testimony_review import assert_transcript_ai_allowed
from apps.subtitles.services.ownership import resolve_owner_gender_from_transcript
from apps.subtitles.constants import VOICE_ENABLED_LANGUAGES
from apps.translations.services.language_codes import normalize_language_code

logger = logging.getLogger(__name__)


def _parse_positive_id(value, *, field: str) -> int:
    try:
        integer = int(value)
    except (TypeError, ValueError):
        raise ValidationError({field: "A positive integer is required."})
    if integer < 1:
        raise ValidationError({field: "A positive integer is required."})
    return integer


def _true(value) -> bool:
    return value is True or str(value).lower() in {"true", "1", "yes"}


def _require_transcript_access(*, transcript, viewer) -> None:
    # Do not disclose private transcript existence or track identifiers.
    if not can_view_transcript(transcript=transcript, viewer=viewer):
        raise NotFound("Track not found.")


def _protect_content_response(response):
    response["Cache-Control"] = "private, no-store, max-age=0"
    response["Vary"] = "Authorization, Cookie"
    response["X-Content-Type-Options"] = "nosniff"
    return response


class SubtitleTrackViewSet(viewsets.ReadOnlyModelViewSet):
    """Read or generate subtitle tracks only for accessible source content."""

    queryset = SubtitleTrack.objects.select_related("transcript")
    serializer_class = SubtitleTrackMiniSerializer
    permission_classes = [AllowAny]

    def list(self, request, *args, **kwargs):
        # Unbounded track enumeration would leak private transcript metadata.
        raise MethodNotAllowed("GET", detail="Use by-transcript for track listings.")

    def get_object(self):
        track = super().get_object()
        _require_transcript_access(transcript=track.transcript, viewer=self.request.user)
        return track

    def retrieve(self, request, *args, **kwargs):
        return _protect_content_response(super().retrieve(request, *args, **kwargs))

    @action(
        detail=False,
        methods=["post"],
        url_path="ensure",
        permission_classes=[IsAuthenticated],
    )
    def ensure(self, request):
        transcript_id = _parse_positive_id(
            request.data.get("transcript_id"), field="transcript_id"
        )
        target_language = str(request.data.get("target_language") or "").strip()
        fmt = str(request.data.get("fmt") or SubtitleFormat.VTT).strip().lower()
        if not target_language:
            raise ValidationError({"target_language": "This field is required."})
        if fmt not in (SubtitleFormat.VTT, SubtitleFormat.SRT):
            raise ValidationError({"fmt": "Unsupported subtitle format."})

        transcript = get_object_or_404(VideoTranscript, pk=transcript_id)
        _require_transcript_access(transcript=transcript, viewer=request.user)
        try:
            assert_transcript_ai_allowed(transcript)
        except Exception:
            return Response(
                {"detail": "AI subtitle generation is unavailable."},
                status=drf_status.HTTP_403_FORBIDDEN,
            )

        try:
            track = ensure_subtitle_track(
                transcript=transcript,
                target_language=target_language,
                fmt=fmt,
                force_retry_failed=_true(request.data.get("force_retry_failed")),
            )
        except (ValueError, RuntimeError) as exc:
            raise ValidationError({"detail": str(exc)}) from exc

        return _protect_content_response(Response(self.get_serializer(track).data))

    @action(detail=True, methods=["get"], url_path="content")
    def content(self, request, pk=None):
        track = self.get_object()
        if track.status != SubtitleJobStatus.DONE or not track.content:
            return Response(
                {"detail": "Content not ready"},
                status=drf_status.HTTP_409_CONFLICT,
            )

        mime_type = (
            "text/vtt; charset=utf-8"
            if track.fmt == SubtitleFormat.VTT
            else "text/plain; charset=utf-8"
        )
        return _protect_content_response(
            HttpResponse(track.content, content_type=mime_type)
        )

    @action(
        detail=False,
        methods=["get"],
        url_path=r"by-transcript/(?P<transcript_id>[^/.]+)",
    )
    def by_transcript(self, request, transcript_id=None):
        pk = _parse_positive_id(transcript_id, field="transcript_id")
        transcript = get_object_or_404(VideoTranscript, pk=pk)
        _require_transcript_access(transcript=transcript, viewer=request.user)
        tracks = self.get_queryset().filter(transcript=transcript).order_by(
            "target_language", "fmt", "id"
        )
        return _protect_content_response(
            Response(self.get_serializer(tracks, many=True).data)
        )


class VoiceTrackViewSet(viewsets.ReadOnlyModelViewSet):
    """Read or generate voice tracks only for accessible source content."""

    queryset = VoiceTrack.objects.select_related("transcript", "subtitle_track")
    serializer_class = VoiceTrackMiniSerializer
    permission_classes = [AllowAny]

    def list(self, request, *args, **kwargs):
        raise MethodNotAllowed("GET", detail="Voice tracks must be retrieved by ID.")

    def get_object(self):
        track = super().get_object()
        _require_transcript_access(transcript=track.transcript, viewer=self.request.user)
        return track

    def retrieve(self, request, *args, **kwargs):
        return _protect_content_response(super().retrieve(request, *args, **kwargs))

    @action(
        detail=False,
        methods=["post"],
        url_path="ensure",
        permission_classes=[IsAuthenticated],
    )
    def ensure(self, request):
        subtitle_track_id = _parse_positive_id(
            request.data.get("subtitle_track_id"), field="subtitle_track_id"
        )
        subtitle = get_object_or_404(
            SubtitleTrack.objects.select_related("transcript"),
            pk=subtitle_track_id,
        )
        _require_transcript_access(transcript=subtitle.transcript, viewer=request.user)
        try:
            assert_transcript_ai_allowed(subtitle.transcript)
        except Exception:
            return Response(
                {"detail": "AI voice generation is unavailable."},
                status=drf_status.HTTP_403_FORBIDDEN,
            )

        provider = str(request.data.get("provider") or "openai").strip()
        if provider != "openai":
            raise ValidationError({"provider": "Unsupported voice provider."})

        try:
            track = ensure_voice_track(
                subtitle_track=subtitle,
                provider=provider,
                voice_id=None,
                owner_gender=resolve_owner_gender_from_transcript(subtitle.transcript),
                force_retry_failed=_true(request.data.get("force_retry_failed")),
            )
        except (ValueError, RuntimeError) as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        return _protect_content_response(Response(self.get_serializer(track).data))

    @action(detail=True, methods=["get"], url_path="content")
    def content(self, request, pk=None):
        track = self.get_object()
        if track.status != VoiceJobStatus.DONE or not track.audio:
            return Response(
                {"detail": "Audio not ready"},
                status=drf_status.HTTP_409_CONFLICT,
            )
        return _protect_content_response(
            FileResponse(track.audio.open("rb"), content_type="audio/mpeg")
        )

    @action(
        detail=False,
        methods=["get"],
        url_path="languages",
        permission_classes=[AllowAny],
    )
    def languages(self, request):
        codes = [normalize_language_code(value) for value in VOICE_ENABLED_LANGUAGES]
        return Response({"languages": [{"code": code} for code in codes if code]})
