# apps/audio_catalog/views/library.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-15.
# Last Update by Hossein Sakkaki on 2026-09-15.

from uuid import UUID

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.audio_catalog.selectors.library import (
    favorite_library_tracks_for_user,
    recently_played_tracks_for_user,
    saved_library_tracks_for_user,
)
from apps.audio_catalog.serializers import (
    AudioLibraryStateSerializer,
    AudioLibraryStateUpdateSerializer,
    AudioLibraryTrackSerializer,
    RecentlyPlayedTrackSerializer,
)
from apps.audio_catalog.services.library import (
    library_state_for_track,
    library_state_payload,
    remove_track_from_library,
    set_track_library_state,
)
from apps.core.pagination import ConfigurablePagination


class MusicLibraryPagination(ConfigurablePagination):
    page_size = 30
    page_size_query_param = "page_size"
    max_page_size = 100


class MusicLibraryViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    pagination_class = MusicLibraryPagination

    def list(self, request):
        return self._paginated_response(
            saved_library_tracks_for_user(request.user),
            AudioLibraryTrackSerializer,
        )

    @action(detail=False, methods=["get"])
    def favorites(self, request):
        return self._paginated_response(
            favorite_library_tracks_for_user(request.user),
            AudioLibraryTrackSerializer,
        )

    @action(detail=False, methods=["get"], url_path="recent")
    def recent(self, request):
        return self._paginated_response(
            recently_played_tracks_for_user(request.user),
            RecentlyPlayedTrackSerializer,
        )

    @action(
        detail=False,
        methods=["get", "put", "delete"],
        url_path=r"tracks/(?P<track_public_id>[0-9a-fA-F-]+)",
    )
    def track_state(self, request, track_public_id=None):
        track_id = self._track_id(track_public_id)

        if request.method == "GET":
            entry = library_state_for_track(
                user=request.user,
                track_public_id=track_id,
            )
            return Response(self._state_data(entry))

        if request.method == "DELETE":
            remove_track_from_library(
                user=request.user,
                track_public_id=track_id,
            )
            return Response(status=status.HTTP_204_NO_CONTENT)

        serializer = AudioLibraryStateUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        entry = set_track_library_state(
            user=request.user,
            track_public_id=track_id,
            **serializer.validated_data,
        )

        return Response(self._state_data(entry))

    def _paginated_response(self, queryset, serializer_class):
        page = self.paginate_queryset(queryset)
        serializer = serializer_class(
            page if page is not None else queryset,
            many=True,
            context=self.get_serializer_context(),
        )

        if page is not None:
            return self.get_paginated_response(serializer.data)

        return Response(serializer.data)

    @staticmethod
    def _track_id(value):
        try:
            return UUID(str(value))
        except (TypeError, ValueError, AttributeError) as exc:
            raise NotFound("Track not found.") from exc

    @staticmethod
    def _state_data(entry):
        serializer = AudioLibraryStateSerializer(
            library_state_payload(entry)
        )
        return serializer.data