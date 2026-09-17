# apps/audio_catalog/views/catalog.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-14.
# Last Update by Hossein Sakkaki on 2026-09-17.

from __future__ import annotations

import logging

from django.db.models import Q
import mimetypes
from pathlib import Path

from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import (
    AllowAny,
    IsAuthenticated,
)
from rest_framework.response import Response

from apps.audio_catalog.analytics.selectors import (
    recommended_tracks_for_user,
    trending_tracks,
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
    TaxonomySerializer,
    TrackDetailSerializer,
    TrackListSerializer,
    TrackSharePreviewSerializer,
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
                queryset = queryset.filter(
                    **{key: normalized}
                )

        instrumental = str(
            params.get("instrumental") or ""
        ).strip().lower()

        if instrumental in {"1", "true", "yes"}:
            queryset = queryset.filter(
                is_instrumental=True
            )

        query = str(
            params.get("q") or ""
        ).strip()[:120]

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
    
    def _get_share_preview_track(
        self,
    ):
        """
        Resolve only currently published, non-private tracks.

        Share preview is public metadata only. It does not grant
        playback or catalog access.
        """

        queryset = (
            published_tracks()
            .exclude(
                catalog__visibility=(
                    AudioCatalog
                    .Visibility
                    .PRIVATE
                )
            )
        )

        return get_object_or_404(
            queryset,
            public_id=(
                self.kwargs[
                    "public_id"
                ]
            ),
        )

    @action(
        detail=False,
        methods=["get"],
        url_path="bootstrap",
    )
    def bootstrap(self, request):
        return Response(
            {
                "catalogs": CatalogSerializer(
                    AudioCatalog.objects.filter(
                        is_active=True
                    ),
                    many=True,
                    context={"request": request},
                ).data,
                "categories": TaxonomySerializer(
                    AudioCategory.objects.filter(
                        is_active=True
                    ),
                    many=True,
                    context={"request": request},
                ).data,
                "genres": TaxonomySerializer(
                    AudioGenre.objects.filter(
                        is_active=True
                    ),
                    many=True,
                    context={"request": request},
                ).data,
                "moods": TaxonomySerializer(
                    AudioMood.objects.filter(
                        is_active=True
                    ),
                    many=True,
                    context={"request": request},
                ).data,
                "tags": TaxonomySerializer(
                    AudioTag.objects.filter(
                        is_active=True
                    ),
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

            return self.get_paginated_response(
                serializer.data
            )

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
            queryset = recommended_tracks_for_user(
                request.user
            )
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

            return self.get_paginated_response(
                serializer.data
            )

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
        detail=True,
        methods=["get"],
        url_path="share-preview",
        permission_classes=[AllowAny],
        authentication_classes=[],
    )
    def share_preview(
        self,
        request,
        public_id=None,
    ):
        """
        Return crawler-safe public metadata for one shareable track.
        """

        track = (
            self
            ._get_share_preview_track()
        )

        serializer = (
            TrackSharePreviewSerializer(
                track,
                context={
                    "request": request,
                },
            )
        )

        response = Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

        response[
            "Cache-Control"
        ] = (
            "public, max-age=300, "
            "stale-while-revalidate=3600"
        )

        return response

    @action(
        detail=True,
        methods=["get"],
        url_path="share-preview-image",
        permission_classes=[AllowAny],
        authentication_classes=[],
    )
    def share_preview_image(
        self,
        request,
        public_id=None,
    ):
        """
        Deliver only the selected artwork for external link previews.

        The stable endpoint hides private storage URLs and exposes
        no audio asset.
        """

        track = (
            self
            ._get_share_preview_track()
        )

        from apps.audio_catalog.serializers.catalog import (
            primary_track_artwork,
        )

        artwork = primary_track_artwork(
            track
        )

        if (
            artwork is None
            or not artwork.is_available()
            or not artwork.image
        ):
            return Response(
                {
                    "detail":
                        "Artwork not found.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        image_name = str(
            artwork.image.name
            or ""
        )

        content_type = (
            mimetypes.guess_type(
                image_name
            )[0]
            or "image/jpeg"
        )

        suffix = (
            Path(
                image_name
            ).suffix
            or ".jpg"
        )

        try:
            file_handle = (
                artwork.image.open(
                    "rb"
                )
            )
        except (
            FileNotFoundError,
            OSError,
        ):
            logger.exception(
                "audio_catalog.share_preview_artwork_open_failed "
                "track_public_id=%s artwork_id=%s",
                track.public_id,
                artwork.pk,
            )

            return Response(
                {
                    "detail":
                        "Artwork not found.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        response = FileResponse(
            file_handle,
            as_attachment=False,
            filename=(
                f"{track.public_id}"
                f"{suffix}"
            ),
            content_type=content_type,
        )

        response[
            "Cache-Control"
        ] = (
            "public, max-age=3600, "
            "stale-while-revalidate=86400"
        )

        response[
            "X-Content-Type-Options"
        ] = "nosniff"

        return response