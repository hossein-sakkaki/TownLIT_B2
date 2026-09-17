# apps/organizations/modules/church/views/resources.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-08.
# Last Update by Hossein Sakkaki on 2026-09-08.
#

from django.core.exceptions import ValidationError as DjangoValidationError

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.organizations.modules.church.constants import (
    ChurchPermissionKey,
    ChurchResourceReservationStatus,
)
from apps.organizations.modules.church.models import (
    ChurchResource,
    ChurchResourceReservation,
)
from apps.organizations.modules.church.serializers import (
    ChurchResourceCreateSerializer,
    ChurchResourceReservationCreateSerializer,
    ChurchResourceReservationSerializer,
    ChurchResourceSerializer,
    ChurchResourceUpdateSerializer,
)
from apps.organizations.modules.church.services.access import ensure_church_permission
from apps.organizations.modules.church.services.resources import (
    cancel_church_resource_reservation,
    complete_church_resource_reservation,
    create_church_resource,
    reserve_church_resource,
    update_church_resource,
)
from apps.organizations.permissions import OrganizationsEnabledPermission
from apps.organizations.views.helpers import raise_drf_validation_error

from .helpers import (
    get_church_campus_or_404,
    get_church_gathering_or_404,
    get_church_ministry_or_404,
    get_church_request_context,
    get_church_resource_or_404,
    get_church_resource_reservation_or_404,
)


def _serialize(serializer_class, instance, request):
    return serializer_class(
        instance,
        context={"request": request},
    ).data


def _ensure_resource_read(*, user, workspace):
    ensure_church_permission(
        actor=user,
        workspace=workspace,
        permission_key=ChurchPermissionKey.MANAGE_RESOURCES,
        require_write=False,
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


class ChurchResourcesView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def get(self, request, slug):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        _ensure_resource_read(user=request.user, workspace=workspace)

        queryset = (
            ChurchResource.objects
            .filter(workspace=workspace)
            .select_related("campus", "ministry")
            .order_by("sort_order", "name", "id")
        )
        return Response(
            ChurchResourceSerializer(
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
        serializer = ChurchResourceCreateSerializer(data=request.data)
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
            resource = create_church_resource(
                workspace=workspace,
                actor=request.user,
                campus=campus,
                ministry=ministry,
                **data,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            _serialize(ChurchResourceSerializer, resource, request),
            status=status.HTTP_201_CREATED,
        )


class ChurchResourceDetailView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def get(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        _ensure_resource_read(user=request.user, workspace=workspace)
        resource = get_church_resource_or_404(
            workspace=workspace,
            public_id=public_id,
        )
        return Response(_serialize(ChurchResourceSerializer, resource, request))

    def patch(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        resource = get_church_resource_or_404(
            workspace=workspace,
            public_id=public_id,
        )
        serializer = ChurchResourceUpdateSerializer(data=request.data)
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
            resource = update_church_resource(
                resource=resource,
                actor=request.user,
                **data,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(_serialize(ChurchResourceSerializer, resource, request))


class ChurchResourceReservationsView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def get(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        _ensure_resource_read(user=request.user, workspace=workspace)
        resource = get_church_resource_or_404(
            workspace=workspace,
            public_id=public_id,
        )
        queryset = (
            ChurchResourceReservation.objects
            .filter(resource=resource)
            .select_related("occurrence")
            .order_by("starts_at", "id")
        )
        include_closed = request.query_params.get("include_closed") == "1"
        if not include_closed:
            queryset = queryset.filter(
                status=ChurchResourceReservationStatus.RESERVED,
            )

        return Response(
            ChurchResourceReservationSerializer(
                queryset,
                many=True,
                context={"request": request},
            ).data
        )

    def post(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        resource = get_church_resource_or_404(
            workspace=workspace,
            public_id=public_id,
        )
        serializer = ChurchResourceReservationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        occurrence = get_church_gathering_or_404(
            workspace=workspace,
            public_id=data.pop("occurrence_public_id"),
        )

        try:
            reservation = reserve_church_resource(
                resource=resource,
                occurrence=occurrence,
                actor=request.user,
                **data,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            _serialize(
                ChurchResourceReservationSerializer,
                reservation,
                request,
            ),
            status=status.HTTP_201_CREATED,
        )


class _ChurchResourceReservationActionView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]
    action = None

    def post(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        reservation = get_church_resource_reservation_or_404(
            workspace=workspace,
            public_id=public_id,
        )

        try:
            reservation = self.action(
                reservation=reservation,
                actor=request.user,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            _serialize(
                ChurchResourceReservationSerializer,
                reservation,
                request,
            )
        )


class ChurchResourceReservationCancelView(_ChurchResourceReservationActionView):
    action = staticmethod(cancel_church_resource_reservation)


class ChurchResourceReservationCompleteView(_ChurchResourceReservationActionView):
    action = staticmethod(complete_church_resource_reservation)
