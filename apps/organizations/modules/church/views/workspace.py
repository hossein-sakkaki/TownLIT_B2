# apps/organizations/modules/church/views/workspace.py
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
    ChurchCampusStatus,
    ChurchLeadershipAssignmentStatus,
    ChurchPermissionKey,
)
from apps.organizations.modules.church.models import ChurchCampus
from apps.organizations.modules.church.serializers import (
    ChurchCampusCreateSerializer,
    ChurchCampusSerializer,
    ChurchCampusUpdateSerializer,
    ChurchLeadershipAssignmentSerializer,
    ChurchLeadershipAssignSerializer,
    ChurchMinistryCreateSerializer,
    ChurchMinistrySerializer,
    ChurchMinistryUpdateSerializer,
    ChurchWorkspaceSerializer,
    ChurchWorkspaceUpdateSerializer,
)
from apps.organizations.modules.church.services.access import user_has_church_permission
from apps.organizations.modules.church.services.campuses import (
    archive_church_campus,
    create_church_campus,
    set_primary_church_campus,
    update_church_campus,
)
from apps.organizations.modules.church.services.leadership import (
    assign_church_leadership,
    end_church_leadership,
)
from apps.organizations.modules.church.services.ministries import (
    create_church_ministry,
    update_church_ministry,
)
from apps.organizations.modules.church.services.workspace import update_church_workspace
from apps.organizations.permissions import OrganizationsEnabledPermission
from apps.organizations.views.helpers import raise_drf_validation_error

from .helpers import (
    get_address_or_404,
    get_church_campus_or_404,
    get_church_leadership_or_404,
    get_church_ministry_or_404,
    get_church_request_context,
    get_organization_membership_or_404,
    visible_church_leadership,
    visible_church_ministries,
)


def _serialize(serializer_class, instance, request):
    return serializer_class(
        instance,
        context={"request": request},
    ).data


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


class ChurchWorkspaceView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def get(self, request, slug):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        return Response(
            _serialize(
                ChurchWorkspaceSerializer,
                workspace,
                request,
            )
        )

    def patch(self, request, slug):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        serializer = ChurchWorkspaceUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            workspace = update_church_workspace(
                workspace=workspace,
                actor=request.user,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            _serialize(
                ChurchWorkspaceSerializer,
                workspace,
                request,
            )
        )


class ChurchCampusesView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def get(self, request, slug):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )

        queryset = (
            ChurchCampus.objects
            .filter(workspace=workspace)
            .select_related("address")
            .order_by("sort_order", "name", "id")
        )

        if not user_has_church_permission(
            user=request.user,
            workspace=workspace,
            permission_key=ChurchPermissionKey.MANAGE_CAMPUSES,
        ):
            queryset = queryset.filter(status=ChurchCampusStatus.ACTIVE)

        return Response(
            ChurchCampusSerializer(
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
        serializer = ChurchCampusCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)

        address_id = data.pop("address_id", None)
        address = get_address_or_404(address_id)

        try:
            campus = create_church_campus(
                workspace=workspace,
                actor=request.user,
                address=address,
                **data,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            _serialize(
                ChurchCampusSerializer,
                campus,
                request,
            ),
            status=status.HTTP_201_CREATED,
        )


class ChurchCampusDetailView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def get(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        campus = get_church_campus_or_404(
            workspace=workspace,
            public_id=public_id,
        )

        if (
            campus.status != ChurchCampusStatus.ACTIVE
            and not user_has_church_permission(
                user=request.user,
                workspace=workspace,
                permission_key=ChurchPermissionKey.MANAGE_CAMPUSES,
            )
        ):
            from rest_framework.exceptions import NotFound
            raise NotFound("Church campus not found.")

        return Response(
            _serialize(
                ChurchCampusSerializer,
                campus,
                request,
            )
        )

    def patch(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        campus = get_church_campus_or_404(
            workspace=workspace,
            public_id=public_id,
        )
        serializer = ChurchCampusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)

        if "address_id" in data:
            data["address"] = get_address_or_404(data.pop("address_id"))

        try:
            campus = update_church_campus(
                campus=campus,
                actor=request.user,
                **data,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            _serialize(
                ChurchCampusSerializer,
                campus,
                request,
            )
        )


class ChurchCampusPrimaryView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def post(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        campus = get_church_campus_or_404(
            workspace=workspace,
            public_id=public_id,
        )

        try:
            campus = set_primary_church_campus(
                campus=campus,
                actor=request.user,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            _serialize(
                ChurchCampusSerializer,
                campus,
                request,
            )
        )


class ChurchCampusArchiveView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def post(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        campus = get_church_campus_or_404(
            workspace=workspace,
            public_id=public_id,
        )

        try:
            campus = archive_church_campus(
                campus=campus,
                actor=request.user,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            _serialize(
                ChurchCampusSerializer,
                campus,
                request,
            )
        )


class ChurchMinistriesView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def get(self, request, slug):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        queryset = visible_church_ministries(
            user=request.user,
            workspace=workspace,
        )

        return Response(
            ChurchMinistrySerializer(
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
        serializer = ChurchMinistryCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)

        campus_public_id = data.pop("campus_public_id", None)
        campus = _resolve_optional_campus(
            workspace=workspace,
            public_id=campus_public_id,
        )

        try:
            ministry = create_church_ministry(
                workspace=workspace,
                actor=request.user,
                campus=campus,
                **data,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            _serialize(
                ChurchMinistrySerializer,
                ministry,
                request,
            ),
            status=status.HTTP_201_CREATED,
        )


class ChurchMinistryDetailView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def get(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        ministry = get_church_ministry_or_404(
            workspace=workspace,
            public_id=public_id,
        )

        if not visible_church_ministries(
            user=request.user,
            workspace=workspace,
        ).filter(pk=ministry.pk).exists():
            from rest_framework.exceptions import NotFound
            raise NotFound("Church ministry not found.")

        return Response(
            _serialize(
                ChurchMinistrySerializer,
                ministry,
                request,
            )
        )

    def patch(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        ministry = get_church_ministry_or_404(
            workspace=workspace,
            public_id=public_id,
        )
        serializer = ChurchMinistryUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)

        if "campus_public_id" in data:
            data["campus"] = _resolve_optional_campus(
                workspace=workspace,
                public_id=data.pop("campus_public_id"),
            )

        try:
            ministry = update_church_ministry(
                ministry=ministry,
                actor=request.user,
                **data,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            _serialize(
                ChurchMinistrySerializer,
                ministry,
                request,
            )
        )


class ChurchLeadershipView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def get(self, request, slug):
        organization, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        queryset = visible_church_leadership(
            user=request.user,
            workspace=workspace,
        )

        return Response(
            ChurchLeadershipAssignmentSerializer(
                queryset,
                many=True,
                context={"request": request},
            ).data
        )

    def post(self, request, slug):
        organization, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        serializer = ChurchLeadershipAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)

        membership = get_organization_membership_or_404(
            organization=organization,
            public_id=data.pop("membership_public_id"),
        )
        campus = _resolve_optional_campus(
            workspace=workspace,
            public_id=data.pop("campus_public_id", None),
        )
        ministry = _resolve_optional_ministry(
            workspace=workspace,
            public_id=data.pop("ministry_public_id", None),
        )

        try:
            assignment = assign_church_leadership(
                workspace=workspace,
                membership=membership,
                actor=request.user,
                campus=campus,
                ministry=ministry,
                **data,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            _serialize(
                ChurchLeadershipAssignmentSerializer,
                assignment,
                request,
            ),
            status=status.HTTP_201_CREATED,
        )


class ChurchLeadershipDetailView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def get(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        assignment = get_church_leadership_or_404(
            workspace=workspace,
            public_id=public_id,
        )

        if not visible_church_leadership(
            user=request.user,
            workspace=workspace,
        ).filter(pk=assignment.pk).exists():
            from rest_framework.exceptions import NotFound
            raise NotFound("Church leadership assignment not found.")

        return Response(
            _serialize(
                ChurchLeadershipAssignmentSerializer,
                assignment,
                request,
            )
        )


class ChurchLeadershipEndView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def post(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        assignment = get_church_leadership_or_404(
            workspace=workspace,
            public_id=public_id,
        )

        try:
            assignment = end_church_leadership(
                assignment=assignment,
                actor=request.user,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            _serialize(
                ChurchLeadershipAssignmentSerializer,
                assignment,
                request,
            )
        )
