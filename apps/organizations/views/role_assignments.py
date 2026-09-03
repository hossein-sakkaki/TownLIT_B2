# apps/organizations/views/role_assignments.py
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
from apps.organizations.models import OrganizationRoleAssignment
from apps.organizations.permissions import OrganizationsEnabledPermission
from apps.organizations.serializers import OrganizationRoleAssignmentSerializer
from apps.organizations.services.access import organization_ids_for_user_permission
from apps.organizations.services.roles import revoke_organization_role

from .helpers import raise_drf_validation_error


class OrganizationRoleAssignmentViewSet(
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = OrganizationRoleAssignmentSerializer
    permission_classes = [
        IsAuthenticated,
        OrganizationsEnabledPermission,
    ]
    lookup_field = "public_id"

    def get_queryset(self):
        user = self.request.user
        queryset = (
            OrganizationRoleAssignment.objects
            .select_related(
                "role",
                "membership__organization",
                "membership__member__user",
            )
        )

        if getattr(user, "is_staff", False):
            return queryset

        managed_ids = organization_ids_for_user_permission(
            user=user,
            permission_key=OrganizationPermissionKey.VIEW_ADMIN,
        )

        return queryset.filter(
            Q(membership__member__user=user)
            | Q(membership__organization_id__in=managed_ids)
        ).distinct()

    @action(detail=True, methods=["post"])
    def revoke(self, request, public_id=None):
        assignment = self.get_object()

        try:
            assignment = revoke_organization_role(
                assignment=assignment,
                actor=request.user,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            self.get_serializer(assignment).data
        )
