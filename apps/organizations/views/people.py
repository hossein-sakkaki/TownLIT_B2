# apps/organizations/views/people.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-30.
# Last Update by Hossein Sakkaki on 2026-09-30.
#

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Case, IntegerField, Prefetch, Q, Value, When
from django.db.models.functions import Lower
from django.shortcuts import get_object_or_404

from rest_framework import status, viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.boundaries.services.policy import BoundaryPolicy
from apps.core.pagination import ConfigurablePagination
from apps.organizations.constants import (
    CURRENT_MEMBERSHIP_STATUSES,
    MembershipRequestDirection,
    MembershipRequestStatus,
    OrganizationMembershipStatus,
    OrganizationPermissionKey,
    OrganizationRoleScope,
)
from apps.organizations.models import (
    Organization,
    OrganizationMembership,
    OrganizationMembershipRequest,
    OrganizationRole,
    OrganizationRoleAssignment,
)
from apps.organizations.permissions import OrganizationsEnabledPermission
from apps.organizations.serializers import (
    OrganizationMembershipRequestSerializer,
    OrganizationRoleSerializer,
)
from apps.organizations.serializers.people import (
    OrganizationMemberCandidateSerializer,
    OrganizationMembershipInvitationCreateSerializer,
    OrganizationMembershipManagementSerializer,
    OrganizationRoleAssignmentCreateSerializer,
    OrganizationRoleAssignmentManagementSerializer,
)
from apps.organizations.services.access import user_has_organization_permission
from apps.organizations.services.memberships import invite_member_to_organization
from apps.organizations.services.roles import assign_organization_role
from apps.profiles.models.member import Member

from .helpers import raise_drf_validation_error


PEOPLE_PERMISSIONS = [
    IsAuthenticated,
    OrganizationsEnabledPermission,
]


class OrganizationPeopleBaseViewSet(viewsets.ViewSet):
    permission_classes = PEOPLE_PERMISSIONS
    pagination_class = ConfigurablePagination
    pagination_page_size = 30

    def get_organization(self):
        return get_object_or_404(
            Organization,
            slug=self.kwargs["slug"],
        )

    def has_permission(self, organization, permission_key):
        return user_has_organization_permission(
            user=self.request.user,
            organization=organization,
            permission_key=permission_key,
            scope_type=OrganizationRoleScope.ORGANIZATION,
            scope_key="",
        )

    def require_permission(self, organization, permission_key):
        if not self.has_permission(organization, permission_key):
            raise PermissionDenied(
                "You do not have permission to manage this Organization area."
            )

    def paginated_response(self, queryset, serializer_class):
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(
            queryset,
            self.request,
            view=self,
        )
        serializer = serializer_class(
            page,
            many=True,
            context={"request": self.request},
        )
        return paginator.get_paginated_response(serializer.data)


class OrganizationMemberCandidatesView(OrganizationPeopleBaseViewSet):
    def list(self, request, slug=None):
        organization = self.get_organization()
        self.require_permission(
            organization,
            OrganizationPermissionKey.MANAGE_MEMBERS,
        )

        query = " ".join(
            str(request.query_params.get("q") or "").split()
        )

        if len(query) < 2:
            return Response([])

        boundary_excluded_ids = set(
            BoundaryPolicy.user_ids_with_boundary_between(request.user)
        )

        current_member_ids = (
            OrganizationMembership.objects
            .filter(
                organization=organization,
                status__in=CURRENT_MEMBERSHIP_STATUSES,
            )
            .values_list("member_id", flat=True)
        )
        pending_member_ids = (
            OrganizationMembershipRequest.objects
            .filter(
                organization=organization,
                status=MembershipRequestStatus.PENDING,
            )
            .values_list("member_id", flat=True)
        )

        queryset = (
            Member.objects
            .select_related(
                "user",
                "user__label",
                "user__member_profile",
            )
            .filter(
                is_active=True,
                user__is_active=True,
                user__is_deleted=False,
                user__is_suspended=False,
            )
            .exclude(id__in=current_member_ids)
            .exclude(id__in=pending_member_ids)
            .exclude(user_id__in=boundary_excluded_ids)
            .filter(
                Q(user__username__icontains=query)
                | Q(user__name__icontains=query)
                | Q(user__family__icontains=query)
            )
            .annotate(
                search_rank=Case(
                    When(user__username__iexact=query, then=Value(0)),
                    When(user__username__istartswith=query, then=Value(1)),
                    When(user__name__istartswith=query, then=Value(2)),
                    When(user__family__istartswith=query, then=Value(3)),
                    default=Value(4),
                    output_field=IntegerField(),
                ),
                username_lower=Lower("user__username"),
            )
            .order_by(
                "search_rank",
                "username_lower",
                "user_id",
            )[:30]
        )

        return Response(
            OrganizationMemberCandidateSerializer(
                queryset,
                many=True,
                context={"request": request},
            ).data
        )


class OrganizationMembersView(OrganizationPeopleBaseViewSet):
    def list(self, request, slug=None):
        organization = self.get_organization()

        can_manage_members = self.has_permission(
            organization,
            OrganizationPermissionKey.MANAGE_MEMBERS,
        )
        can_manage_roles = self.has_permission(
            organization,
            OrganizationPermissionKey.MANAGE_ROLES,
        )

        if not (can_manage_members or can_manage_roles):
            raise PermissionDenied(
                "You do not have permission to view Organization members."
            )

        assignment_queryset = (
            OrganizationRoleAssignment.objects
            .select_related("role")
            .prefetch_related("role__permissions")
            .filter(
                is_active=True,
                revoked_at__isnull=True,
                role__is_active=True,
            )
            .order_by("-role__priority", "id")
        )

        queryset = (
            OrganizationMembership.objects
            .select_related(
                "member__user",
                "member__user__label",
                "member__user__member_profile",
                "connection",
            )
            .prefetch_related(
                Prefetch(
                    "role_assignments",
                    queryset=assignment_queryset,
                    to_attr="active_role_assignments_cache",
                )
            )
            .filter(organization=organization)
        )

        if not can_manage_members:
            queryset = queryset.filter(
                status__in=CURRENT_MEMBERSHIP_STATUSES
            )

        status_filter = str(
            request.query_params.get("status") or ""
        ).strip().lower()

        if status_filter:
            if status_filter not in OrganizationMembershipStatus.values:
                raise ValidationError({
                    "status": "Unknown membership status.",
                })
            queryset = queryset.filter(status=status_filter)

        query = " ".join(
            str(request.query_params.get("q") or "").split()
        )
        if query:
            queryset = queryset.filter(
                Q(member__user__username__icontains=query)
                | Q(member__user__name__icontains=query)
                | Q(member__user__family__icontains=query)
            )

        queryset = queryset.annotate(
            status_rank=Case(
                When(
                    status=OrganizationMembershipStatus.ACTIVE,
                    then=Value(0),
                ),
                When(
                    status=OrganizationMembershipStatus.SUSPENDED,
                    then=Value(1),
                ),
                default=Value(2),
                output_field=IntegerField(),
            )
        ).order_by(
            "status_rank",
            "member__user__name",
            "member__user__family",
            "id",
        )

        return self.paginated_response(
            queryset,
            OrganizationMembershipManagementSerializer,
        )


class OrganizationMembershipRequestsManagementView(
    OrganizationPeopleBaseViewSet
):
    def list(self, request, slug=None):
        organization = self.get_organization()
        self.require_permission(
            organization,
            OrganizationPermissionKey.MANAGE_MEMBERS,
        )

        queryset = (
            OrganizationMembershipRequest.objects
            .select_related(
                "member__user",
                "member__user__label",
                "member__user__member_profile",
            )
            .filter(organization=organization)
        )

        direction = str(
            request.query_params.get("direction") or ""
        ).strip().lower()
        if direction:
            if direction not in MembershipRequestDirection.values:
                raise ValidationError({
                    "direction": "Unknown membership request direction.",
                })
            queryset = queryset.filter(direction=direction)

        status_filter = str(
            request.query_params.get("status") or MembershipRequestStatus.PENDING
        ).strip().lower()
        if status_filter != "all":
            if status_filter not in MembershipRequestStatus.values:
                raise ValidationError({
                    "status": "Unknown membership request status.",
                })
            queryset = queryset.filter(status=status_filter)

        query = " ".join(
            str(request.query_params.get("q") or "").split()
        )
        if query:
            queryset = queryset.filter(
                Q(member__user__username__icontains=query)
                | Q(member__user__name__icontains=query)
                | Q(member__user__family__icontains=query)
            )

        queryset = queryset.order_by("-created_at", "-id")

        return self.paginated_response(
            queryset,
            OrganizationMembershipRequestSerializer,
        )

    def create(self, request, slug=None):
        organization = self.get_organization()
        self.require_permission(
            organization,
            OrganizationPermissionKey.MANAGE_MEMBERS,
        )

        serializer = OrganizationMembershipInvitationCreateSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        member = (
            Member.objects
            .select_related("user")
            .filter(
                user_id=serializer.validated_data["member_user_id"],
                is_active=True,
                user__is_active=True,
                user__is_deleted=False,
                user__is_suspended=False,
            )
            .first()
        )

        if not member:
            raise ValidationError({
                "member_user_id": "This Member account is not available.",
            })

        boundary_excluded_ids = set(
            BoundaryPolicy.user_ids_with_boundary_between(request.user)
        )
        if member.user_id in boundary_excluded_ids:
            raise ValidationError({
                "member_user_id": "This Member account is not available.",
            })

        try:
            membership_request = invite_member_to_organization(
                actor=request.user,
                organization=organization,
                member=member,
                message=serializer.validated_data.get("message"),
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            OrganizationMembershipRequestSerializer(
                membership_request,
                context={"request": request},
            ).data,
            status=status.HTTP_201_CREATED,
        )


class OrganizationRolesView(OrganizationPeopleBaseViewSet):
    def list(self, request, slug=None):
        organization = self.get_organization()
        self.require_permission(
            organization,
            OrganizationPermissionKey.MANAGE_ROLES,
        )

        queryset = (
            OrganizationRole.objects
            .prefetch_related("permissions")
            .filter(
                organization=organization,
                is_active=True,
            )
            .order_by("-priority", "name", "id")
        )

        return Response(
            OrganizationRoleSerializer(
                queryset,
                many=True,
                context={"request": request},
            ).data
        )


class OrganizationRoleAssignmentsManagementView(
    OrganizationPeopleBaseViewSet
):
    def list(self, request, slug=None):
        organization = self.get_organization()
        self.require_permission(
            organization,
            OrganizationPermissionKey.MANAGE_ROLES,
        )

        queryset = (
            OrganizationRoleAssignment.objects
            .select_related(
                "membership__member__user",
                "membership__member__user__label",
                "membership__member__user__member_profile",
                "role",
            )
            .prefetch_related("role__permissions")
            .filter(membership__organization=organization)
        )

        membership_public_id = str(
            request.query_params.get("membership_public_id") or ""
        ).strip()
        if membership_public_id:
            queryset = queryset.filter(
                membership__public_id=membership_public_id
            )

        active_filter = str(
            request.query_params.get("active") or "true"
        ).strip().lower()
        if active_filter == "true":
            queryset = queryset.filter(
                is_active=True,
                revoked_at__isnull=True,
            )
        elif active_filter == "false":
            queryset = queryset.filter(is_active=False)
        elif active_filter != "all":
            raise ValidationError({
                "active": "Use true, false, or all.",
            })

        queryset = queryset.order_by(
            "-role__priority",
            "-created_at",
            "-id",
        )

        return self.paginated_response(
            queryset,
            OrganizationRoleAssignmentManagementSerializer,
        )

    def create(self, request, slug=None):
        organization = self.get_organization()
        self.require_permission(
            organization,
            OrganizationPermissionKey.MANAGE_ROLES,
        )

        serializer = OrganizationRoleAssignmentCreateSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        membership = get_object_or_404(
            OrganizationMembership.objects.select_related(
                "organization",
                "member__user",
            ),
            organization=organization,
            public_id=serializer.validated_data["membership_public_id"],
            status__in=CURRENT_MEMBERSHIP_STATUSES,
        )
        role = get_object_or_404(
            OrganizationRole,
            organization=organization,
            public_id=serializer.validated_data["role_public_id"],
            is_active=True,
        )

        try:
            assignment = assign_organization_role(
                membership=membership,
                role=role,
                actor=request.user,
                scope_type=serializer.validated_data["scope_type"],
                scope_key=serializer.validated_data["scope_key"],
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        assignment = (
            OrganizationRoleAssignment.objects
            .select_related(
                "membership__member__user",
                "membership__member__user__label",
                "membership__member__user__member_profile",
                "role",
            )
            .prefetch_related("role__permissions")
            .get(pk=assignment.pk)
        )

        return Response(
            OrganizationRoleAssignmentManagementSerializer(
                assignment,
                context={"request": request},
            ).data,
            status=status.HTTP_201_CREATED,
        )
