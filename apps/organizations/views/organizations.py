# apps/organizations/views/organizations.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-29.
# Last Update by Hossein Sakkaki on 2026-08-29.
#

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Count, Q

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.organizations.constants import (
    MembershipRequestStatus,
    CURRENT_MEMBERSHIP_STATUSES,
    OrganizationMembershipStatus,
    OrganizationPermissionKey,
    OrganizationRoleScope,
    OrganizationStatus,
    OrganizationVisibility,
)
from apps.organizations.feature_flags import (
    organization_creation_enabled,
)
from apps.organizations.models import (
    Organization,
    OrganizationMembership,
    OrganizationRole,
)
from apps.organizations.permissions import OrganizationsEnabledPermission
from apps.organizations.serializers import (
    OrganizationMembershipRequestSerializer,
    OrganizationMembershipSerializer,
    OrganizationRoleAssignmentSerializer,
    OrganizationRoleSerializer,
    OrganizationSerializer,
    OrganizationWriteSerializer,
)
from apps.organizations.services.access import (
    user_has_organization_permission,
)
from apps.organizations.services.creation import create_organization
from apps.organizations.services.follows import (
    follow_organization,
    unfollow_organization,
)
from apps.organizations.services.memberships import (
    invite_member_to_organization,
    request_organization_membership,
)
from apps.organizations.services.profile import update_organization_profile
from apps.organizations.services.roles import assign_organization_role
from apps.profiles.models.member import Member

from .helpers import raise_drf_validation_error


class OrganizationViewSet(viewsets.ModelViewSet):
    permission_classes = [
        IsAuthenticated,
        OrganizationsEnabledPermission,
    ]
    lookup_field = "slug"

    def get_queryset(self):
        base = Organization.objects.all()

        if not getattr(self.request.user, "is_staff", False):
            public_visibility = [OrganizationVisibility.PUBLIC]

            if self.action != "list":
                public_visibility.append(
                    OrganizationVisibility.UNLISTED
                )

            base = base.filter(
                Q(
                    status=OrganizationStatus.ACTIVE,
                    visibility__in=public_visibility,
                )
                | Q(
                    memberships__member__user=self.request.user,
                    memberships__status__in=CURRENT_MEMBERSHIP_STATUSES,
                )
            ).distinct()

        return base.annotate(
            follower_count=Count(
                "connections",
                filter=Q(
                    connections__status="active",
                    connections__relationship_type="follower",
                ),
                distinct=True,
            ),
            member_count=Count(
                "memberships",
                filter=Q(memberships__status="active"),
                distinct=True,
            ),
        )

    def get_serializer_class(self):
        if self.action in {
            "create",
            "update",
            "partial_update",
        }:
            return OrganizationWriteSerializer

        return OrganizationSerializer

    def create(self, request, *args, **kwargs):
        if not organization_creation_enabled():
            return Response(
                {
                    "detail": (
                        "Organization creation is currently unavailable."
                    ),
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            organization = create_organization(
                creator=request.user,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        output = OrganizationSerializer(
            organization,
            context=self.get_serializer_context(),
        )

        return Response(
            output.data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        organization = self.get_object()
        serializer = self.get_serializer(
            organization,
            data=request.data,
            partial=partial,
        )
        serializer.is_valid(raise_exception=True)

        try:
            organization = update_organization_profile(
                organization=organization,
                actor=request.user,
                validated_data=serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            OrganizationSerializer(
                organization,
                context=self.get_serializer_context(),
            ).data
        )

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        raise MethodNotAllowed(
            "DELETE",
            detail=(
                "Organization deletion requires the governance workflow."
            ),
        )

    @action(detail=True, methods=["post"])
    def follow(self, request, slug=None):
        organization = self.get_object()

        try:
            connection = follow_organization(
                user=request.user,
                organization=organization,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response({
            "relationship": connection.relationship_type,
            "status": connection.status,
        })

    @action(detail=True, methods=["post"])
    def unfollow(self, request, slug=None):
        organization = self.get_object()

        try:
            unfollow_organization(
                user=request.user,
                organization=organization,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=True,
        methods=["post"],
        url_path="request-membership",
    )
    def request_membership(self, request, slug=None):
        organization = self.get_object()
        member = getattr(request.user, "member_profile", None)

        if not member:
            raise PermissionDenied(
                "Only TownLIT Members can request organization membership."
            )

        try:
            membership_request = request_organization_membership(
                member=member,
                organization=organization,
                message=request.data.get("message"),
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            OrganizationMembershipRequestSerializer(
                membership_request,
                context=self.get_serializer_context(),
            ).data,
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="invite-member",
    )
    def invite_member(self, request, slug=None):
        organization = self.get_object()
        member_id = request.data.get("member_id")

        if not member_id:
            return Response(
                {"member_id": ["This field is required."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            member = Member.objects.select_related("user").get(
                pk=member_id,
                is_active=True,
            )
        except Member.DoesNotExist:
            return Response(
                {"member_id": ["Member not found."]},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            membership_request = invite_member_to_organization(
                actor=request.user,
                organization=organization,
                member=member,
                message=request.data.get("message"),
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            OrganizationMembershipRequestSerializer(
                membership_request,
                context=self.get_serializer_context(),
            ).data,
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=True,
        methods=["get"],
        url_path="members",
    )
    def members(self, request, slug=None):
        organization = self.get_object()

        if not user_has_organization_permission(
            user=request.user,
            organization=organization,
            permission_key=OrganizationPermissionKey.VIEW_ADMIN,
        ):
            raise PermissionDenied(
                "You do not have permission to view organization members."
            )

        memberships = (
            OrganizationMembership.objects
            .select_related("member__user")
            .filter(
                organization=organization,
                status=OrganizationMembershipStatus.ACTIVE,
            )
            .order_by("joined_at")
        )

        return Response(
            OrganizationMembershipSerializer(
                memberships,
                many=True,
                context=self.get_serializer_context(),
            ).data
        )

    @action(
        detail=True,
        methods=["get"],
        url_path="membership-requests",
    )
    def membership_requests(self, request, slug=None):
        organization = self.get_object()

        if not user_has_organization_permission(
            user=request.user,
            organization=organization,
            permission_key=OrganizationPermissionKey.MANAGE_MEMBERS,
        ):
            raise PermissionDenied(
                "You do not have permission to manage membership requests."
            )

        requests_qs = (
            organization.membership_requests
            .select_related("member__user")
            .filter(status=MembershipRequestStatus.PENDING)
            .order_by("created_at")
        )

        return Response(
            OrganizationMembershipRequestSerializer(
                requests_qs,
                many=True,
                context=self.get_serializer_context(),
            ).data
        )

    @action(
        detail=True,
        methods=["get"],
        url_path="roles",
    )
    def roles(self, request, slug=None):
        organization = self.get_object()

        if not user_has_organization_permission(
            user=request.user,
            organization=organization,
            permission_key=OrganizationPermissionKey.VIEW_ADMIN,
        ):
            raise PermissionDenied(
                "You do not have permission to view organization roles."
            )

        roles = (
            OrganizationRole.objects
            .prefetch_related("permissions")
            .filter(
                organization=organization,
                is_active=True,
            )
        )

        return Response(
            OrganizationRoleSerializer(
                roles,
                many=True,
                context=self.get_serializer_context(),
            ).data
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="assign-role",
    )
    def assign_role(self, request, slug=None):
        organization = self.get_object()
        membership_public_id = request.data.get(
            "membership_public_id"
        )
        role_key = request.data.get("role_key")

        if not membership_public_id or not role_key:
            return Response(
                {
                    "detail": (
                        "membership_public_id and role_key are required."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            membership = OrganizationMembership.objects.get(
                organization=organization,
                public_id=membership_public_id,
            )
            role = OrganizationRole.objects.get(
                organization=organization,
                key=role_key,
                is_active=True,
            )
        except (
            OrganizationMembership.DoesNotExist,
            OrganizationRole.DoesNotExist,
        ):
            return Response(
                {"detail": "Membership or role not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            assignment = assign_organization_role(
                membership=membership,
                role=role,
                actor=request.user,
                scope_type=request.data.get(
                    "scope_type",
                    OrganizationRoleScope.ORGANIZATION,
                ),
                scope_key=request.data.get(
                    "scope_key",
                    "",
                ),
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            OrganizationRoleAssignmentSerializer(
                assignment,
                context=self.get_serializer_context(),
            ).data,
            status=status.HTTP_201_CREATED,
        )
