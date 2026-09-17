# apps/audio_catalog/views/releases.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-15.
# Last Update by Hossein Sakkaki on 2026-09-15.

from django.db.models import Q

from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from apps.audio_catalog.selectors.releases import published_releases
from apps.audio_catalog.serializers import (
    ReleaseDetailSerializer,
    ReleaseListSerializer,
)
from apps.core.pagination import ConfigurablePagination


class MusicReleasePagination(ConfigurablePagination):
    page_size = 20
    max_page_size = 100


class MusicReleaseViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated]
    pagination_class = MusicReleasePagination

    lookup_field = "public_id"
    lookup_url_kwarg = "public_id"

    def get_queryset(self):
        queryset = published_releases()
        params = self.request.query_params

        release_type = str(params.get("type") or "").strip()
        catalog = str(params.get("catalog") or "").strip()
        query = str(params.get("q") or "").strip()[:120]

        if release_type:
            queryset = queryset.filter(release_type=release_type)

        if catalog:
            queryset = queryset.filter(catalog__slug=catalog)

        if query:
            queryset = queryset.filter(
                Q(title__icontains=query)
                | Q(subtitle__icontains=query)
                | Q(
                    contributor_links__contributor__display_name__icontains=query
                )
            ).distinct()

        return queryset

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ReleaseDetailSerializer

        return ReleaseListSerializer