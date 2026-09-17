# apps/organizations/modules/church/views/attendance.py
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

from apps.organizations.modules.church.constants import ChurchPermissionKey
from apps.organizations.modules.church.models import ChurchAttendanceSession
from apps.organizations.modules.church.serializers import (
    ChurchAttendanceCheckInSerializer,
    ChurchAttendanceGuestCountsSerializer,
    ChurchAttendanceOpenSerializer,
    ChurchAttendanceRecordSerializer,
    ChurchAttendanceSessionDetailSerializer,
    ChurchAttendanceSessionSerializer,
)
from apps.organizations.modules.church.services.attendance import (
    check_in_church_member,
    check_out_church_member,
    close_church_attendance_session,
    open_church_attendance_session,
    update_church_guest_counts,
)
from apps.organizations.permissions import OrganizationsEnabledPermission
from apps.organizations.views.helpers import raise_drf_validation_error

from .helpers import (
    ensure_any_church_permission,
    get_church_attendance_record_or_404,
    get_church_attendance_session_or_404,
    get_church_gathering_or_404,
    get_church_request_context,
    get_organization_membership_or_404,
)


ATTENDANCE_READ_PERMISSIONS = (
    ChurchPermissionKey.VIEW_ATTENDANCE,
    ChurchPermissionKey.MANAGE_ATTENDANCE,
)


def _ensure_attendance_read(*, user, workspace):
    ensure_any_church_permission(
        user=user,
        workspace=workspace,
        permission_keys=ATTENDANCE_READ_PERMISSIONS,
    )


def _serialize(serializer_class, instance, request):
    return serializer_class(
        instance,
        context={"request": request},
    ).data


class ChurchAttendanceSessionsView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def get(self, request, slug):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        _ensure_attendance_read(user=request.user, workspace=workspace)

        queryset = (
            ChurchAttendanceSession.objects
            .filter(workspace=workspace)
            .select_related("occurrence")
            .order_by("-opened_at", "-id")
        )

        occurrence_public_id = request.query_params.get("occurrence_public_id")
        if occurrence_public_id:
            queryset = queryset.filter(
                occurrence__public_id=occurrence_public_id,
            )

        return Response(
            ChurchAttendanceSessionSerializer(
                queryset[:200],
                many=True,
                context={"request": request},
            ).data
        )

    def post(self, request, slug):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        serializer = ChurchAttendanceOpenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        occurrence = get_church_gathering_or_404(
            workspace=workspace,
            public_id=serializer.validated_data["occurrence_public_id"],
        )

        try:
            session = open_church_attendance_session(
                occurrence=occurrence,
                actor=request.user,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            _serialize(
                ChurchAttendanceSessionDetailSerializer,
                session,
                request,
            ),
            status=status.HTTP_201_CREATED,
        )


class ChurchAttendanceSessionDetailView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def get(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        _ensure_attendance_read(user=request.user, workspace=workspace)

        session = get_church_attendance_session_or_404(
            workspace=workspace,
            public_id=public_id,
        )
        return Response(
            _serialize(
                ChurchAttendanceSessionDetailSerializer,
                session,
                request,
            )
        )


class ChurchAttendanceCheckInView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def post(self, request, slug, public_id):
        organization, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        session = get_church_attendance_session_or_404(
            workspace=workspace,
            public_id=public_id,
        )
        serializer = ChurchAttendanceCheckInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)

        membership = get_organization_membership_or_404(
            organization=organization,
            public_id=data.pop("membership_public_id"),
        )

        try:
            record = check_in_church_member(
                session=session,
                membership=membership,
                actor=request.user,
                **data,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            _serialize(
                ChurchAttendanceRecordSerializer,
                record,
                request,
            ),
            status=status.HTTP_201_CREATED,
        )


class ChurchAttendanceRecordCheckOutView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def post(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        record = get_church_attendance_record_or_404(
            workspace=workspace,
            public_id=public_id,
        )

        try:
            record = check_out_church_member(
                record=record,
                actor=request.user,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            _serialize(
                ChurchAttendanceRecordSerializer,
                record,
                request,
            )
        )


class ChurchAttendanceGuestCountsView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def post(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        session = get_church_attendance_session_or_404(
            workspace=workspace,
            public_id=public_id,
        )
        serializer = ChurchAttendanceGuestCountsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            session = update_church_guest_counts(
                session=session,
                actor=request.user,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            _serialize(
                ChurchAttendanceSessionDetailSerializer,
                session,
                request,
            )
        )


class ChurchAttendanceCloseView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def post(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        session = get_church_attendance_session_or_404(
            workspace=workspace,
            public_id=public_id,
        )

        try:
            session = close_church_attendance_session(
                session=session,
                actor=request.user,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            _serialize(
                ChurchAttendanceSessionDetailSerializer,
                session,
                request,
            )
        )
