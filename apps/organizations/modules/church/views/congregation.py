# apps/organizations/modules/church/views/congregation.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-08.
# Last Update by Hossein Sakkaki on 2026-09-08.
#

from django.apps import apps
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q

from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.pagination import ConfigurablePagination
from apps.organizations.modules.church.constants import (
    ChurchCongregantStatus,
    ChurchPermissionKey,
)
from apps.organizations.modules.church.models import ChurchHousehold
from apps.organizations.modules.church.selectors.congregation import (
    list_internal_church_congregants,
    list_member_visible_church_congregants,
)
from apps.organizations.modules.church.serializers import (
    ChurchCongregantSerializer,
    ChurchCongregantUpdateSerializer,
    ChurchDirectoryVisibilityUpdateSerializer,
    ChurchExternalCongregantCreateSerializer,
    ChurchGuestCongregantCreateSerializer,
    ChurchHouseholdCreateSerializer,
    ChurchHouseholdMemberAddSerializer,
    ChurchHouseholdMembershipSerializer,
    ChurchHouseholdSerializer,
    ChurchHouseholdUpdateSerializer,
    ChurchMemberCongregantCreateSerializer,
    ChurchMemberDirectoryEntrySerializer,
)
from apps.organizations.modules.church.services.access import ensure_church_permission
from apps.organizations.modules.church.services.congregation import (
    register_external_congregant,
    register_guest_congregant,
    register_member_congregant,
    set_own_church_directory_visibility,
    sync_member_congregant_official_membership,
    update_church_congregant,
)
from apps.organizations.modules.church.services.households import (
    add_church_household_member,
    create_church_household,
    remove_church_household_member,
    update_church_household,
)
from apps.organizations.permissions import OrganizationsEnabledPermission
from apps.organizations.views.helpers import raise_drf_validation_error

from .helpers import (
    get_church_campus_or_404,
    get_church_congregant_or_404,
    get_church_household_membership_or_404,
    get_church_household_or_404,
    get_church_request_context,
    viewer_is_active_organization_member,
)


class ChurchDirectoryPagination(ConfigurablePagination):
    page_size = 50
    max_page_size = 100


def _paginate(*, request, view, queryset, serializer_class):
    paginator = ChurchDirectoryPagination()
    page = paginator.paginate_queryset(
        queryset,
        request,
        view=view,
    )
    serializer = serializer_class(
        page,
        many=True,
        context={"request": request},
    )
    return paginator.get_paginated_response(serializer.data)


def _apply_congregant_filters(*, queryset, request, allow_status):
    query = " ".join(str(request.query_params.get("q") or "").split())
    campus_public_id = request.query_params.get("campus")
    status_value = request.query_params.get("status")

    if query:
        queryset = queryset.filter(
            Q(preferred_name__icontains=query)
            | Q(display_name_snapshot__icontains=query)
            | Q(member__user__username__icontains=query)
            | Q(member__user__name__icontains=query)
            | Q(member__user__family__icontains=query)
            | Q(guest_profile__user__username__icontains=query)
            | Q(guest_profile__user__name__icontains=query)
            | Q(guest_profile__user__family__icontains=query)
        )

    if campus_public_id:
        queryset = queryset.filter(campus__public_id=campus_public_id)

    if allow_status and status_value:
        valid_statuses = {value for value, _ in ChurchCongregantStatus.choices}
        if status_value not in valid_statuses:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"status": "Unsupported Church congregant status."})
        queryset = queryset.filter(status=status_value)

    return queryset


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


def _ensure_congregation_manage(*, user, workspace):
    ensure_church_permission(
        actor=user,
        workspace=workspace,
        permission_key=ChurchPermissionKey.MANAGE_CONGREGATION_DIRECTORY,
        require_write=True,
    )


def _ensure_households_manage(*, user, workspace, require_write=True):
    ensure_church_permission(
        actor=user,
        workspace=workspace,
        permission_key=ChurchPermissionKey.MANAGE_HOUSEHOLDS,
        require_write=require_write,
    )


def _get_member_by_user_id(user_id):
    Member = apps.get_model("profiles", "Member")
    member = (
        Member.objects
        .select_related("user", "user__label")
        .filter(user_id=user_id)
        .first()
    )
    if not member:
        raise NotFound("Member profile not found.")
    return member


def _get_guest_by_user_id(user_id):
    GuestUser = apps.get_model("profiles", "GuestUser")
    guest = (
        GuestUser.objects
        .select_related("user", "user__label")
        .filter(user_id=user_id)
        .first()
    )
    if not guest:
        raise NotFound("Guest profile not found.")
    return guest


class ChurchCongregantsView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def get(self, request, slug):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        ensure_church_permission(
            actor=request.user,
            workspace=workspace,
            permission_key=ChurchPermissionKey.VIEW_CONGREGATION_DIRECTORY,
            require_write=False,
        )
        queryset = list_internal_church_congregants(
            workspace=workspace,
            actor=request.user,
        )
        queryset = _apply_congregant_filters(
            queryset=queryset,
            request=request,
            allow_status=True,
        )
        return _paginate(
            request=request,
            view=self,
            queryset=queryset,
            serializer_class=ChurchCongregantSerializer,
        )


class ChurchMemberCongregantCreateView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def post(self, request, slug):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        _ensure_congregation_manage(user=request.user, workspace=workspace)
        serializer = ChurchMemberCongregantCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)

        member = _get_member_by_user_id(data.pop("user_id"))
        campus = _resolve_optional_campus(
            workspace=workspace,
            public_id=data.pop("campus_public_id", None),
        )

        try:
            congregant = register_member_congregant(
                workspace=workspace,
                member=member,
                actor=request.user,
                campus=campus,
                **data,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            _serialize(ChurchCongregantSerializer, congregant, request),
            status=status.HTTP_201_CREATED,
        )


class ChurchGuestCongregantCreateView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def post(self, request, slug):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        _ensure_congregation_manage(user=request.user, workspace=workspace)
        serializer = ChurchGuestCongregantCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)

        guest = _get_guest_by_user_id(data.pop("user_id"))
        campus = _resolve_optional_campus(
            workspace=workspace,
            public_id=data.pop("campus_public_id", None),
        )

        try:
            congregant = register_guest_congregant(
                workspace=workspace,
                guest_profile=guest,
                actor=request.user,
                campus=campus,
                **data,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            _serialize(ChurchCongregantSerializer, congregant, request),
            status=status.HTTP_201_CREATED,
        )


class ChurchExternalCongregantCreateView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def post(self, request, slug):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        _ensure_congregation_manage(user=request.user, workspace=workspace)
        serializer = ChurchExternalCongregantCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)

        campus = _resolve_optional_campus(
            workspace=workspace,
            public_id=data.pop("campus_public_id", None),
        )

        try:
            congregant = register_external_congregant(
                workspace=workspace,
                actor=request.user,
                campus=campus,
                **data,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            _serialize(ChurchCongregantSerializer, congregant, request),
            status=status.HTTP_201_CREATED,
        )


class ChurchCongregantDetailView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def get(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        ensure_church_permission(
            actor=request.user,
            workspace=workspace,
            permission_key=ChurchPermissionKey.VIEW_CONGREGATION_DIRECTORY,
            require_write=False,
        )
        congregant = get_church_congregant_or_404(
            workspace=workspace,
            public_id=public_id,
        )
        return Response(_serialize(ChurchCongregantSerializer, congregant, request))

    def patch(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        _ensure_congregation_manage(user=request.user, workspace=workspace)
        congregant = get_church_congregant_or_404(
            workspace=workspace,
            public_id=public_id,
        )
        serializer = ChurchCongregantUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)

        if "campus_public_id" in data:
            data["campus"] = _resolve_optional_campus(
                workspace=workspace,
                public_id=data.pop("campus_public_id"),
            )

        try:
            congregant = update_church_congregant(
                congregant=congregant,
                actor=request.user,
                **data,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(_serialize(ChurchCongregantSerializer, congregant, request))


class ChurchCongregantSyncOfficialMembershipView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def post(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        _ensure_congregation_manage(user=request.user, workspace=workspace)
        congregant = get_church_congregant_or_404(
            workspace=workspace,
            public_id=public_id,
        )
        try:
            congregant = sync_member_congregant_official_membership(
                congregant=congregant,
                actor=request.user,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(_serialize(ChurchCongregantSerializer, congregant, request))


class ChurchCongregantDirectoryVisibilityView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def patch(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        from apps.organizations.modules.church.models import ChurchCongregant

        congregant = (
            ChurchCongregant.objects
            .select_related(
                "workspace__activation__organization",
                "member__user",
                "official_membership",
                "campus",
            )
            .filter(
                workspace=workspace,
                public_id=public_id,
                member__user=request.user,
            )
            .first()
        )
        if not congregant:
            raise NotFound("Church congregant not found.")

        serializer = ChurchDirectoryVisibilityUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            congregant = set_own_church_directory_visibility(
                congregant=congregant,
                actor=request.user,
                visibility=serializer.validated_data["visibility"],
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(_serialize(ChurchCongregantSerializer, congregant, request))


class ChurchMemberDirectoryView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def get(self, request, slug):
        organization, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        if not workspace.membership_directory_enabled:
            raise PermissionDenied("Church member directory is disabled.")
        if not viewer_is_active_organization_member(
            user=request.user,
            organization=organization,
        ):
            raise PermissionDenied(
                "An active official Organization membership is required to view the Church member directory."
            )

        queryset = list_member_visible_church_congregants(
            workspace=workspace,
            viewer=request.user,
        )
        queryset = _apply_congregant_filters(
            queryset=queryset,
            request=request,
            allow_status=False,
        )
        return _paginate(
            request=request,
            view=self,
            queryset=queryset,
            serializer_class=ChurchMemberDirectoryEntrySerializer,
        )


class ChurchHouseholdsView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def get(self, request, slug):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        _ensure_households_manage(
            user=request.user,
            workspace=workspace,
            require_write=False,
        )
        queryset = (
            ChurchHousehold.objects
            .filter(workspace=workspace)
            .select_related("campus")
            .prefetch_related(
                "memberships__congregant__member__user",
                "memberships__congregant__guest_profile__user",
                "memberships__congregant__campus",
            )
            .order_by("name", "id")
        )
        return Response(
            ChurchHouseholdSerializer(
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
        _ensure_households_manage(user=request.user, workspace=workspace)
        serializer = ChurchHouseholdCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        campus = _resolve_optional_campus(
            workspace=workspace,
            public_id=data.pop("campus_public_id", None),
        )

        try:
            household = create_church_household(
                workspace=workspace,
                actor=request.user,
                campus=campus,
                **data,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            _serialize(ChurchHouseholdSerializer, household, request),
            status=status.HTTP_201_CREATED,
        )


class ChurchHouseholdDetailView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def get(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        _ensure_households_manage(
            user=request.user,
            workspace=workspace,
            require_write=False,
        )
        household = get_church_household_or_404(
            workspace=workspace,
            public_id=public_id,
        )
        return Response(_serialize(ChurchHouseholdSerializer, household, request))

    def patch(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        _ensure_households_manage(user=request.user, workspace=workspace)
        household = get_church_household_or_404(
            workspace=workspace,
            public_id=public_id,
        )
        serializer = ChurchHouseholdUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)

        if "campus_public_id" in data:
            data["campus"] = _resolve_optional_campus(
                workspace=workspace,
                public_id=data.pop("campus_public_id"),
            )

        try:
            household = update_church_household(
                household=household,
                actor=request.user,
                **data,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(_serialize(ChurchHouseholdSerializer, household, request))


class ChurchHouseholdMembersView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def post(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        _ensure_households_manage(user=request.user, workspace=workspace)
        household = get_church_household_or_404(
            workspace=workspace,
            public_id=public_id,
        )
        serializer = ChurchHouseholdMemberAddSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        congregant = get_church_congregant_or_404(
            workspace=workspace,
            public_id=data.pop("congregant_public_id"),
        )

        try:
            membership = add_church_household_member(
                household=household,
                congregant=congregant,
                actor=request.user,
                **data,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            _serialize(ChurchHouseholdMembershipSerializer, membership, request),
            status=status.HTTP_201_CREATED,
        )


class ChurchHouseholdMembershipRemoveView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def post(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        _ensure_households_manage(user=request.user, workspace=workspace)
        membership = get_church_household_membership_or_404(
            workspace=workspace,
            public_id=public_id,
        )

        try:
            membership = remove_church_household_member(
                household_membership=membership,
                actor=request.user,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            _serialize(ChurchHouseholdMembershipSerializer, membership, request)
        )
