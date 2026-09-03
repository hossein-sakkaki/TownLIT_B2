# apps/organizations/views/memberships.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-29.
# Last Update by Hossein Sakkaki on 2026-08-29.
#

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q

from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.organizations.constants import OrganizationPermissionKey
from apps.organizations.models import OrganizationMembership
from apps.organizations.permissions import OrganizationsEnabledPermission
from apps.organizations.serializers import OrganizationMembershipSerializer
from apps.organizations.services.access import organization_ids_for_user_permission
from apps.organizations.services.memberships import (
    leave_organization,
    remove_organization_member,
)

from .helpers import raise_drf_validation_error


class OrganizationMembershipViewSet(
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = OrganizationMembershipSerializer
    permission_classes = [
        IsAuthenticated,
        OrganizationsEnabledPermission,
    ]
    lookup_field = "public_id"

    def get_queryset(self):
        user = self.request.user
        queryset = (
            OrganizationMembership.objects
            .select_related(
                "organization",
                "member__user",
                "connection",
            )
        )

        if getattr(user, "is_staff", False):
            return queryset

        managed_ids = organization_ids_for_user_permission(
            user=user,
            permission_key=OrganizationPermissionKey.MANAGE_MEMBERS,
        )

        return queryset.filter(
            Q(member__user=user)
            | Q(organization_id__in=managed_ids)
        ).distinct()

    @action(detail=True, methods=["post"])
    def leave(self, request, public_id=None):
        membership = self.get_object()

        try:
            membership = leave_organization(
                membership=membership,
                actor=request.user,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            self.get_serializer(membership).data
        )

    @action(detail=True, methods=["post"])
    def remove(self, request, public_id=None):
        membership = self.get_object()

        try:
            membership = remove_organization_member(
                membership=membership,
                actor=request.user,
                reason=request.data.get("reason"),
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            self.get_serializer(membership).data
        )
