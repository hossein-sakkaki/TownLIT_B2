# apps/organizations/modules/church/views/gatherings.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-08.
# Last Update by Hossein Sakkaki on 2026-09-08.
#

from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone

from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.organizations.modules.church.constants import (
    ChurchGatheringOccurrenceStatus,
    ChurchGatheringSeriesStatus,
    ChurchPermissionKey,
)
from apps.organizations.modules.church.serializers import (
    ChurchGatheringMaterializeSerializer,
    ChurchGatheringOccurrenceCreateSerializer,
    ChurchGatheringOccurrenceSerializer,
    ChurchGatheringSeriesCreateSerializer,
    ChurchGatheringSeriesSerializer,
    ChurchGatheringSeriesUpdateSerializer,
)
from apps.organizations.modules.church.services.access import user_has_church_permission
from apps.organizations.modules.church.services.gatherings import (
    cancel_church_gathering,
    complete_church_gathering,
    create_church_gathering_occurrence,
    create_church_gathering_series,
    materialize_church_gathering_occurrences,
    update_church_gathering_series,
)
from apps.organizations.permissions import OrganizationsEnabledPermission
from apps.organizations.views.helpers import raise_drf_validation_error

from .helpers import (
    get_church_campus_or_404,
    get_church_gathering_or_404,
    get_church_gathering_series_or_404,
    get_church_ministry_or_404,
    get_church_request_context,
    visible_church_gathering_series,
    visible_church_gatherings,
)


def _resolve_optional_campus(*, workspace, public_id):
    if public_id is None:
        return None
    return get_church_campus_or_404(
        workspace=workspace,
        public_id=public_id,
    )


def _resolve_optional_ministry(*, workspace, public_id):
    if public_id is None:
        return None
    return get_church_ministry_or_404(
        workspace=workspace,
        public_id=public_id,
    )


def _serialize(serializer_class, instance, request):
    return serializer_class(
        instance,
        context={"request": request},
    ).data


class ChurchGatheringSeriesView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def get(self, request, slug):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        queryset = visible_church_gathering_series(
            user=request.user,
            workspace=workspace,
        )

        include_archived = request.query_params.get("include_archived") == "1"
        can_manage = user_has_church_permission(
            user=request.user,
            workspace=workspace,
            permission_key=ChurchPermissionKey.MANAGE_GATHERINGS,
        )

        if not include_archived or not can_manage:
            queryset = queryset.exclude(
                status=ChurchGatheringSeriesStatus.ARCHIVED,
            )

        return Response(
            ChurchGatheringSeriesSerializer(
                queryset,
                many=True,
                context={"request": request},
            ).data
        )

    def post(self, request, slug):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        serializer = ChurchGatheringSeriesCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)

        campus = _resolve_optional_campus(
            workspace=workspace,
            public_id=data.pop("campus_public_id", None),
        )
        ministry = _resolve_optional_ministry(
            workspace=workspace,
            public_id=data.pop("ministry_public_id", None),
        )

        try:
            series = create_church_gathering_series(
                workspace=workspace,
                actor=request.user,
                campus=campus,
                ministry=ministry,
                **data,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            _serialize(
                ChurchGatheringSeriesSerializer,
                series,
                request,
            ),
            status=status.HTTP_201_CREATED,
        )


class ChurchGatheringSeriesDetailView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def get(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        series = get_church_gathering_series_or_404(
            workspace=workspace,
            public_id=public_id,
        )

        if not visible_church_gathering_series(
            user=request.user,
            workspace=workspace,
        ).filter(pk=series.pk).exists():
            raise NotFound("Church gathering series not found.")

        return Response(
            _serialize(
                ChurchGatheringSeriesSerializer,
                series,
                request,
            )
        )

    def patch(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        series = get_church_gathering_series_or_404(
            workspace=workspace,
            public_id=public_id,
        )
        serializer = ChurchGatheringSeriesUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)

        if "campus_public_id" in data:
            data["campus"] = _resolve_optional_campus(
                workspace=workspace,
                public_id=data.pop("campus_public_id"),
            )

        if "ministry_public_id" in data:
            data["ministry"] = _resolve_optional_ministry(
                workspace=workspace,
                public_id=data.pop("ministry_public_id"),
            )

        try:
            series = update_church_gathering_series(
                series=series,
                actor=request.user,
                **data,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            _serialize(
                ChurchGatheringSeriesSerializer,
                series,
                request,
            )
        )


class ChurchGatheringSeriesMaterializeView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def post(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        series = get_church_gathering_series_or_404(
            workspace=workspace,
            public_id=public_id,
        )
        serializer = ChurchGatheringMaterializeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            created = materialize_church_gathering_occurrences(
                series=series,
                actor=request.user,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            ChurchGatheringOccurrenceSerializer(
                created,
                many=True,
                context={"request": request},
            ).data,
            status=status.HTTP_201_CREATED,
        )


class ChurchGatheringsView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def get(self, request, slug):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        queryset = visible_church_gatherings(
            user=request.user,
            workspace=workspace,
        )

        include_past = request.query_params.get("include_past") == "1"
        can_manage = user_has_church_permission(
            user=request.user,
            workspace=workspace,
            permission_key=ChurchPermissionKey.MANAGE_GATHERINGS,
        )

        if not include_past or not can_manage:
            queryset = queryset.filter(
                status=ChurchGatheringOccurrenceStatus.SCHEDULED,
                ends_at__gt=timezone.now(),
            )

        return Response(
            ChurchGatheringOccurrenceSerializer(
                queryset,
                many=True,
                context={"request": request},
            ).data
        )

    def post(self, request, slug):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        serializer = ChurchGatheringOccurrenceCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)

        campus = _resolve_optional_campus(
            workspace=workspace,
            public_id=data.pop("campus_public_id", None),
        )
        ministry = _resolve_optional_ministry(
            workspace=workspace,
            public_id=data.pop("ministry_public_id", None),
        )

        try:
            occurrence = create_church_gathering_occurrence(
                workspace=workspace,
                actor=request.user,
                campus=campus,
                ministry=ministry,
                **data,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            _serialize(
                ChurchGatheringOccurrenceSerializer,
                occurrence,
                request,
            ),
            status=status.HTTP_201_CREATED,
        )


class ChurchGatheringDetailView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def get(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        occurrence = get_church_gathering_or_404(
            workspace=workspace,
            public_id=public_id,
        )

        if not visible_church_gatherings(
            user=request.user,
            workspace=workspace,
        ).filter(pk=occurrence.pk).exists():
            raise NotFound("Church gathering not found.")

        return Response(
            _serialize(
                ChurchGatheringOccurrenceSerializer,
                occurrence,
                request,
            )
        )


class ChurchGatheringCancelView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def post(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        occurrence = get_church_gathering_or_404(
            workspace=workspace,
            public_id=public_id,
        )

        try:
            occurrence = cancel_church_gathering(
                occurrence=occurrence,
                actor=request.user,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            _serialize(
                ChurchGatheringOccurrenceSerializer,
                occurrence,
                request,
            )
        )


class ChurchGatheringCompleteView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def post(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        occurrence = get_church_gathering_or_404(
            workspace=workspace,
            public_id=public_id,
        )

        try:
            occurrence = complete_church_gathering(
                occurrence=occurrence,
                actor=request.user,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            _serialize(
                ChurchGatheringOccurrenceSerializer,
                occurrence,
                request,
            )
        )
