# apps/organizations/views/membership_requests.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-29.
# Last Update by Hossein Sakkaki on 2026-08-29.
#

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q

from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.organizations.constants import OrganizationPermissionKey
from apps.organizations.models import OrganizationMembershipRequest
from apps.organizations.permissions import OrganizationsEnabledPermission
from apps.organizations.serializers import (
    OrganizationMembershipRequestSerializer,
    OrganizationMembershipSerializer,
)
from apps.organizations.services.access import organization_ids_for_user_permission
from apps.organizations.services.memberships import (
    accept_membership_request,
    cancel_membership_invitation,
    reject_membership_request,
    withdraw_membership_request,
)

from .helpers import raise_drf_validation_error


class OrganizationMembershipRequestViewSet(
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = OrganizationMembershipRequestSerializer
    permission_classes = [
        IsAuthenticated,
        OrganizationsEnabledPermission,
    ]
    lookup_field = "public_id"

    def get_queryset(self):
        user = self.request.user
        queryset = (
            OrganizationMembershipRequest.objects
            .select_related(
                "organization",
                "member__user",
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
    def accept(self, request, public_id=None):
        membership_request = self.get_object()

        try:
            membership = accept_membership_request(
                membership_request=membership_request,
                actor=request.user,
                response_message=request.data.get(
                    "response_message"
                ),
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            OrganizationMembershipSerializer(
                membership,
                context=self.get_serializer_context(),
            ).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def reject(self, request, public_id=None):
        membership_request = self.get_object()

        try:
            membership_request = reject_membership_request(
                membership_request=membership_request,
                actor=request.user,
                response_message=request.data.get(
                    "response_message"
                ),
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            self.get_serializer(membership_request).data
        )

    @action(detail=True, methods=["post"])
    def withdraw(self, request, public_id=None):
        membership_request = self.get_object()

        try:
            membership_request = withdraw_membership_request(
                membership_request=membership_request,
                actor=request.user,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            self.get_serializer(membership_request).data
        )

    @action(detail=True, methods=["post"])
    def cancel(self, request, public_id=None):
        membership_request = self.get_object()

        try:
            membership_request = cancel_membership_invitation(
                membership_request=membership_request,
                actor=request.user,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            self.get_serializer(membership_request).data
        )
