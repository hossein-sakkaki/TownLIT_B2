# apps/audio_catalog/views.py

from __future__ import annotations

import logging

from django.db.models import Q

from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.audio_catalog.analytics.selectors import (
    recommended_tracks_for_user,
    trending_tracks,
)
from apps.audio_catalog.analytics.services import (
    end_playback,
    heartbeat_playback,
    start_playback,
)
from apps.audio_catalog.models import (
    AudioCatalog,
    AudioCategory,
    AudioGenre,
    AudioMood,
    AudioTag,
)
from apps.audio_catalog.querysets import published_tracks
from apps.audio_catalog.serializers import (
    CatalogSerializer,
    PlaybackEndSerializer,
    PlaybackHeartbeatSerializer,
    PlaybackSessionResponseSerializer,
    PlaybackStartSerializer,
    TaxonomySerializer,
    TrackDetailSerializer,
    TrackListSerializer,
)
from apps.core.pagination import ConfigurablePagination


logger = logging.getLogger(__name__)


class AudioCatalogPagination(ConfigurablePagination):
    """
    Page-number pagination matching the shared iOS paginated response.
    """

    page_size = 30
    page_size_query_param = "page_size"
    max_page_size = 100


class MusicTrackViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated]
    pagination_class = AudioCatalogPagination

    lookup_field = "public_id"
    lookup_url_kwarg = "public_id"

    def get_queryset(self):
        queryset = published_tracks()
        params = self.request.query_params

        filters = {
            "catalog__slug": params.get("catalog"),
            "categories__slug": params.get("category"),
            "genres__slug": params.get("genre"),
            "moods__slug": params.get("mood"),
            "tags__slug": params.get("tag"),
        }

        for key, value in filters.items():
            normalized = str(value or "").strip()

            if normalized:
                queryset = queryset.filter(**{key: normalized})

        instrumental = str(
            params.get("instrumental") or ""
        ).strip().lower()

        if instrumental in {"1", "true", "yes"}:
            queryset = queryset.filter(is_instrumental=True)

        query = str(params.get("q") or "").strip()[:120]

        if query:
            queryset = queryset.filter(
                Q(title__icontains=query)
                | Q(subtitle__icontains=query)
                | Q(search_document__icontains=query)
                | Q(tags__name__icontains=query)
                | Q(categories__name__icontains=query)
                | Q(genres__name__icontains=query)
                | Q(moods__name__icontains=query)
            )

        return queryset.distinct()

    def get_serializer_class(self):
        if self.action == "retrieve":
            return TrackDetailSerializer

        return TrackListSerializer

    @action(
        detail=False,
        methods=["get"],
        url_path="bootstrap",
    )
    def bootstrap(self, request):
        return Response(
            {
                "catalogs": CatalogSerializer(
                    AudioCatalog.objects.filter(is_active=True),
                    many=True,
                    context={"request": request},
                ).data,
                "categories": TaxonomySerializer(
                    AudioCategory.objects.filter(is_active=True),
                    many=True,
                    context={"request": request},
                ).data,
                "genres": TaxonomySerializer(
                    AudioGenre.objects.filter(is_active=True),
                    many=True,
                    context={"request": request},
                ).data,
                "moods": TaxonomySerializer(
                    AudioMood.objects.filter(is_active=True),
                    many=True,
                    context={"request": request},
                ).data,
                "tags": TaxonomySerializer(
                    AudioTag.objects.filter(is_active=True),
                    many=True,
                    context={"request": request},
                ).data,
                "limits": {
                    "default_page_size": 30,
                    "max_page_size": 100,
                    "max_clip_duration_ms": 60_000,
                    "heartbeat_interval_seconds": 15,
                },
            },
            status=status.HTTP_200_OK,
        )

    @action(
        detail=False,
        methods=["get"],
        url_path="trending",
    )
    def trending(self, request):
        queryset = trending_tracks()
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = TrackListSerializer(
                page,
                many=True,
                context={"request": request},
            )

            return self.get_paginated_response(serializer.data)

        serializer = TrackListSerializer(
            queryset,
            many=True,
            context={"request": request},
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    @action(
        detail=False,
        methods=["get"],
        url_path="recommended",
    )
    def recommended(self, request):
        """
        Return personalized tracks with a catalog fallback.
        """

        try:
            queryset = recommended_tracks_for_user(request.user)
        except Exception:
            logger.exception(
                "audio_catalog.recommended_failed user_id=%s",
                request.user.pk,
            )
            queryset = published_tracks()

        if not queryset.exists():
            queryset = published_tracks()

        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = TrackListSerializer(
                page,
                many=True,
                context={"request": request},
            )

            return self.get_paginated_response(serializer.data)

        serializer = TrackListSerializer(
            queryset,
            many=True,
            context={"request": request},
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
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
        serializer = PlaybackStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        result = start_playback(
            user=request.user,
            session_id=data["session_id"],
            track_public_id=data["track_id"],
            variant_public_id=data.get("variant_id"),
            surface=data["surface"],
            source_context=data.get("source_context", {}),
            client_platform=data.get("client_platform", ""),
            client_version=data.get("client_version", ""),
            raw_device_id=request.headers.get("X-Device-ID", ""),
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
        serializer = PlaybackHeartbeatSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        result = heartbeat_playback(
            user=request.user,
            session_id=data["session_id"],
            sequence=data["sequence"],
            position_ms=data["position_ms"],
            listened_delta_ms=data["listened_delta_ms"],
            is_playing=data["is_playing"],
            is_foreground=data["is_foreground"],
        )

        response = PlaybackSessionResponseSerializer(
            result.session
        ).data

        response["accepted_delta_ms"] = result.accepted_delta_ms
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
        serializer = PlaybackEndSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

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